from __future__ import absolute_import, unicode_literals

from hitrack_celery.celery import celery_app
import logging
import re
from datetime import timedelta
from django.utils import timezone

# Configure logging
logger = logging.getLogger(__name__)

DOCKER_IMAGE_REGEX = re.compile(r'^[a-zA-Z0-9._/-]+(:[a-zA-Z0-9._-]+)?$')

def is_safe_image_ref(image_ref: str) -> bool:
    return bool(DOCKER_IMAGE_REGEX.match(image_ref)) and len(image_ref) < 200

@celery_app.task(bind=True, max_retries=1)
def generate_sbom_and_create_components(self, image_uuid: str, art_type: str="docker"):
    """
    Generate SBOM data for an image using Syft.
    This task can be retried up to 1 times if it fails.
    """
    from .models import Image, ContainerRegistry
    import subprocess
    import json
    import tempfile
    import os
    from .utils.acr import get_bearer_token

    logger.info(f"Starting SBOM generation for image {image_uuid}")
    
    try:
        # Get image with prefetched related data
        image = Image.objects.prefetch_related(
            'repository_tags__repository__container_registry'
        ).get(uuid=image_uuid)
        
        # Check if already in process
        if image.scan_status == 'in_process':
            logger.warning(f"Image {image_uuid} is already being scanned")
            return {"status": "skipped", "reason": "already in process"}

        # Update status to in_process
        image.scan_status = 'in_process'
        image.save()
        
        # Get image reference
        image_ref = image.name or image.artifact_reference
        if not is_safe_image_ref(image_ref):
            logger.error(f"Unsafe image_ref: {image_ref}")
            image.scan_status = 'error'
            image.save()
            raise ValueError("Unsafe image reference")

        # Get registry token if available
        token = None
        if image.repository_tags.exists():
            registry = image.repository_tags.first().repository.container_registry
            if registry:
                token = get_bearer_token(registry.api_url, registry.login, registry.password)

        # Try to pull image
        try:
            logger.info(f"Pulling image {image_ref}")
            subprocess.run(["docker", "pull", image_ref], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            if token:
                # Try with registry authentication
                registry_host = image_ref.split('/')[0]
                logger.info(f"First pull failed, trying with registry authentication for {registry_host}")
                
                # Docker login
                login_process = subprocess.Popen(
                    ["docker", "login", registry_host, "-u", "00000000-0000-0000-0000-000000000000", "--password-stdin"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                _, stderr = login_process.communicate(input=token)
                
                if login_process.returncode != 0:
                    logger.error(f"Failed to login to registry {registry_host}: {stderr}")
                    image.scan_status = 'error'
                    image.save()
                    raise
                
                # Retry pull after login
                logger.info(f"Retrying pull for {image_ref}")
                subprocess.run(["docker", "pull", image_ref], capture_output=True, check=True)
            else:
                logger.error(f"Failed to pull image {image_ref} and no registry credentials available")
                image.scan_status = 'error'
                image.save()
                raise

        # Get image SHA if not already set
        if not image.digest:
            logger.info(f"Getting SHA for image {image_ref}")
            result = subprocess.run(
                ["docker", "inspect", image_ref],
                capture_output=True,
                check=True,
                text=True
            )
            inspect_data = json.loads(result.stdout)
            if inspect_data and len(inspect_data) > 0:
                repo_digests = inspect_data[0].get('RepoDigests', [])
                if repo_digests:
                    image.digest = repo_digests[0].split('@')[1]
                    image.save()
                    logger.info(f"Set image SHA to {image.digest}")

        # Generate SBOM
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_file_path = temp_file.name

        try:
            logger.info(f"Running Syft command for image {image_ref}")
            result = subprocess.run(
                ["syft", image_ref, "--output", f"json={temp_file_path}"],
                capture_output=True,
                check=True,
                text=True
            )

            # Read and save SBOM data
            with open(temp_file_path, 'r') as f:
                image.sbom_data = json.load(f)
            image.scan_status = 'success'
            image.save()
            
            logger.info(f"Successfully generated SBOM for image {image_uuid}")

            # Schedule SBOM parsing
            parse_sbom_and_create_components.delay(str(image_uuid))
            logger.info(f"Scheduled SBOM parsing for image {image_uuid}")

            return {
                "status": "success",
                "image_uuid": str(image_uuid),
                "image_name": image_ref,
                "digest": image.digest
            }

        finally:
            # Clean up
            try:
                logger.info(f"Removing image {image_ref}")
                subprocess.run(["docker", "rmi", image_ref], capture_output=True)
            except Exception as e:
                logger.warning(f"Failed to remove image {image_ref}: {str(e)}")
            
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error generating SBOM for image {image_uuid}: {str(e)}")
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
        except Exception:
            pass
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@celery_app.task()
def periodic_repository_scan():
    """
    Periodic task that scans all active repositories for new tags.
    This task should be scheduled to run daily.
    """
    from .models import Repository, RepositoryTag, ContainerRegistry
    from .utils.acr import get_tags, get_bearer_token, get_manifest, is_helm_chart
    from datetime import datetime

    logger.info("Starting periodic repository scan")
    results = []
    active_repositories = Repository.objects.filter(status=True)
    logger.info(f"Found {active_repositories.count()} active repositories")

    for repository in active_repositories:
        try:
            logger.info(f"Processing repository: {repository.name}")

            # Get registry and token
            registry = repository.container_registry
            if not registry:
                logger.warning(f"No registry found for repository {repository.name}, skipping")
                continue

            token = get_bearer_token(registry.api_url, registry.login, registry.password)

            # Get all tags from registry 
            all_tags = list(get_tags(registry.api_url, token, repository.name, limit=10))
            logger.info(f"Found {len(all_tags)} tags for repository {repository.name}")

            # Determine repository type if unknown
            if repository.repository_type in ('none', 'Unknown') and all_tags:
                first_tag = all_tags[0]
                manifest, _ = get_manifest(registry.api_url, token, repository.name, first_tag)
                if manifest:
                    if is_helm_chart(manifest):
                        repository.repository_type = 'helm'
                    else:
                        repository.repository_type = 'docker'
                    repository.save()

            tags_to_scan = all_tags[-10:] if all_tags else []
            logger.info(f"Found {len(tags_to_scan)} tags to scan for repository {repository.name}")

            # Get existing tags from database
            existing_tags = set(repository.tags.values_list('tag', flat=True))
            logger.info(f"Found {len(existing_tags)} existing tags in database for repository {repository.name}")

            # Find new tags
            new_tags = [tag for tag in tags_to_scan if tag not in existing_tags]
            logger.info(f"Found {len(new_tags)} new tags for repository {repository.name}")

            # Create new tags
            for tag in new_tags:
                RepositoryTag.objects.create(
                    repository=repository,
                    tag=tag
                )

            # Update repository last scanned timestamp
            repository.last_scanned = datetime.now()
            repository.save()

            results.append({
                "repository": repository.name,
                "status": "success",
                "new_tags": len(new_tags)
            })

        except Exception as e:
            logger.error(f"Error processing repository {repository.name}: {str(e)}")
            results.append({
                "repository": repository.name,
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "results": results
    }

@celery_app.task()
def scan_repository(repository_name: str, repository_url: str, scan_option: str):
    """
    Scan a repository for tags and determine its type (Helm or Docker).
    """
    from .models import Repository, RepositoryTag, ContainerRegistry
    from .utils.acr import get_tags, get_manifest, is_helm_chart, get_bearer_token
    from datetime import datetime

    logger.info(f"Starting repository scan for {repository_name}")

    try:
        # Get registry name from repository URL
        registry_name = repository_url.split('/')[0]
        try:
            registry = ContainerRegistry.objects.get(api_url__contains=registry_name)
        except ContainerRegistry.DoesNotExist:
            logger.warning(f"No ContainerRegistry found for {registry_name}, using default ACR")
            registry = ContainerRegistry.objects.get(provider='acr')

        # Get token for registry
        token = get_bearer_token(registry.api_url, registry.login, registry.password)

        # Get or create repository
        repository, created = Repository.objects.get_or_create(
            name=repository_name,
            defaults={
                'url': repository_url,
                'repository_type': 'docker',  # Default type
                'container_registry': registry,
                'status': True
            }
        )

        # If repository was not created, update its registry and status
        if not created:
            repository.container_registry = registry
            repository.status = True
            repository.save()

        # Get all tags
        all_tags = list(get_tags(registry.api_url, token, repository_name, limit=30))
        if scan_option == 'last':
            tags_to_scan = all_tags[-1:] if all_tags else []
        elif scan_option == 'last10':
            tags_to_scan = all_tags[-10:] if all_tags else []
        else:  # 'all'
            tags_to_scan = all_tags[-30:] if all_tags else []

        logger.info(f"Found {len(tags_to_scan)} tags to scan for repository {repository_name}")

        # Check repository type using the first tag
        if tags_to_scan:
            first_tag = tags_to_scan[0]
            manifest, _ = get_manifest(registry.api_url, token, repository_name, first_tag)
            if manifest and is_helm_chart(manifest):
                repository.repository_type = 'helm'
                repository.save()
                logger.info(f"Repository {repository_name} identified as Helm chart")

        # Create tags
        for tag_name in tags_to_scan:
            RepositoryTag.objects.get_or_create(
                tag=tag_name,
                repository=repository
            )

        repository.last_scanned = datetime.now()
        repository.save()
        logger.info(f"Successfully scanned repository {repository_name}")

    except Exception as e:
        logger.error(f"Error scanning repository {repository_name}: {str(e)}")
        if repository:
            repository.status = False
            repository.save()
        raise

@celery_app.task()
def process_all_tags():
    """
    Process all tags from active repositories and create images if they don't exist.
    This task can be manually triggered.
    """
    from .models import Repository, RepositoryTag, Image
    from .utils.acr import get_manifest, is_helm_chart, get_chart_digest, get_helm_images, get_bearer_token

    logger.info("Starting processing of all tags from active repositories")

    results = []
    active_repositories = Repository.objects.filter(status=True)
    logger.info(f"Found {active_repositories.count()} active repositories")

    for repository in active_repositories:
        try:
            logger.info(f"Processing repository: {repository.name}")
            repository_tags = RepositoryTag.objects.filter(repository=repository)
            logger.info(f"Found {repository_tags.count()} tags for repository {repository.name}")

            # Get registry token if available
            token = None
            if repository.container_registry:
                token = get_bearer_token(
                    repository.container_registry.api_url,
                    repository.container_registry.login,
                    repository.container_registry.password
                )

            processed_tags = []
            for repo_tag in repository_tags:
                # For Docker images, just create the record
                if repository.repository_type == 'docker':
                    image_ref = f"{repository.url}:{repo_tag.tag}"
                    image, created = Image.objects.get_or_create(
                        name=image_ref,
                        defaults={
                            'artifact_reference': image_ref
                        }
                    )
                    image.repository_tags.add(repo_tag)
                    logger.info(f"{'Created' if created else 'Linked'} Docker image {image_ref}")
                else:
                    # For Helm charts, get manifest to extract images and digest
                    manifest, digest = get_manifest(
                        repository.container_registry.api_url if repository.container_registry else None,
                        token,
                        repository.name,
                        repo_tag.tag
                    )

                    if not manifest:
                        logger.warning(f"Could not get manifest for {repository.name}:{repo_tag.tag}")
                        continue

                    if is_helm_chart(manifest):
                        chart_digest = get_chart_digest(manifest)
                        if chart_digest:
                            for image_ref in get_helm_images(
                                repository.container_registry.api_url if repository.container_registry else None,
                                token,
                                repository.name,
                                chart_digest
                            ):
                                # Create or get image with digest from manifest
                                image, created = Image.objects.get_or_create(
                                    name=image_ref,
                                    defaults={
                                        'digest': digest,  # Save digest from manifest
                                        'artifact_reference': f"{repository.url}:{repo_tag.tag}"
                                    }
                                )
                                image.repository_tags.add(repo_tag)
                                logger.info(f"{'Created' if created else 'Linked'} Helm image {image_ref} with digest {digest}")

                processed_tags.append(repo_tag.tag)

            results.append({
                "repository": repository.name,
                "status": "success",
                "tags_processed": len(processed_tags)
            })

        except Exception as e:
            logger.error(f"Error processing repository {repository.name}: {str(e)}")
            results.append({
                "repository": repository.name,
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "completed",
        "results": results
    }

@celery_app.task()
def parse_sbom_and_create_components(image_uuid: str):
    """
    Parse SBOM data from an image and create corresponding components and component versions.
    This task should be called after SBOM generation is complete.
    """
    from .models import Image, Component, ComponentVersion
    from django.db import transaction
    from django.db.models import Q
    from collections import defaultdict
    import time

    logger.info(f"Starting SBOM parsing for image {image_uuid}")
    start_time = time.time()

    try:
        # Get image with prefetched related data
        image = Image.objects.select_related().get(uuid=image_uuid)
        logger.info(f"Found image: {image.name} (digest: {image.digest})")
        
        if not image.sbom_data:
            logger.warning(f"No SBOM data found for image {image_uuid}")
            return {
                "status": "error",
                "error": "No SBOM data found"
            }

        if image.scan_status != 'success':
            logger.warning(f"Image {image_uuid} scan status is not success: {image.scan_status}")
            return {
                "status": "error",
                "error": f"Image scan status is {image.scan_status}"
            }

        # Process artifacts in batches
        BATCH_SIZE = 1000
        components_created = 0
        versions_created = 0
        components_updated = 0
        artifacts = image.sbom_data.get('artifacts', [])
        total_artifacts = len(artifacts)

        logger.info(f"Found {total_artifacts} artifacts in SBOM")
        logger.info(f"Processing artifacts in batches of {BATCH_SIZE}")

        # Process artifacts in batches
        for i in range(0, total_artifacts, BATCH_SIZE):
            batch_start_time = time.time()
            batch = artifacts[i:i + BATCH_SIZE]
            current_batch = i//BATCH_SIZE + 1
            total_batches = (total_artifacts + BATCH_SIZE - 1)//BATCH_SIZE
            
            logger.info(f"Processing batch {current_batch}/{total_batches} ({len(batch)} artifacts)")
            
            # Collect unique component names and versions
            component_data = {}
            skipped_artifacts = 0
            for artifact in batch:
                name = artifact.get('name')
                version = artifact.get('version')
                type = artifact.get('type', 'unknown')
                purl = artifact.get('purl')
                cpes = artifact.get('cpes', [])

                if not name or not version:
                    skipped_artifacts += 1
                    continue

                if name not in component_data:
                    component_data[name] = {
                        'name': name,
                        'type': type,
                        'versions': {},
                        'purl': purl
                    }

                component_data[name]['versions'][version] = {
                    'purl': purl,
                    'cpes': cpes
                }

            if skipped_artifacts:
                logger.warning(f"Skipped {skipped_artifacts} artifacts in batch {current_batch} due to missing name or version")

            logger.info(f"Found {len(component_data)} unique components in batch {current_batch}")

            # Get existing components
            existing_components = {
                c.name: c for c in Component.objects.filter(
                    name__in=component_data.keys()
                )
            }
            logger.info(f"Found {len(existing_components)} existing components in batch {current_batch}")

            # Get existing component versions
            existing_versions = {
                f"{cv.component.name}:{cv.version}": cv 
                for cv in ComponentVersion.objects.filter(
                    component__name__in=component_data.keys()
                ).select_related('component')
            }
            logger.info(f"Found {len(existing_versions)} existing component versions in batch {current_batch}")

            # Initialize lists for bulk operations
            components_to_create = []
            components_to_update = []
            component_versions_to_create = []
            component_versions_to_update = []

            # Prepare components for creation/update
            for name, data in component_data.items():
                if name in existing_components:
                    component = existing_components[name]
                    # Update component if needed
                    if data['type'] != 'unknown' and component.type == 'unknown':
                        component.type = data['type']
                        components_to_update.append(component)
                else:
                    # Create new component
                    components_to_create.append(Component(
                        name=name,
                        type=data['type']
                    ))

            logger.info(f"Prepared {len(components_to_create)} components for creation and {len(components_to_update)} for update in batch {current_batch}")

            # Bulk create/update components
            with transaction.atomic():
                if components_to_create:
                    created_components = Component.objects.bulk_create(components_to_create)
                    components_created += len(created_components)
                    logger.info(f"Created {len(created_components)} new components in batch {current_batch}")
                    # Add new components to existing_components dict
                    existing_components.update({c.name: c for c in created_components})

                if components_to_update:
                    Component.objects.bulk_update(
                        components_to_update,
                        ['type']
                    )
                    components_updated += len(components_to_update)
                    logger.info(f"Updated {len(components_to_update)} existing components in batch {current_batch}")

                # Prepare component versions
                for name, data in component_data.items():
                    component = existing_components[name]
                    for version, version_data in data['versions'].items():
                        version_key = f"{name}:{version}"
                        if version_key not in existing_versions:
                            component_versions_to_create.append(ComponentVersion(
                                component=component,
                                version=version,
                                purl=version_data['purl'],
                                cpes=version_data['cpes']
                            ))
                        else:
                            # Update existing version if purl or cpes are missing
                            version_obj = existing_versions[version_key]
                            if (version_data['purl'] and not version_obj.purl) or \
                               (version_data['cpes'] and not version_obj.cpes):
                                version_obj.purl = version_data['purl'] or version_obj.purl
                                version_obj.cpes = version_data['cpes'] or version_obj.cpes
                                component_versions_to_update.append(version_obj)

                logger.info(f"Prepared {len(component_versions_to_create)} component versions for creation in batch {current_batch}")

                # Bulk create component versions
                if component_versions_to_create:
                    created_versions = ComponentVersion.objects.bulk_create(component_versions_to_create)
                    versions_created += len(created_versions)
                    logger.info(f"Created {len(created_versions)} new component versions in batch {current_batch}")
                    # Add new versions to existing_versions dict
                    existing_versions.update({
                        f"{cv.component.name}:{cv.version}": cv 
                        for cv in created_versions
                    })

                # Link image to component versions
                image_versions = image.component_versions.all()
                links_created = 0
                for name, data in component_data.items():
                    component = existing_components[name]
                    for version, version_data in data['versions'].items():
                        version_key = f"{name}:{version}"
                        version_obj = existing_versions[version_key]
                        if version_obj not in image_versions:
                            version_obj.images.add(image)
                            links_created += 1

            batch_time = time.time() - batch_start_time
            logger.info(f"Completed batch {current_batch}/{total_batches} in {batch_time:.2f} seconds")

        total_time = time.time() - start_time
        logger.info(f"SBOM parsing completed in {total_time:.2f} seconds")
        logger.info(f"Summary:")
        logger.info(f"- Total artifacts processed: {total_artifacts}")
        logger.info(f"- Components created: {components_created}")
        logger.info(f"- Components updated: {components_updated}")
        logger.info(f"- Component versions created: {versions_created}")

        # Schedule Grype scan after successful SBOM processing
        scan_image_with_grype.delay(str(image_uuid))
        logger.info(f"Scheduled Grype scan for image {image_uuid}")

        return {
            "status": "success",
            "image_uuid": str(image_uuid),
            "components_created": components_created,
            "components_updated": components_updated,
            "versions_created": versions_created,
            "processing_time": total_time
        }

    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error parsing SBOM for image {image_uuid}: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task()
def update_components_latest_versions(image_uuid: str):
    """
    Update latest versions for all component versions in an image.
    This task can be triggered manually through the API.
    """
    from .models import Image, ComponentVersion
    import time
    import requests
    import subprocess
    from packaging.version import parse as parse_version

    logger.info(f"Starting latest versions update for image {image_uuid}")
    start_time = time.time()

    try:
        image = Image.objects.prefetch_related('component_versions').get(uuid=image_uuid)
        component_versions = image.component_versions.all()
        logger.info(f"Found {component_versions.count()} component versions to process")
        updated_count = 0
        for component_version in component_versions:
            try:
                now = timezone.now()
                # Skip update if already updated within the last 4 days
                if (
                    component_version.latest_version_updated_at and
                    (now - component_version.latest_version_updated_at).days <= 4
                ):
                    logger.info(
                        f"Skipped update for {component_version.component.name}:{component_version.version} (last updated {component_version.latest_version_updated_at})"
                    )
                    continue
                if not component_version.purl:
                    logger.debug(f"No PURL found for component version {component_version.component.name}:{component_version.version}")
                    continue
                logger.debug(f"Processing component version {component_version.component.name}:{component_version.version}")
                parts = component_version.purl.split("/")
                if len(parts) < 2:
                    continue
                package_type = parts[0].split(":")[1] if ":" in parts[0] else None
                if not package_type:
                    continue
                package_name = parts[1].lower()
                if len(parts) > 2:
                    package_name = f"{package_name}/{parts[2].lower()}"
                if "@" in package_name:
                    package_name = package_name.split("@")[0]
                logger.debug(f"Processing PURL: {component_version.purl}")
                logger.debug(f"Package type: {package_type}, Package name: {package_name}")
                latest_version = None
                if package_type == "pypi":
                    url = f"https://pypi.org/pypi/{package_name}/json"
                    r = requests.get(url, timeout=5)
                    if r.ok:
                        latest_version = r.json()["info"]["version"]
                elif package_type == "npm":
                    url = f"https://registry.npmjs.org/{package_name}"
                    r = requests.get(url, timeout=5)
                    if r.ok:
                        latest_version = r.json()["dist-tags"]["latest"]
                elif package_type == "nuget":
                    url = f"https://api.nuget.org/v3-flatcontainer/{package_name}/index.json"
                    r = requests.get(url, timeout=5)
                    if r.ok:
                        versions = r.json().get("versions", [])
                        latest_version = versions[-1] if versions else None
                elif package_type == "deb":
                    try:
                        output = subprocess.check_output(["apt-cache", "policy", package_name], text=True, timeout=5)
                        for line in output.splitlines():
                            if "Candidate:" in line:
                                latest_version = line.split(":")[1].strip()
                                break
                    except Exception:
                        continue
                elif package_type == "golang":
                    if package_name == "stdlib":
                        url = "https://golang.org/dl/?mode=json"
                        r = requests.get(url, timeout=5)
                        if r.ok:
                            versions = r.json()
                            stable_versions = [v['version'] for v in versions if not v['version'].endswith('beta') and not v['version'].endswith('rc')]
                            if stable_versions:
                                latest_version = max(stable_versions).replace('go', '')
                    else:
                        url = f"https://proxy.golang.org/{package_name}/@latest"
                        r = requests.get(url, timeout=5)
                        if r.ok:
                            data = r.json()
                            latest_version = data.get('Version', '').replace('v', '')
                if latest_version:
                    component_version.latest_version = latest_version
                    component_version.latest_version_updated_at = now
                    component_version.save()
                    updated_count += 1
                    logger.info(
                        f"Updated latest version for {component_version.component.name}:{component_version.version} to {latest_version} (updated_at={now})"
                    )
            except Exception as e:
                logger.warning(
                    f"Error processing component version {component_version.component.name}:{component_version.version}: {str(e)}"
                )
                continue
        total_time = time.time() - start_time
        logger.info(f"Latest versions update completed in {total_time:.2f} seconds")
        logger.info(f"Updated latest versions for {updated_count} component versions")
        return {
            "status": "success",
            "image_uuid": str(image_uuid),
            "component_versions_updated": updated_count,
            "processing_time": total_time
        }
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error updating latest versions for image {image_uuid}: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task()
def process_grype_scan_results(image_uuid: str, scan_results: dict):
    """
    Process Grype scan results for an image and update the database with vulnerability information.
    
    This function:
    1. Creates new vulnerabilities if they don't exist
    2. Updates existing vulnerabilities if they already exist
    3. Links vulnerabilities to component versions through ComponentVersionVulnerability
    4. Links component versions to images
    
    A vulnerability can be linked to multiple component versions,
    and a component version can have multiple vulnerabilities.
    
    Args:
        image_uuid (str): UUID of the Image to process
        scan_results (dict): Grype scan results in JSON format
    """
    from .models import Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Processing Grype scan results for image {image_uuid}")

    try:
        # Get the image
        image = Image.objects.get(uuid=image_uuid)
        
        # Process each match (vulnerability) in the scan results
        for match in scan_results.get('matches', []):
            # Extract vulnerability information
            vulnerability_data = match.get('vulnerability', {})
            vuln_id = vulnerability_data.get('id', '')
            severity = vulnerability_data.get('severity', 'UNKNOWN').upper()
            description = vulnerability_data.get('description', '')
            
            # Determine vulnerability type from ID
            vuln_type = 'CVE'  # Default type
            if vuln_id.startswith('GHSA-'):
                vuln_type = 'GHSA'
            elif vuln_id.startswith('RUSTSEC-'):
                vuln_type = 'RUSTSEC'
            elif vuln_id.startswith('PYSEC-'):
                vuln_type = 'PYSEC'
            elif vuln_id.startswith('NPM-'):
                vuln_type = 'NPM'
            # Add more vulnerability types as needed
            
            # Extract EPSS score - handle both old and new format
            epss_score = 0.0
            epss_data = vulnerability_data.get('epss', [])
            if isinstance(epss_data, list) and epss_data:
                # New format: list of EPSS data
                epss_score = epss_data[0].get('epss', 0.0)
            elif isinstance(epss_data, (int, float)):
                # Old format: direct number
                epss_score = float(epss_data)
            
            # Extract fix info from Grype report
            fix_data = vulnerability_data.get('fix', {})
            fix_versions = fix_data.get('versions', []) if isinstance(fix_data, dict) else []
            fix_state = fix_data.get('state', '') if isinstance(fix_data, dict) else ''
            # fixable is True if there are fix versions, or state is present and not 'wont-fix'/'not-fixed' (case-insensitive)
            fixable = bool(fix_versions) or (bool(fix_state) and fix_state.lower() not in ['wont-fix', 'not-fixed', ''])
            fixable = bool(fixable)  # Ensure only True/False
            fix_str = ', '.join(fix_versions) if fix_versions else (fix_state or '')
            
            # Get or create vulnerability using the new field names
            vulnerability, created = Vulnerability.objects.get_or_create(
                vulnerability_id=vuln_id,
                defaults={
                    'vulnerability_type': vuln_type,
                    'severity': severity,
                    'description': description,
                    'epss': epss_score
                }
            )
            
            # Update vulnerability if it already existed
            if not created:
                vulnerability.severity = severity
                vulnerability.description = description
                vulnerability.epss = epss_score
                vulnerability.save()
                # logger.info(f"Updated existing vulnerability {vuln_id}")
            else:
                logger.info(f"Created new vulnerability {vuln_id} of type {vuln_type}")
            
            # Get the affected component information
            artifact = match.get('artifact', {})
            component_name = artifact.get('name')
            component_type = artifact.get('type', 'unknown')
            component_version = artifact.get('version')
            purl = artifact.get('purl')
            
            if component_name and component_version:
                # Get or create component
                component, component_created = Component.objects.get_or_create(
                    name=component_name,
                    defaults={
                        'type': component_type
                    }
                )
                
                if component_created:
                    logger.info(f"Created new component {component_name}")
                
                # Get or create component version
                component_version_obj, version_created = ComponentVersion.objects.get_or_create(
                    version=component_version,
                    component=component,
                    defaults={
                        'purl': purl,
                        'cpes': artifact.get('cpes', [])
                    }
                )
                
                if version_created:
                    logger.info(f"Created new version {component_version} for component {component_name}")
                else:
                    # Update purl and cpes if they are missing
                    if (purl and not component_version_obj.purl) or \
                       (artifact.get('cpes') and not component_version_obj.cpes):
                        component_version_obj.purl = purl or component_version_obj.purl
                        component_version_obj.cpes = artifact.get('cpes', []) or component_version_obj.cpes
                        component_version_obj.save()
                        logger.info(f"Updated purl/cpes for version {component_version} of component {component_name}")
                
                # Link component version to image if not already linked
                if image not in component_version_obj.images.all():
                    component_version_obj.images.add(image)
                    logger.info(f"Linked component version {component_version} to image {image.name}")
                
                # Create or update the through model relationship with fix information
                cvv, cvv_created = ComponentVersionVulnerability.objects.get_or_create(
                    component_version=component_version_obj,
                    vulnerability=vulnerability,
                    defaults={
                        'fixable': fixable,
                        'fix': fix_str
                    }
                )
                
                if not cvv_created:
                    # Update fix information if it already existed
                    cvv.fixable = fixable
                    cvv.fix = fix_str
                    cvv.save()
                
        # Update image scan status
        image.scan_status = 'success'
        image.save()
        
        logger.info(f"Successfully processed Grype scan results for image {image_uuid}")
        return {
            "status": "success",
            "image_uuid": str(image_uuid),
            "vulnerabilities_processed": len(scan_results.get('matches', []))
        }
        
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error processing Grype scan results for image {image_uuid}: {str(e)}")
        if image:
            image.scan_status = 'error'
            image.save()
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task(bind=True, max_retries=1)
def scan_image_with_grype(self, image_uuid: str):
    """
    Scan an image's SBOM with Grype and save the results.
    This task should be called after SBOM generation is complete.
    
    Args:
        image_uuid (str): UUID of the Image to scan
    """
    from .models import Image
    import subprocess
    import json
    import tempfile
    import os

    logger.info(f"Starting Grype scan for image {image_uuid}")
    
    try:
        # Get image
        image = Image.objects.get(uuid=image_uuid)
        
        # Check if already in process
        if image.scan_status == 'in_process':
            logger.warning(f"Image {image_uuid} is already being scanned")
            return {"status": "skipped", "reason": "already in process"}

        # Check if we have SBOM data
        if not image.sbom_data:
            logger.error(f"No SBOM data found for image {image_uuid}")
            image.scan_status = 'error'
            image.save()
            return {
                "status": "error",
                "error": "No SBOM data found"
            }

        # Update status to in_process
        image.scan_status = 'in_process'
        image.save()

        # Create temporary files for SBOM and Grype results
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as sbom_file, \
             tempfile.NamedTemporaryFile(suffix='.json', delete=False) as grype_file:
            sbom_file_path = sbom_file.name
            grype_file_path = grype_file.name

        try:
            # Save SBOM data to temporary file
            with open(sbom_file_path, 'w') as f:
                json.dump(image.sbom_data, f)

            # Run Grype scan on SBOM file
            logger.info(f"Running Grype scan on SBOM for image {image_uuid}")
            result = subprocess.run(
                ["grype", f"sbom:{sbom_file_path}", "--output", "json", "--file", grype_file_path],
                capture_output=True,
                check=True,
                text=True
            )

            # Read Grype results
            with open(grype_file_path, 'r') as f:
                grype_results = json.load(f)

            # Save Grype results to image
            image.grype_data = grype_results
            image.save()
            logger.info(f"Saved Grype results for image {image_uuid}")

            # Process Grype results
            process_grype_scan_results.delay(str(image_uuid), grype_results)
            
            logger.info(f"Successfully scanned image {image_uuid} with Grype")
            return {
                "status": "success",
                "image_uuid": str(image_uuid)
            }

        finally:
            # Clean up temporary files
            for file_path in [sbom_file_path, grype_file_path]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error scanning image {image_uuid} with Grype: {str(e)}")
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
        except Exception:
            pass
        self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

@celery_app.task()
def scan_repository_tags(repository_uuid: str):
    """
    Task that scans a single repository for new tags.
    """
    from .models import Repository, RepositoryTag, ContainerRegistry
    from .utils.acr import get_tags, get_bearer_token, get_manifest, is_helm_chart
    from datetime import datetime

    logger.info(f"Starting repository tags scan for repository {repository_uuid}")
    
    try:
        repository = Repository.objects.get(uuid=repository_uuid)
        
        # Update status to in_process
        repository.scan_status = 'in_process'
        repository.save()

        # Get registry and token
        registry = repository.container_registry
        if not registry:
            logger.warning(f"No registry found for repository {repository.name}")
            repository.scan_status = 'error'
            repository.save()
            return

        token = get_bearer_token(registry.api_url, registry.login, registry.password)

        # Get all tags from registry 
        all_tags = list(get_tags(registry.api_url, token, repository.name, limit=10))
        logger.info(f"Found {len(all_tags)} tags for repository {repository.name}")

        # Determine repository type if unknown
        if repository.repository_type in ('none', 'Unknown') and all_tags:
            first_tag = all_tags[0]
            manifest, _ = get_manifest(registry.api_url, token, repository.name, first_tag)
            if manifest:
                if is_helm_chart(manifest):
                    repository.repository_type = 'helm'
                else:
                    repository.repository_type = 'docker'
                repository.save()

        # Process each tag
        for tag_name in all_tags:
            try:
                # Check if tag already exists
                if not RepositoryTag.objects.filter(repository=repository, tag=tag_name).exists():
                    # Get manifest for the tag
                    manifest, digest = get_manifest(registry.api_url, token, repository.name, tag_name)
                    if digest:
                        digest = digest.replace('sha256:', '')
                    else:
                        digest = ''
                    # Create new tag
                    RepositoryTag.objects.create(
                        repository=repository,
                        tag=tag_name,
                        digest=digest
                    )
                    logger.info(f"Created new tag {tag_name} for repository {repository.name}")
            except Exception as e:
                logger.error(f"Error processing tag {tag_name} for repository {repository.name}: {str(e)}")
                continue

        # Update repository status
        repository.scan_status = 'success'
        repository.last_scanned = datetime.now()
        repository.save()
        logger.info(f"Successfully completed repository tags scan for {repository.name}")

    except Repository.DoesNotExist:
        logger.error(f"Repository with UUID {repository_uuid} not found")
    except Exception as e:
        logger.error(f"Error scanning repository {repository_uuid}: {str(e)}")
        try:
            repository = Repository.objects.get(uuid=repository_uuid)
            repository.scan_status = 'error'
            repository.save()
        except Exception:
            pass

@celery_app.task()
def process_single_tag(tag_uuid: str):
    """
    Process a single repository tag and create an image if it doesn't exist.
    """
    from .models import RepositoryTag, Image
    from .utils.acr import get_manifest, is_helm_chart, get_chart_digest, get_helm_images, get_bearer_token

    logger.info(f"Starting processing of tag {tag_uuid}")

    try:
        tag = RepositoryTag.objects.select_related('repository', 'repository__container_registry').get(uuid=tag_uuid)
        # Set status to in_process
        tag.processing_status = 'in_process'
        tag.save()
        repository = tag.repository
        logger.info(f"Processing tag {tag.tag} from repository {repository.name}")

        # Get registry token if available
        token = None
        if repository.container_registry:
            token = get_bearer_token(
                repository.container_registry.api_url,
                repository.container_registry.login,
                repository.container_registry.password
            )

        # For Docker images, just create the record
        if repository.repository_type == 'docker':
            image_ref = f"{repository.url}:{tag.tag}"
            image, created = Image.objects.get_or_create(
                name=image_ref,
                defaults={
                    'artifact_reference': image_ref
                }
            )
            image.repository_tags.add(tag)
            logger.info(f"{'Created' if created else 'Linked'} Docker image {image_ref}")
        else:
            # For Helm charts, get manifest to extract images and digest
            manifest, digest = get_manifest(
                repository.container_registry.api_url if repository.container_registry else None,
                token,
                repository.name,
                tag.tag
            )

            if not manifest:
                logger.warning(f"Could not get manifest for {repository.name}:{tag.tag}")
                tag.processing_status = 'error'
                tag.save()
                return

            if is_helm_chart(manifest):
                chart_digest = get_chart_digest(manifest)
                if chart_digest:
                    for image_ref in get_helm_images(
                        repository.container_registry.api_url if repository.container_registry else None,
                        token,
                        repository.name,
                        chart_digest
                    ):
                        # Create or get image with digest from manifest
                        image, created = Image.objects.get_or_create(
                            name=image_ref,
                            defaults={
                                'digest': digest,  # Save digest from manifest
                                'artifact_reference': f"{repository.url}:{tag.tag}"
                            }
                        )
                        image.repository_tags.add(tag)
                        logger.info(f"{'Created' if created else 'Linked'} Helm image {image_ref} with digest {digest}")

        # Set status to success
        tag.processing_status = 'success'
        tag.save()

        return {
            "status": "success",
            "tag_uuid": str(tag_uuid),
            "repository": repository.name,
            "tag": tag.tag
        }

    except RepositoryTag.DoesNotExist:
        logger.error(f"Tag with UUID {tag_uuid} not found")
        return {
            "status": "error",
            "error": f"Tag with UUID {tag_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error processing tag {tag_uuid}: {str(e)}")
        try:
            tag = RepositoryTag.objects.get(uuid=tag_uuid)
            tag.processing_status = 'error'
            tag.save()
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task()
def delete_old_repository_tags(days: int = 1):
    """
    Delete all RepositoryTag objects older than `days` days.
    """
    from .models import RepositoryTag
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = RepositoryTag.objects.filter(created_at__lt=cutoff).delete()
    return f"Deleted {deleted_count} old repository tags older than {days} days"
