from __future__ import absolute_import, unicode_literals

from hitrack_celery.celery import celery_app
import logging
import re
from datetime import timedelta
from django.utils import timezone
from typing import List, Dict
from django.db import transaction
import time

# Configure logging
logger = logging.getLogger(__name__)

DOCKER_IMAGE_REGEX = re.compile(r'^[a-zA-Z0-9._/-]+(:[a-zA-Z0-9._-]+)?$')

def is_safe_image_ref(image_ref: str) -> bool:
    return bool(DOCKER_IMAGE_REGEX.match(image_ref)) and len(image_ref) < 200

@celery_app.task(bind=True, max_retries=1, name="Generate SBOM and Create Components")
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
    from .utils.acr import get_bearer_token, get_acr_image_digest

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

@celery_app.task(name="Periodic Repository Scan")
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

@celery_app.task(name="Scan Repository")
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
        
        return {
            "status": "success",
            "message": f"Successfully scanned repository {repository_name}",
            "task_name": "Scan Repository",
            "repository_name": repository_name,
            "tags_processed": len(tags_to_scan)
        }

    except Exception as e:
        logger.error(f"Error scanning repository {repository_name}: {str(e)}")
        if repository:
            repository.status = False
            repository.save()
        raise

@celery_app.task(name="Process All Tags")
def process_all_tags():
    """
    Process all tags from active repositories and create images if they don't exist.
    This task can be manually triggered.
    """
    from .models import Repository, RepositoryTag, Image
    from .utils.acr import get_manifest, is_helm_chart, get_chart_digest, get_helm_images, get_bearer_token, get_acr_image_digest

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
                                # Get image digest from ACR
                                image_digest = None
                                if repository.container_registry and repository.container_registry.provider == 'acr':
                                    image_digest = get_acr_image_digest(
                                        repository.container_registry.api_url,
                                        token,
                                        image_ref
                                    )
                                
                                # Create or get image with proper digest
                                image, created = Image.objects.get_or_create(
                                    name=image_ref,
                                    defaults={
                                        'digest': image_digest,  # Use actual image digest
                                        'artifact_reference': f"{repository.url}:{repo_tag.tag}"
                                    }
                                )
                                image.repository_tags.add(repo_tag)
                                logger.info(f"{'Created' if created else 'Linked'} Helm image {image_ref} with digest {image_digest}")

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
        "task_name": "Process All Tags",
        "results": results
    }

@celery_app.task(name="Parse SBOM and Create Components")
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
            "task_name": "Parse SBOM and Create Components",
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

@celery_app.task(name="Update Components Latest Versions")
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
            "task_name": "Update Components Latest Versions",
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

@celery_app.task(name="Process Grype Scan Results")
def process_grype_scan_results(image_uuid: str, scan_results: dict):
    """
    Process Grype scan results for an image and update the database with vulnerability information.
    Optimized for bulk operations and safe parallel execution.
    """
    from .models import Image, Component, ComponentVersion, Vulnerability, ComponentVersionVulnerability, VulnerabilityDetails, ComponentLocation
    from django.db import IntegrityError
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"Processing Grype scan results for image {image_uuid}")

    try:
        image = Image.objects.get(uuid=image_uuid)
        matches = scan_results.get('matches', [])

        # Collect unique names/versions/ids
        component_names = set()
        component_versions_set = set()
        vuln_ids = set()
        for match in matches:
            artifact = match.get('artifact', {})
            component_name = artifact.get('name')
            component_version = artifact.get('version')
            if component_name:
                component_names.add(component_name)
            if component_name and component_version:
                component_versions_set.add((component_name, component_version))
            vulnerability_data = match.get('vulnerability', {})
            vuln_id = vulnerability_data.get('id', '')
            if vuln_id:
                vuln_ids.add(vuln_id)

        # Bulk create Components
        existing_components = {c.name: c for c in Component.objects.filter(name__in=component_names)}
        new_components = [Component(name=name) for name in component_names if name not in existing_components]
        Component.objects.bulk_create(new_components, ignore_conflicts=True)
        # Refresh cache
        existing_components = {c.name: c for c in Component.objects.filter(name__in=component_names)}

        # Bulk create Vulnerabilities
        existing_vulns = {v.vulnerability_id: v for v in Vulnerability.objects.filter(vulnerability_id__in=vuln_ids)}
        new_vulns = [Vulnerability(vulnerability_id=vid) for vid in vuln_ids if vid not in existing_vulns]
        Vulnerability.objects.bulk_create(new_vulns, ignore_conflicts=True)
        existing_vulns = {v.vulnerability_id: v for v in Vulnerability.objects.filter(vulnerability_id__in=vuln_ids)}

        # Bulk create ComponentVersions
        existing_versions = {(cv.component.name, cv.version): cv for cv in ComponentVersion.objects.filter(
            component__name__in=component_names,
            version__in=[v for _, v in component_versions_set]
        ).select_related('component')}
        new_versions = [
            ComponentVersion(component=existing_components[name], version=version)
            for (name, version) in component_versions_set if (name, version) not in existing_versions
        ]
        ComponentVersion.objects.bulk_create(new_versions, ignore_conflicts=True)
        existing_versions = {(cv.component.name, cv.version): cv for cv in ComponentVersion.objects.filter(
            component__name__in=component_names,
            version__in=[v for _, v in component_versions_set]
        ).select_related('component')}

        # Process each match
        for match in matches:
            vulnerability_data = match.get('vulnerability', {})
            vuln_id = vulnerability_data.get('id', '')
            severity = vulnerability_data.get('severity', 'UNKNOWN').upper()
            description = vulnerability_data.get('description', '')
            vuln_type = 'CVE'
            if vuln_id.startswith('GHSA-'):
                vuln_type = 'GHSA'
            elif vuln_id.startswith('RUSTSEC-'):
                vuln_type = 'RUSTSEC'
            elif vuln_id.startswith('PYSEC-'):
                vuln_type = 'PYSEC'
            elif vuln_id.startswith('NPM-'):
                vuln_type = 'NPM'
            epss_score = 0.0
            epss_data = vulnerability_data.get('epss', [])
            if isinstance(epss_data, list) and epss_data:
                epss_score = epss_data[0].get('epss', 0.0)
            elif isinstance(epss_data, (int, float)):
                epss_score = float(epss_data)
            fix_data = vulnerability_data.get('fix', {})
            fix_versions = fix_data.get('versions', []) if isinstance(fix_data, dict) else []
            fix_state = fix_data.get('state', '') if isinstance(fix_data, dict) else ''
            fixable = bool(fix_versions) or (bool(fix_state) and fix_state.lower() not in ['wont-fix', 'not-fixed', ''])
            fixable = bool(fixable)
            fix_str = ', '.join(fix_versions) if fix_versions else (fix_state or '')

            # Get or create vulnerability (safe for parallel)
            vulnerability, _ = Vulnerability.objects.get_or_create(
                vulnerability_id=vuln_id,
                defaults={
                    'vulnerability_type': vuln_type,
                    'severity': severity,
                    'description': description,
                    'epss': epss_score
                }
            )
            # Update fields if needed
            updated = False
            if vulnerability.severity != severity:
                vulnerability.severity = severity
                updated = True
            if vulnerability.description != description:
                vulnerability.description = description
                updated = True
            if vulnerability.epss != epss_score:
                vulnerability.epss = epss_score
                updated = True
            if updated:
                vulnerability.save()

            artifact = match.get('artifact', {})
            component_name = artifact.get('name')
            component_type = artifact.get('type', 'unknown')
            component_version = artifact.get('version')
            purl = artifact.get('purl')
            cpes = artifact.get('cpes', [])
            locations = artifact.get('locations', [])

            if component_name and component_version:
                # Get or create component (safe for parallel)
                component, _ = Component.objects.get_or_create(
                    name=component_name,
                    defaults={'type': component_type}
                )
                # Update type if needed
                if component.type == 'unknown' and component_type != 'unknown':
                    component.type = component_type
                    component.save()
                # Get or create component version (safe for parallel)
                component_version_obj, _ = ComponentVersion.objects.get_or_create(
                    version=component_version,
                    component=component,
                    defaults={'purl': purl, 'cpes': cpes}
                )
                # Update purl/cpes if needed
                updated = False
                if purl and not component_version_obj.purl:
                    component_version_obj.purl = purl
                    updated = True
                if cpes and not component_version_obj.cpes:
                    component_version_obj.cpes = cpes
                    updated = True
                if updated:
                    component_version_obj.save()
                # Link image to component version
                if not component_version_obj.images.filter(pk=image.pk).exists():
                    component_version_obj.images.add(image)
                    logger.info(f"Linked component version {component_version} to image {image.name}")
                
                # Process component locations
                for location in locations:
                    path = location.get('path', '')
                    layer_id = location.get('layerID', '')
                    access_path = location.get('accessPath', '')
                    annotations = location.get('annotations', {})
                    
                    # Determine evidence type from annotations
                    evidence_type = 'unknown'
                    if annotations:
                        evidence = annotations.get('evidence', '')
                        if evidence == 'primary':
                            evidence_type = 'primary'
                        elif evidence == 'supporting':
                            evidence_type = 'supporting'
                    
                    # Create or update component location
                    ComponentLocation.objects.get_or_create(
                        component_version=component_version_obj,
                        image=image,
                        path=path,
                        defaults={
                            'layer_id': layer_id,
                            'access_path': access_path,
                            'evidence_type': evidence_type,
                            'annotations': annotations
                        }
                    )
                
                # Get or create CVV (safe for parallel)
                cvv, _ = ComponentVersionVulnerability.objects.get_or_create(
                    component_version=component_version_obj,
                    vulnerability=vulnerability,
                    defaults={'fixable': fixable, 'fix': fix_str}
                )
                # Update fix info if needed
                if not _:
                    updated = False
                    if cvv.fixable != fixable:
                        cvv.fixable = fixable
                        updated = True
                    if cvv.fix != fix_str:
                        cvv.fix = fix_str
                        updated = True
                    if updated:
                        cvv.save()

        image.scan_status = 'success'
        image.save()
        logger.info(f"Successfully processed Grype scan results for image {image_uuid}")
        return {
            "status": "success",
            "task_name": "Process Grype Scan Results",
            "image_uuid": str(image_uuid),
            "vulnerabilities_processed": len(matches)
        }

    except Image.DoesNotExist:
        logger.error(f"Image with UUID {image_uuid} not found")
        return {
            "status": "error",
            "error": f"Image with UUID {image_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error processing Grype scan results for image {image_uuid}: {str(e)}")
        try:
            image = Image.objects.get(uuid=image_uuid)
            image.scan_status = 'error'
            image.save()
        except Exception:
            pass
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task(bind=True, max_retries=1, name="Scan Image with Grype")
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
            image.scan_status = 'success'  # Mark as successfully scanned
            image.save()
            logger.info(f"Saved Grype results for image {image_uuid}")

            # Process Grype results
            process_grype_scan_results.delay(str(image_uuid), grype_results)
            
            logger.info(f"Successfully scanned image {image_uuid} with Grype")
            return {
                "status": "success",
                "task_name": "Scan Image with Grype",
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

@celery_app.task(name="Rescan All Images with SBOM")
def rescan_all_images_with_sbom():
    """
    Re-analyze all images that have SBOM data using Grype.
    This task schedules individual scans without waiting for them to complete.
    """
    from .models import Image
    from django.db.models import Q
    import time

    logger.info("Starting mass rescan of all images with SBOM")
    start_time = time.time()

    try:
        # Get all images that have SBOM data and are not currently being processed
        images = Image.objects.filter(
            Q(sbom_data__isnull=False) & 
            ~Q(sbom_data={}) &
            ~Q(scan_status__in=['in_process', 'pending'])
        ).order_by('updated_at')

        total_images = images.count()
        logger.info(f"Found {total_images} images with SBOM data to rescan")

        if total_images == 0:
            logger.info("No images with SBOM data found")
            return {
                "status": "success",
                "task_name": "Rescan All Images with SBOM",
                "message": "No images with SBOM data found",
                "images_scheduled": 0,
                "processing_time": 0
            }

        scheduled_count = 0
        error_count = 0
        task_ids = []

        for idx, image in enumerate(images, 1):
            logger.info(f"[{idx}/{total_images}] Scheduling scan for image {image.uuid} ({image.name})")
            
            try:
                # Schedule Grype scan for this image (non-blocking)
                result = scan_image_with_grype.apply_async(args=[str(image.uuid)])
                task_ids.append(result.id)
                scheduled_count += 1
                logger.info(f"✅ Scheduled scan for image {image.name} (task_id: {result.id})")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error scheduling scan for image {image.uuid} ({image.name}): {str(e)}")
                logger.error(f"Exception type: {type(e).__name__}")
                continue

        total_time = time.time() - start_time
        logger.info(f"🎉 Mass rescan scheduling completed in {total_time:.2f} seconds")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Total images found: {total_images}")
        logger.info(f"   - Successfully scheduled: {scheduled_count}")
        logger.info(f"   - Scheduling errors: {error_count}")
        logger.info(f"   - Processing time: {total_time:.2f} seconds")
        logger.info(f"   - Task IDs: {task_ids[:5]}{'...' if len(task_ids) > 5 else ''}")

        return {
            "status": "success",
            "task_name": "Rescan All Images with SBOM",
            "total_images": total_images,
            "images_scheduled": scheduled_count,
            "scheduling_errors": error_count,
            "processing_time": total_time,
            "task_ids": task_ids
        }

    except Exception as e:
        logger.error(f"❌ Error in mass rescan task: {str(e)}")
        return {
            "status": "error",
            "task_name": "Rescan All Images with SBOM",
            "error": str(e)
        }


@celery_app.task(name="Monitor Mass Rescan Progress") 
def monitor_mass_rescan_progress():
    """
    Monitor the progress of mass rescan by checking scan_status of images with SBOM.
    This can be called periodically to see how many images have been processed.
    """
    from .models import Image
    from django.db.models import Q, Count
    import time

    logger.info("Checking mass rescan progress...")
    
    try:
        # Get stats on images with SBOM
        images_with_sbom = Image.objects.filter(
            Q(sbom_data__isnull=False) & 
            ~Q(sbom_data={})
        )
        
        total_count = images_with_sbom.count()
        
        # Count by scan status
        status_counts = images_with_sbom.values('scan_status').annotate(count=Count('id'))
        status_breakdown = {item['scan_status']: item['count'] for item in status_counts}
        
        # Calculate progress
        completed = status_breakdown.get('success', 0)
        in_progress = status_breakdown.get('in_process', 0) + status_breakdown.get('pending', 0)
        errors = status_breakdown.get('error', 0)
        not_started = total_count - completed - in_progress - errors
        
        progress_percentage = (completed / total_count * 100) if total_count > 0 else 0
        
        logger.info(f"📊 Mass Rescan Progress Report:")
        logger.info(f"   - Total images with SBOM: {total_count}")
        logger.info(f"   - Completed: {completed} ({progress_percentage:.1f}%)")
        logger.info(f"   - In Progress: {in_progress}")
        logger.info(f"   - Errors: {errors}")
        logger.info(f"   - Not Started: {not_started}")
        logger.info(f"   - Status breakdown: {status_breakdown}")
        
        return {
            "status": "success",
            "task_name": "Monitor Mass Rescan Progress",
            "total_images": total_count,
            "completed": completed,
            "in_progress": in_progress,
            "errors": errors,
            "not_started": not_started,
            "progress_percentage": round(progress_percentage, 1),
            "status_breakdown": status_breakdown,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"❌ Error monitoring mass rescan progress: {str(e)}")
        return {
            "status": "error",
            "task_name": "Monitor Mass Rescan Progress",
            "error": str(e)
        }


@celery_app.task(name="Scan Repository Tags")
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
        
        return {
            "status": "success",
            "task_name": "Scan Repository Tags",
            "repository_name": repository.name,
            "tags_processed": len(all_tags)
        }

    except Repository.DoesNotExist:
        logger.error(f"Repository with UUID {repository_uuid} not found")
        return {
            "status": "error",
            "task_name": "Scan Repository Tags",
            "error": f"Repository with UUID {repository_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error scanning repository {repository_uuid}: {str(e)}")
        try:
            repository = Repository.objects.get(uuid=repository_uuid)
            repository.scan_status = 'error'
            repository.save()
        except Exception:
            pass
        return {
            "status": "error",
            "task_name": "Scan Repository Tags",
            "error": str(e)
        }

@celery_app.task(name="Process Single Tag")
def process_single_tag(tag_uuid: str):
    """
    Process a single repository tag and create an image if it doesn't exist.
    After processing, trigger SBOM scan for all images linked to this tag.
    """
    from .models import RepositoryTag, Image
    from .utils.acr import get_manifest, is_helm_chart, get_chart_digest, get_helm_images, get_bearer_token, get_acr_image_digest
    from .tasks import generate_sbom_and_create_components

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
                        # Get image digest from ACR
                        image_digest = None
                        if repository.container_registry and repository.container_registry.provider == 'acr':
                            image_digest = get_acr_image_digest(
                                repository.container_registry.api_url,
                                token,
                                image_ref
                            )
                        
                        # Create or get image with proper digest
                        image, created = Image.objects.get_or_create(
                            name=image_ref,
                            defaults={
                                'digest': image_digest,  # Use actual image digest
                                'artifact_reference': f"{repository.url}:{tag.tag}"
                            }
                        )
                        image.repository_tags.add(tag)
                        logger.info(f"{'Created' if created else 'Linked'} Helm image {image_ref} with digest {image_digest}")

        # Set status to success
        tag.processing_status = 'success'
        tag.save()

        # Trigger SBOM scan for all images linked to this tag
        images = tag.images.all()
        started = 0
        for image in images:
            if image.scan_status not in ['in_process', 'pending']:
                image.scan_status = 'pending'
                image.save()
                repo_tag = image.repository_tags.first()
                art_type = repo_tag.repository.repository_type if repo_tag else 'docker'
                generate_sbom_and_create_components.delay(
                    image_uuid=str(image.uuid),
                    art_type=art_type
                )
                started += 1
        logger.info(f"Triggered SBOM scan for {started} images for tag {tag.tag}")

        return {
            "status": "success",
            "task_name": "Process Single Tag",
            "tag_uuid": str(tag_uuid),
            "repository": tag.repository.name,
            "tag": tag.tag,
            "images_scanned": started
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

@celery_app.task(name="Delete Old Repository Tags")
def delete_old_repository_tags(days: int = 1):
    """
    Delete all RepositoryTag objects older than `days` days.
    """
    from .models import RepositoryTag
    cutoff = timezone.now() - timedelta(days=days)
    deleted_count, _ = RepositoryTag.objects.filter(created_at__lt=cutoff).delete()
    return {
        "status": "success",
        "task_name": "Delete Old Repository Tags",
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} old repository tags older than {days} days"
    }

@celery_app.task(name="Update Vulnerability Details")
def update_vulnerability_details(vulnerability_uuid: str):
    """
    Update detailed information for a specific vulnerability.
    This task can be triggered manually or as part of a batch update.
    """
    from .models import Vulnerability, VulnerabilityDetails
    from .utils.vulnerability_sources import collect_vulnerability_data
    from django.utils import timezone
    from django.db import transaction
    import time

    logger.info(f"Starting vulnerability details update for {vulnerability_uuid}")
    start_time = time.time()

    try:
        vulnerability = Vulnerability.objects.get(uuid=vulnerability_uuid)
        
        # Skip if already updated recently (within 24 hours)
        try:
            existing_details = vulnerability.details
            if existing_details.last_updated and (timezone.now() - existing_details.last_updated).days < 1:
                logger.info(f"Skipping {vulnerability.vulnerability_id} - updated recently")
                return {
                    "status": "skipped",
                    "reason": "updated recently",
                    "vulnerability_id": vulnerability.vulnerability_id
                }
        except VulnerabilityDetails.DoesNotExist:
            pass  # No existing details, will create new ones

        # Collect data from external sources
        cve_details, exploit_info = collect_vulnerability_data(vulnerability.vulnerability_id)
        
        # Use transaction to ensure atomicity
        with transaction.atomic():
            # Use get_or_create to avoid race conditions
            details, created = VulnerabilityDetails.objects.get_or_create(
                vulnerability=vulnerability,
                defaults={
                    'data_source': 'manual'  # Will be updated below
                }
            )

            # Update CVE details if available
            if cve_details:
                for field, value in cve_details.items():
                    if value is not None:
                        setattr(details, field, value)

            # Update exploit information if available
            if exploit_info:
                for field, value in exploit_info.items():
                    if value is not None:
                        setattr(details, field, value)

            # Update data source with current sources
            data_sources = []
            if cve_details:
                data_sources.append('CVE-CIRCL')
            if exploit_info:
                # Check CISA KEV
                if exploit_info.get('cisa_kev_known_exploited'):
                    data_sources.append('CISA-KEV')
                
                # Check Exploit-DB (separate tracking)
                if exploit_info.get('exploit_db_available'):
                    data_sources.append('Exploit-DB')
                
                # Check NVD (for reference links)
                if any('nvd' in link for link in exploit_info.get('exploit_links', [])):
                    data_sources.append('NVD')
            
            if data_sources:
                details.data_source = ' + '.join(data_sources)

            # Always update the last_updated timestamp
            details.last_updated = timezone.now()
            details.save()

        processing_time = time.time() - start_time
        logger.info(f"Updated vulnerability details for {vulnerability.vulnerability_id} in {processing_time:.2f}s")

        return {
            "status": "success",
            "task_name": "Update Vulnerability Details",
            "vulnerability_id": vulnerability.vulnerability_id,
            "created": created,
            "processing_time": processing_time,
            "has_cve_details": cve_details is not None,
            "has_exploit_info": exploit_info is not None
        }

    except Vulnerability.DoesNotExist:
        logger.error(f"Vulnerability with UUID {vulnerability_uuid} not found")
        return {
            "status": "error",
            "error": f"Vulnerability with UUID {vulnerability_uuid} not found"
        }
    except Exception as e:
        logger.error(f"Error updating vulnerability details for {vulnerability_uuid}: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Update All Vulnerability Details")
def update_all_vulnerability_details():
    """
    Update detailed information for all vulnerabilities in the database.
    This is a periodic task that should be scheduled to run daily.
    """
    from .models import Vulnerability
    from django.db import transaction
    import time

    logger.info("Starting bulk vulnerability details update")
    start_time = time.time()

    try:
        # Get all vulnerabilities that need updating
        vulnerabilities = Vulnerability.objects.all()
        total_vulnerabilities = vulnerabilities.count()
        
        logger.info(f"Found {total_vulnerabilities} vulnerabilities to process")
        
        # Process vulnerabilities in batches to avoid memory issues
        BATCH_SIZE = 100  # Increased batch size for better performance
        processed_count = 0
        success_count = 0
        error_count = 0
        
        for i in range(0, total_vulnerabilities, BATCH_SIZE):
            batch = vulnerabilities[i:i + BATCH_SIZE]
            batch_start_time = time.time()
            
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(total_vulnerabilities + BATCH_SIZE - 1)//BATCH_SIZE}")
            
            # Schedule tasks for this batch
            batch_tasks = []
            for vulnerability in batch:
                # Schedule individual task asynchronously
                task = update_vulnerability_details.delay(str(vulnerability.uuid))
                batch_tasks.append(task)
                processed_count += 1
            
            # Wait for all tasks in this batch to complete
            for task in batch_tasks:
                try:
                    result = task.get(timeout=300)  # 5 minute timeout per task
                    if result.get('status') in ['success', 'skipped']:
                        success_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"Task failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Task failed with exception: {str(e)}")
                    error_count += 1
            
            batch_time = time.time() - batch_start_time
            logger.info(f"Completed batch in {batch_time:.2f}s")

        total_time = time.time() - start_time
        logger.info(f"Bulk vulnerability update completed in {total_time:.2f}s")
        logger.info(f"Processed: {processed_count}, Success: {success_count}, Errors: {error_count}")

        return {
            "status": "completed",
            "task_name": "Update All Vulnerability Details",
            "total_vulnerabilities": total_vulnerabilities,
            "processed_count": processed_count,
            "success_count": success_count,
            "error_count": error_count,
            "processing_time": total_time
        }

    except Exception as e:
        logger.error(f"Error in bulk vulnerability update: {str(e)}")
        return {
            "status": "error",
            "task_name": "Update All Vulnerability Details",
            "error": str(e)
        }


@celery_app.task(name="Update Critical Vulnerability Details")
def update_critical_vulnerability_details():
    """
    Update detailed information for critical and high severity vulnerabilities.
    This task should be scheduled to run more frequently than the full update.
    """
    from .models import Vulnerability
    from django.utils import timezone
    from datetime import timedelta
    import time

    logger.info("Starting critical vulnerability details update")
    start_time = time.time()

    try:
        # Get critical and high severity vulnerabilities
        critical_vulns = Vulnerability.objects.filter(
            severity__in=['CRITICAL', 'HIGH']
        )
        
        # Also include vulnerabilities updated more than 7 days ago
        week_ago = timezone.now() - timedelta(days=7)
        old_vulns = Vulnerability.objects.filter(
            details__last_updated__lt=week_ago
        )
        
        # Combine and deduplicate
        vulnerabilities = (critical_vulns | old_vulns).distinct()
        total_vulnerabilities = vulnerabilities.count()
        
        logger.info(f"Found {total_vulnerabilities} critical/old vulnerabilities to process")
        
        processed_count = 0
        success_count = 0
        error_count = 0
        
        # Process in batches for better performance
        BATCH_SIZE = 50
        batch_tasks = []
        
        for i in range(0, total_vulnerabilities, BATCH_SIZE):
            batch = vulnerabilities[i:i + BATCH_SIZE]
            
            # Schedule tasks for this batch
            for vulnerability in batch:
                task = update_vulnerability_details.delay(str(vulnerability.uuid))
                batch_tasks.append(task)
                processed_count += 1
            
            # Wait for batch to complete
            for task in batch_tasks:
                try:
                    result = task.get(timeout=300)  # 5 minute timeout
                    if result.get('status') in ['success', 'skipped']:
                        success_count += 1
                    else:
                        error_count += 1
                        logger.warning(f"Critical vulnerability update failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Critical vulnerability task failed: {str(e)}")
                    error_count += 1
            
            batch_tasks = []  # Reset for next batch

        total_time = time.time() - start_time
        logger.info(f"Critical vulnerability update completed in {total_time:.2f}s")

        return {
            "status": "completed",
            "task_name": "Update Critical Vulnerability Details",
            "total_vulnerabilities": total_vulnerabilities,
            "processed_count": processed_count,
            "success_count": success_count,
            "error_count": error_count,
            "processing_time": total_time
        }

    except Exception as e:
        logger.error(f"Error in critical vulnerability update: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Cleanup Old Vulnerability Data")
def cleanup_old_vulnerability_data():
    """
    Clean up old vulnerability data and archive outdated information.
    This task should be scheduled to run weekly.
    """
    from .models import VulnerabilityDetails
    from django.utils import timezone
    from datetime import timedelta
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting vulnerability data cleanup")

    try:
        # Remove details for vulnerabilities that haven't been updated in 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        old_details = VulnerabilityDetails.objects.filter(
            last_updated__lt=cutoff_date
        )
        
        deleted_count = old_details.count()
        old_details.delete()
        
        logger.info(f"Deleted {deleted_count} old vulnerability detail records")
        
        return {
            "status": "completed",
            "task_name": "Cleanup Old Vulnerability Data",
            "deleted_records": deleted_count
        }

    except Exception as e:
        logger.error(f"Error in vulnerability data cleanup: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }


@celery_app.task(name="Update Vulnerability Details (Bulk)")
def update_vulnerability_details_bulk(vulnerability_uuids: List[str], batch_size: int = 50):
    """
    Bulk update vulnerability details for multiple vulnerabilities.
    
    Args:
        vulnerability_uuids: List of vulnerability UUIDs to update
        batch_size: Number of vulnerabilities to process in each batch
    """
    start_time = time.time()
    
    try:
        # Get vulnerabilities with select_related to optimize queries
        vulnerabilities = Vulnerability.objects.filter(uuid__in=vulnerability_uuids).select_related()
        total_count = vulnerabilities.count()
        
        logger.info(f"Starting bulk update for {total_count} vulnerabilities")
        
        processed_count = 0
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, total_count, batch_size):
            batch_vulnerabilities = vulnerabilities[i:i + batch_size]
            batch_cve_ids = [v.vulnerability_id for v in batch_vulnerabilities]
            
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_cve_ids)} vulnerabilities")
            
            try:
                # Collect data in bulk using optimized collector
                from .utils.vulnerability_sources import collect_vulnerability_data_bulk
                bulk_data = collect_vulnerability_data_bulk(batch_cve_ids)
                
                # Update database with transaction for atomicity
                with transaction.atomic():
                    for vulnerability in batch_vulnerabilities:
                        try:
                            cve_details, exploit_info = bulk_data.get(vulnerability.vulnerability_id, (None, None))
                            
                            # Use get_or_create to avoid race conditions
                            details, created = VulnerabilityDetails.objects.get_or_create(
                                vulnerability=vulnerability,
                                defaults={
                                    'data_source': 'manual'
                                }
                            )
                            
                            # Determine data source
                            data_sources = []
                            if cve_details:
                                data_sources.append('CVE-CIRCL')
                            if exploit_info:
                                # Check CISA KEV
                                if exploit_info.get('cisa_kev_known_exploited'):
                                    data_sources.append('CISA-KEV')
                                
                                # Check Exploit-DB (separate tracking)
                                if exploit_info.get('exploit_db_available'):
                                    data_sources.append('Exploit-DB')
                                
                                # Check NVD (for reference links)
                                if any('nvd' in link for link in exploit_info.get('exploit_links', [])):
                                    data_sources.append('NVD')
                            
                            data_source_str = ' + '.join(data_sources) if data_sources else 'manual'
                            
                            # Update CVE details if available
                            if cve_details:
                                for field, value in cve_details.items():
                                    if value is not None:
                                        setattr(details, field, value)
                            
                            # Update exploit information if available
                            if exploit_info:
                                for field, value in exploit_info.items():
                                    if value is not None:
                                        setattr(details, field, value)
                            
                            # Update data source
                            details.data_source = data_source_str
                            details.last_updated = timezone.now()
                            details.save()
                            
                            success_count += 1
                            
                        except Exception as e:
                            logger.error(f"Error updating vulnerability {vulnerability.vulnerability_id}: {str(e)}")
                            error_count += 1
                
                processed_count += len(batch_vulnerabilities)
                
                # Rate limiting between batches (reduced for better performance)
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
                error_count += len(batch_vulnerabilities)
                processed_count += len(batch_vulnerabilities)
        
        processing_time = time.time() - start_time
        
        result = {
            'status': 'completed',
            'total_vulnerabilities': total_count,
            'processed_count': processed_count,
            'success_count': success_count,
            'error_count': error_count,
            'processing_time': processing_time
        }
        
        logger.info(f"Bulk update completed: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in bulk update: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(name="Update Critical Vulnerabilities (Bulk)")
def update_critical_vulnerabilities_bulk():
    """
    Update details for all critical vulnerabilities using bulk processing.
    """
    try:
        # Get critical vulnerabilities that haven't been updated recently
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        critical_vulnerabilities = Vulnerability.objects.filter(
            severity='CRITICAL'
        ).exclude(
            details__last_updated__gte=cutoff_time
        )
        
        vulnerability_uuids = list(critical_vulnerabilities.values_list('uuid', flat=True))
        
        if not vulnerability_uuids:
            logger.info("No critical vulnerabilities need updating")
            return {
                'status': 'completed',
                'message': 'No critical vulnerabilities need updating',
                'total_vulnerabilities': 0
            }
        
        logger.info(f"Found {len(vulnerability_uuids)} critical vulnerabilities to update")
        
        # Use bulk update task
        return update_vulnerability_details_bulk.delay(vulnerability_uuids, batch_size=25)
        
    except Exception as e:
        logger.error(f"Error updating critical vulnerabilities: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


@celery_app.task(name="Update CISA KEV Vulnerabilities")
def update_cisa_kev_vulnerabilities():
    """
    Update details for vulnerabilities found in CISA KEV catalog.
    """
    try:
        from .utils.vulnerability_sources import VulnerabilityDataCollector
        
        collector = VulnerabilityDataCollector()
        
        # Get all vulnerabilities
        all_vulnerabilities = Vulnerability.objects.all()
        all_cve_ids = list(all_vulnerabilities.values_list('vulnerability_id', flat=True))
        
        logger.info(f"Checking {len(all_cve_ids)} vulnerabilities against CISA KEV")
        
        # Check which CVEs are in CISA KEV
        kev_results = collector._check_cisa_kev_bulk(set(all_cve_ids))
        kev_cve_ids = list(kev_results.keys())
        
        if not kev_cve_ids:
            logger.info("No vulnerabilities found in CISA KEV")
            return {
                'status': 'completed',
                'task_name': 'Update CISA KEV Vulnerabilities',
                'message': 'No vulnerabilities found in CISA KEV',
                'total_vulnerabilities': 0
            }
        
        # Get UUIDs for KEV vulnerabilities
        kev_vulnerabilities = Vulnerability.objects.filter(vulnerability_id__in=kev_cve_ids)
        vulnerability_uuids = list(kev_vulnerabilities.values_list('uuid', flat=True))
        
        logger.info(f"Found {len(vulnerability_uuids)} vulnerabilities in CISA KEV")
        
        # Use bulk update task
        return update_vulnerability_details_bulk.delay(vulnerability_uuids, batch_size=25)
        
    except Exception as e:
        logger.error(f"Error updating CISA KEV vulnerabilities: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }


def get_vulnerability_statistics() -> Dict:
    """Get statistics about vulnerability details."""
    try:
        total_vulnerabilities = Vulnerability.objects.count()
        vulnerabilities_with_details = VulnerabilityDetails.objects.count()
        
        # Count vulnerabilities with exploits
        vulnerabilities_with_exploits = VulnerabilityDetails.objects.filter(
            exploit_available=True
        ).count()
        
        # Count CISA KEV vulnerabilities
        cisa_kev_vulnerabilities = VulnerabilityDetails.objects.filter(
            cisa_kev_known_exploited=True
        ).count()
        
        # Count ransomware vulnerabilities
        ransomware_vulnerabilities = VulnerabilityDetails.objects.filter(
            cisa_kev_ransomware_use='Known'
        ).count()
        
        return {
            'total_vulnerabilities': total_vulnerabilities,
            'vulnerabilities_with_details': vulnerabilities_with_details,
            'vulnerabilities_with_exploits': vulnerabilities_with_exploits,
            'cisa_kev_vulnerabilities': cisa_kev_vulnerabilities,
            'ransomware_vulnerabilities': ransomware_vulnerabilities,
            'details_percentage': (vulnerabilities_with_details / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0,
            'exploits_percentage': (vulnerabilities_with_exploits / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0,
            'kev_percentage': (cisa_kev_vulnerabilities / total_vulnerabilities * 100) if total_vulnerabilities > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting vulnerability statistics: {str(e)}")
        return {}

@celery_app.task(name="Test Task")
def test_task():
    """
    Simple test task for debugging
    """
    import time
    
    time.sleep(2)  # Simulate some work
    
    return {
        'status': 'success',
        'message': 'Test task completed successfully',
        'task_name': 'Test Task'
    }

@celery_app.task(name="Test Failing Task")
def test_failing_task():
    """
    Simple test task that fails
    """
    raise Exception("This is a test failure")

@celery_app.task(name="Update All Components Latest Versions")
def update_all_components_latest_versions():
    """
    Update latest versions for all component versions in the system.
    This task should be scheduled to run periodically (e.g., monthly).
    
    Restrictions:
    - Skips components updated within the last 30 days
    - Processes in batches of 50 components
    """
    from .models import ComponentVersion
    import time
    import requests
    import subprocess
    from packaging.version import parse as parse_version
    from django.utils import timezone
    from datetime import timedelta

    logger.info("Starting latest versions update for all components")
    start_time = time.time()

    try:
        # Get all component versions that need updating
        now = timezone.now()
        # Skip components updated within the last 30 days (month)
        cutoff_date = now - timedelta(days=30)
        
        component_versions = ComponentVersion.objects.filter(
            purl__isnull=False
        ).exclude(
            latest_version_updated_at__gte=cutoff_date
        )
        
        total_count = component_versions.count()
        logger.info(f"Found {total_count} component versions to process (skipping components updated within last 30 days)")
        
        # Process in batches to avoid memory issues and improve performance
        BATCH_SIZE = 50  # Reduced batch size for better memory management
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i in range(0, total_count, BATCH_SIZE):
            batch = component_versions[i:i + BATCH_SIZE]
            batch_start_time = time.time()
            current_batch = i//BATCH_SIZE + 1
            total_batches = (total_count + BATCH_SIZE - 1)//BATCH_SIZE
            
            logger.info(f"Processing batch {current_batch}/{total_batches} ({len(batch)} components)")
            
            for component_version in batch:
                try:
                    if not component_version.purl:
                        skipped_count += 1
                        continue
                    
                    # Skip if already updated recently (double-check)
                    if (component_version.latest_version_updated_at and 
                        (now - component_version.latest_version_updated_at).days < 30):
                        skipped_count += 1
                        continue
                    
                    logger.debug(f"Processing component version {component_version.component.name}:{component_version.version}")
                    parts = component_version.purl.split("/")
                    if len(parts) < 2:
                        skipped_count += 1
                        continue
                    
                    package_type = parts[0].split(":")[1] if ":" in parts[0] else None
                    if not package_type:
                        skipped_count += 1
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
                            f"Updated latest version for {component_version.component.name}:{component_version.version} to {latest_version}"
                        )
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"Error processing component version {component_version.component.name}:{component_version.version}: {str(e)}"
                    )
                    continue
            
            # Log batch completion
            batch_time = time.time() - batch_start_time
            logger.info(f"Completed batch {current_batch}/{total_batches} in {batch_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"All components latest versions update completed in {total_time:.2f} seconds")
        logger.info(f"Updated: {updated_count}, Skipped: {skipped_count}, Errors: {error_count}")

        return {
            "status": "success",
            "task_name": "Update All Components Latest Versions",
            "total_processed": total_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "error_count": error_count,
            "processing_time": total_time
        }

    except Exception as e:
        logger.error(f"Error updating all components latest versions: {str(e)}")
        return {
            "status": "error",
            "task_name": "Update All Components Latest Versions",
            "error": str(e)
        }
