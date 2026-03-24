import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Component,
    ComponentLocation,
    ComponentVersion,
    ComponentVersionVulnerability,
    ContainerRegistry,
    Image,
    Repository,
    RepositoryTag,
    Vulnerability,
    VulnerabilityDetails,
)
from core.tasks import (
    _sync_repository_tag_processing_statuses,
    cleanup_old_vulnerability_data,
    deduplicate_images_by_identity,
    parse_sbom_and_create_components,
    periodic_repository_scan,
    process_grype_scan_results,
    process_single_tag,
    recalculate_vulnerability_fix_availability,
    scan_repository_tags,
    scan_image_with_grype,
    update_all_vulnerability_details,
    update_all_components_latest_versions,
    update_deb_components_latest_versions,
    update_components_latest_versions,
    update_critical_vulnerability_details,
    update_vulnerability_details_bulk,
)
from core.utils.vulnerability_sources import VulnerabilityDataCollector


class ParseSbomAndCreateComponentsTests(TestCase):
    def _create_image(self, name="registry.example.com/demo:latest"):
        return Image.objects.create(
            name=name,
            scan_status="success",
            sbom_data={
                "artifacts": [
                    {
                        "name": "Microsoft.Bcl.AsyncInterfaces",
                        "version": "9.0.0",
                        "type": "nuget",
                        "purl": "pkg:nuget/Microsoft.Bcl.AsyncInterfaces@9.0.0",
                        "cpes": [
                            {
                                "cpe": "cpe:2.3:a:microsoft_bcl_asyncinterfaces:microsoft_bcl_asyncinterfaces:9.0.0:*:*:*:*:*:*:*",
                                "source": "syft-generated",
                            }
                        ],
                    }
                ]
            },
        )

    @patch("core.tasks.scan_image_with_grype.delay")
    def test_links_existing_component_version_when_bulk_create_conflicts(self, delay_mock):
        image = self._create_image()
        component = Component.objects.create(name="Microsoft.Bcl.AsyncInterfaces", type="unknown")

        original_bulk_create = ComponentVersion.objects.bulk_create

        def concurrent_insert_then_ignore(objs, **kwargs):
            self.assertTrue(kwargs.get("ignore_conflicts"))
            for obj in objs:
                ComponentVersion.objects.create(
                    component=obj.component,
                    version=obj.version,
                    purl=obj.purl,
                    cpes=obj.cpes,
                )
            return original_bulk_create([], **kwargs)

        with patch.object(ComponentVersion.objects, "bulk_create", side_effect=concurrent_insert_then_ignore):
            result = parse_sbom_and_create_components(str(image.uuid))

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            ComponentVersion.objects.filter(component=component, version="9.0.0").count(),
            1,
        )
        component_version = ComponentVersion.objects.get(component=component, version="9.0.0")
        self.assertTrue(component_version.images.filter(pk=image.pk).exists())
        self.assertEqual(component_version.purl, "pkg:nuget/Microsoft.Bcl.AsyncInterfaces@9.0.0")
        self.assertEqual(component_version.cpes[0]["source"], "syft-generated")
        delay_mock.assert_called_once_with(str(image.uuid))

    @patch("core.tasks.scan_image_with_grype.delay")
    def test_returns_integrity_error_without_masking_exception_type(self, delay_mock):
        image = self._create_image(name="registry.example.com/demo:error")

        with patch.object(ComponentVersion.objects, "bulk_create", side_effect=IntegrityError("duplicate key")):
            result = parse_sbom_and_create_components(str(image.uuid))

        image.refresh_from_db()
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "IntegrityError")
        self.assertEqual(image.scan_status, "error")
        delay_mock.assert_not_called()

    @patch("core.tasks.scan_image_with_grype.delay")
    def test_parse_accepts_image_in_process_status_during_full_pipeline(self, delay_mock):
        image = self._create_image(name="registry.example.com/demo:in-process")
        image.scan_status = "in_process"
        image.save(update_fields=["scan_status", "updated_at"])

        result = parse_sbom_and_create_components(str(image.uuid))

        self.assertEqual(result["status"], "success")
        delay_mock.assert_called_once_with(str(image.uuid))


class ScanImageWithGrypeTests(TestCase):
    @patch("core.tasks.process_grype_scan_results.delay")
    @patch("subprocess.run")
    def test_continues_when_pipeline_marks_image_in_process(self, run_mock, process_results_delay):
        image = Image.objects.create(
            name="registry.example.com/demo:grype",
            scan_status="in_process",
            sbom_data={"artifacts": []},
        )

        def fake_run(args, **kwargs):
            self.assertEqual(args[0], "grype")
            grype_file_path = args[args.index("--file") + 1]
            with open(grype_file_path, "w", encoding="utf-8") as handle:
                json.dump({"matches": []}, handle)
            return SimpleNamespace(stdout="", returncode=0)

        run_mock.side_effect = fake_run

        result = scan_image_with_grype.run(str(image.uuid))

        image.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(image.scan_status, "in_process")
        self.assertEqual(image.grype_data, {"matches": []})
        process_results_delay.assert_called_once_with(str(image.uuid), {"matches": []})


class GrypeFixMetadataTests(TestCase):
    def test_process_grype_scan_results_marks_state_only_fix_as_not_fixable(self):
        image = Image.objects.create(
            name="registry.example.com/python-app:latest",
            scan_status="in_process",
        )

        result = process_grype_scan_results(
            str(image.uuid),
            {
                "matches": [
                    {
                        "artifact": {
                            "name": "requests",
                            "version": "2.28.0",
                            "type": "python",
                            "purl": "pkg:pypi/requests@2.28.0",
                        },
                        "vulnerability": {
                            "id": "CVE-2026-0001",
                            "severity": "HIGH",
                            "description": "Demo vulnerability",
                            "fix": {
                                "state": "fixed",
                                "versions": [],
                            },
                        },
                    }
                ]
            },
        )

        self.assertEqual(result["status"], "success")
        cvv = ComponentVersionVulnerability.objects.get(vulnerability__vulnerability_id="CVE-2026-0001")
        self.assertFalse(cvv.fixable)
        self.assertEqual(cvv.fix_status, "version_unknown")
        self.assertEqual(cvv.fix_state, "fixed")
        self.assertEqual(cvv.fix_versions, [])
        self.assertEqual(cvv.fix, "fixed")

    def test_process_grype_scan_results_marks_deb_fix_not_in_repo_when_latest_version_is_older(self):
        image = Image.objects.create(
            name="registry.example.com/debian-app:latest",
            scan_status="in_process",
        )
        component = Component.objects.create(name="openssl", type="deb")
        ComponentVersion.objects.create(
            component=component,
            version="1.0.0-1",
            latest_version="1.0.1-1",
            purl="pkg:deb/debian/openssl@1.0.0-1?arch=amd64&distro=debian-12",
        )

        result = process_grype_scan_results(
            str(image.uuid),
            {
                "matches": [
                    {
                        "artifact": {
                            "name": "openssl",
                            "version": "1.0.0-1",
                            "type": "deb",
                            "purl": "pkg:deb/debian/openssl@1.0.0-1?arch=amd64&distro=debian-12",
                        },
                        "vulnerability": {
                            "id": "CVE-2026-0002",
                            "severity": "HIGH",
                            "description": "Debian vulnerability",
                            "fix": {
                                "state": "fixed",
                                "versions": ["1.0.5-1"],
                            },
                        },
                    }
                ]
            },
        )

        self.assertEqual(result["status"], "success")
        cvv = ComponentVersionVulnerability.objects.get(vulnerability__vulnerability_id="CVE-2026-0002")
        self.assertFalse(cvv.fixable)
        self.assertEqual(cvv.fix_status, "not_in_repo")
        self.assertEqual(cvv.fix_versions, ["1.0.5-1"])
        self.assertIn("not yet in repo", cvv.fix)

    def test_recalculate_vulnerability_fix_availability_updates_existing_rows_from_stored_grype_data(self):
        image = Image.objects.create(
            name="registry.example.com/recalc-app:latest",
            scan_status="success",
            grype_data={
                "matches": [
                    {
                        "artifact": {
                            "name": "requests",
                            "version": "2.28.0",
                            "type": "python",
                            "purl": "pkg:pypi/requests@2.28.0",
                        },
                        "vulnerability": {
                            "id": "CVE-2026-0100",
                            "severity": "HIGH",
                            "description": "Stored grype vulnerability",
                            "fix": {
                                "state": "fixed",
                                "versions": [],
                            },
                        },
                    }
                ]
            },
        )
        component = Component.objects.create(name="requests", type="python")
        component_version = ComponentVersion.objects.create(
            component=component,
            version="2.28.0",
            purl="pkg:pypi/requests@2.28.0",
        )
        component_version.images.add(image)
        vulnerability = Vulnerability.objects.create(vulnerability_id="CVE-2026-0100")
        cvv = ComponentVersionVulnerability.objects.create(
            component_version=component_version,
            vulnerability=vulnerability,
            fixable=True,
            fix="fixed",
            fix_status="available",
            fix_state=None,
            fix_versions=[],
        )

        result = recalculate_vulnerability_fix_availability()

        cvv.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["cvvs_updated"], 1)
        self.assertFalse(cvv.fixable)
        self.assertEqual(cvv.fix_status, "version_unknown")
        self.assertEqual(cvv.fix_state, "fixed")
        self.assertEqual(cvv.fix_versions, [])


class SharedImageTagProcessingTests(TestCase):
    def _create_registry(self, name="jfrog-main", provider="jfrog"):
        return ContainerRegistry.objects.create(
            name=name,
            provider=provider,
            api_url=f"https://{name}.example.com",
        )

    @patch("core.tasks.generate_sbom_and_create_components.delay")
    @patch("core.utils.registry.get_helm_images_from_native_chart", return_value=["registry.example.com/shared:1.0"])
    @patch("core.utils.registry.get_helm_chart_url", return_value="https://registry.example.com/demo-chart-1.0.0.tgz")
    def test_process_single_tag_reuses_completed_shared_image_without_rescan(
        self,
        chart_url_mock,
        helm_images_mock,
        generate_sbom_delay,
    ):
        registry = self._create_registry()
        repository = Repository.objects.create(
            name="helm-local/demo-chart",
            url="registry.example.com/helm-local/demo-chart",
            repository_type="helm",
            container_registry=registry,
            repo_key="helm-local",
        )
        tag = RepositoryTag.objects.create(repository=repository, tag="1.0.0")
        image = Image.objects.create(
            name="registry.example.com/shared:1.0",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )

        result = process_single_tag(str(tag.uuid))

        tag.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["images_scanned"], 0)
        self.assertEqual(tag.processing_status, "success")
        self.assertTrue(tag.images.filter(pk=image.pk).exists())
        generate_sbom_delay.assert_not_called()
        chart_url_mock.assert_called_once()
        helm_images_mock.assert_called_once()

    @patch("core.tasks.generate_sbom_and_create_components.delay")
    @patch("core.utils.registry.get_helm_images_from_native_chart", return_value=["registry.example.com/shared:1.0"])
    @patch("core.utils.registry.get_helm_chart_url", return_value="https://registry.example.com/demo-chart-1.0.1.tgz")
    def test_process_single_tag_recovers_stale_completed_shared_image_status(
        self,
        chart_url_mock,
        helm_images_mock,
        generate_sbom_delay,
    ):
        registry = self._create_registry(name="jfrog-stale")
        repository = Repository.objects.create(
            name="helm-local/demo-chart-stale",
            url="registry.example.com/helm-local/demo-chart-stale",
            repository_type="helm",
            container_registry=registry,
            repo_key="helm-local",
        )
        existing_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.0",
            processing_status="in_process",
        )
        new_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.1",
            processing_status="in_process",
        )
        image = Image.objects.create(
            name="registry.example.com/shared:1.0",
            scan_status="in_process",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )
        image.repository_tags.add(existing_tag)

        result = process_single_tag(str(new_tag.uuid))

        image.refresh_from_db()
        existing_tag.refresh_from_db()
        new_tag.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["images_scanned"], 0)
        self.assertEqual(image.scan_status, "success")
        self.assertEqual(existing_tag.processing_status, "success")
        self.assertEqual(new_tag.processing_status, "success")
        self.assertTrue(new_tag.images.filter(pk=image.pk).exists())
        generate_sbom_delay.assert_not_called()
        chart_url_mock.assert_called_once()
        helm_images_mock.assert_called_once()

    def test_process_grype_scan_results_syncs_duplicate_shared_images(self):
        repository = Repository.objects.create(
            name="demo-repo",
            url="registry.example.com/demo",
            repository_type="helm",
        )
        first_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.0",
            processing_status="in_process",
        )
        second_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.1",
            processing_status="in_process",
        )
        source_image = Image.objects.create(
            name="registry.example.com/shared:1.0",
            digest="sha256:shared",
            scan_status="in_process",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )
        duplicate_image = Image.objects.create(
            name="registry.example.com/shared:1.0",
            digest="sha256:shared",
            scan_status="in_process",
        )
        source_image.repository_tags.add(first_tag)
        duplicate_image.repository_tags.add(second_tag)

        result = process_grype_scan_results(str(source_image.uuid), {"matches": []})

        first_tag.refresh_from_db()
        second_tag.refresh_from_db()
        source_image.refresh_from_db()
        duplicate_image.refresh_from_db()

        self.assertEqual(result["status"], "success")
        self.assertEqual(source_image.scan_status, "success")
        self.assertEqual(duplicate_image.scan_status, "success")
        self.assertEqual(duplicate_image.sbom_data, {"artifacts": []})
        self.assertEqual(duplicate_image.grype_data, {"matches": []})
        self.assertEqual(first_tag.processing_status, "success")
        self.assertEqual(second_tag.processing_status, "success")


class PeriodicRepositoryLatestScanTests(TestCase):
    def _create_registry(self, name="acr-main"):
        return ContainerRegistry.objects.create(
            name=name,
            provider="acr",
            api_url=f"https://{name}.example.com",
        )

    def _create_repository(
        self,
        name,
        registry,
        *,
        active=True,
        scan_status="none",
    ):
        return Repository.objects.create(
            name=name,
            url=f"registry.example.com/{name}",
            status=active,
            repository_type="docker",
            scan_status=scan_status,
            container_registry=registry,
        )

    @patch("core.tasks.process_single_tag.apply_async")
    @patch("core.utils.registry.get_tags", return_value=["1.2.3"])
    def test_scan_repository_tags_requeues_existing_latest_tag_when_requested(
        self,
        get_tags_mock,
        process_single_tag_async,
    ):
        registry = self._create_registry()
        repository = self._create_repository("demo-service", registry)
        tag = RepositoryTag.objects.create(repository=repository, tag="1.2.3")

        result = scan_repository_tags(
            str(repository.uuid),
            latest_only=True,
            process_existing=True,
        )

        repository.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["new_tags_created"], 0)
        self.assertEqual(result["summary"]["existing_tags_requeued"], 1)
        self.assertEqual(result["summary"]["tags_scheduled_for_processing"], 1)
        self.assertEqual(RepositoryTag.objects.filter(repository=repository).count(), 1)
        self.assertEqual(repository.scan_status, "success")
        process_single_tag_async.assert_called_once_with(
            args=[str(tag.uuid)],
            task_name="Process Single Tag",
        )
        get_tags_mock.assert_called_once()

    @patch("core.tasks.scan_repository_tags.apply_async")
    def test_periodic_repository_scan_queues_latest_scan_for_active_repositories(
        self,
        scan_repository_tags_async,
    ):
        registry = self._create_registry()
        queued_repo = self._create_repository("queued-service", registry, active=True)
        self._create_repository("busy-service", registry, active=True, scan_status="in_process")
        Repository.objects.create(
            name="missing-registry-service",
            url="registry.example.com/missing-registry-service",
            status=True,
            repository_type="docker",
        )
        self._create_repository("inactive-service", registry, active=False)

        scan_repository_tags_async.return_value = SimpleNamespace(id="queued-task-id")

        result = periodic_repository_scan()

        queued_repo.refresh_from_db()
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["summary"]["total_repositories_seen"], 3)
        self.assertEqual(result["summary"]["queued_repositories"], 1)
        self.assertEqual(result["summary"]["skipped_repositories"], 2)
        self.assertEqual(result["summary"]["failed_repositories"], 0)
        self.assertEqual(queued_repo.scan_status, "pending")
        scan_repository_tags_async.assert_called_once_with(
            args=[str(queued_repo.uuid)],
            kwargs={
                "latest_only": True,
                "process_existing": True,
            },
        )


class DockerTagImageIdentityTests(TestCase):
    def _create_registry(self, name="acr-docker-identity"):
        return ContainerRegistry.objects.create(
            name=name,
            provider="acr",
            api_url=f"https://{name}.example.com",
        )

    def _create_repository(self, registry, name="demo-service"):
        return Repository.objects.create(
            name=name,
            url=f"registry.example.com/{name}",
            repository_type="docker",
            container_registry=registry,
        )

    @patch("core.tasks.generate_sbom_and_create_components.delay")
    @patch("core.utils.registry.get_image_digest", return_value=None)
    def test_process_single_tag_reuses_existing_docker_image_from_stored_digest(
        self,
        get_image_digest_mock,
        generate_sbom_delay,
    ):
        registry = self._create_registry()
        repository = self._create_repository(registry)
        tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.2.3",
            digest="abc123",
        )
        image_ref = f"{repository.url}:{tag.tag}"
        existing_image = Image.objects.create(
            name=image_ref,
            digest="sha256:abc123",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )

        result = process_single_tag(str(tag.uuid))

        tag.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["images_scanned"], 0)
        self.assertEqual(Image.objects.filter(name=image_ref).count(), 1)
        self.assertEqual(tag.digest, "sha256:abc123")
        self.assertTrue(tag.images.filter(pk=existing_image.pk).exists())
        generate_sbom_delay.assert_not_called()
        get_image_digest_mock.assert_called_once_with(registry, image_ref)

    @patch("core.tasks.generate_sbom_and_create_components.delay")
    @patch("core.utils.registry.get_image_digest", return_value="sha256:newdigest")
    def test_process_single_tag_creates_new_docker_image_when_digest_changes(
        self,
        get_image_digest_mock,
        generate_sbom_delay,
    ):
        registry = self._create_registry(name="acr-docker-mutable")
        repository = self._create_repository(registry, name="mutable-service")
        tag = RepositoryTag.objects.create(
            repository=repository,
            tag="latest",
            digest="olddigest",
        )
        image_ref = f"{repository.url}:{tag.tag}"
        Image.objects.create(
            name=image_ref,
            digest="sha256:olddigest",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )

        result = process_single_tag(str(tag.uuid))

        tag.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(tag.digest, "sha256:newdigest")
        self.assertEqual(
            Image.objects.filter(name=image_ref).count(),
            2,
        )
        new_image = Image.objects.get(name=image_ref, digest="sha256:newdigest")
        self.assertEqual(new_image.scan_status, "pending")
        self.assertTrue(tag.images.filter(pk=new_image.pk).exists())
        generate_sbom_delay.assert_called_once_with(
            image_uuid=str(new_image.uuid),
            art_type="docker",
        )
        get_image_digest_mock.assert_called_once_with(registry, image_ref)


class ImageDeduplicationTaskTests(TestCase):
    def test_deduplicate_images_by_identity_merges_existing_duplicate_rows(self):
        repository = Repository.objects.create(
            name="dedupe-service",
            url="registry.example.com/dedupe-service",
            repository_type="docker",
        )
        first_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.0",
            processing_status="in_process",
        )
        second_tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.0-build2",
            processing_status="in_process",
        )
        image_name = "registry.example.com/dedupe-service:1.0.0"
        stale_image = Image.objects.create(
            name=image_name,
            digest="sha256:shared",
            artifact_reference=image_name,
            scan_status="error",
        )
        canonical_image = Image.objects.create(
            name=image_name,
            digest="sha256:shared",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )
        stale_image.repository_tags.add(first_tag)
        canonical_image.repository_tags.add(second_tag)

        component = Component.objects.create(name="openssl", type="deb")
        component_version = ComponentVersion.objects.create(
            component=component,
            version="1.0.0",
        )
        component_version.images.add(stale_image)
        ComponentLocation.objects.create(
            component_version=component_version,
            image=stale_image,
            path="/usr/lib/libssl.so",
            layer_id="layer-1",
            access_path="/layers/1",
            evidence_type="primary",
            annotations={"source": "test"},
        )

        result = deduplicate_images_by_identity()

        first_tag.refresh_from_db()
        second_tag.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["duplicate_groups_merged"], 1)
        self.assertEqual(result["summary"]["duplicate_images_deleted"], 1)
        self.assertEqual(Image.objects.filter(name=image_name, digest="sha256:shared").count(), 1)

        survivor = Image.objects.get(name=image_name, digest="sha256:shared")
        self.assertTrue(survivor.repository_tags.filter(pk=first_tag.pk).exists())
        self.assertTrue(survivor.repository_tags.filter(pk=second_tag.pk).exists())
        self.assertTrue(component_version.images.filter(pk=survivor.pk).exists())
        self.assertTrue(
            ComponentLocation.objects.filter(
                image=survivor,
                component_version=component_version,
                path="/usr/lib/libssl.so",
            ).exists()
        )
        self.assertEqual(first_tag.processing_status, "success")
        self.assertEqual(second_tag.processing_status, "success")

    def test_deduplicate_images_by_identity_normalizes_digest_variants(self):
        image_name = "registry.example.com/dedupe-service:latest"
        Image.objects.create(
            name=image_name,
            digest="abc123",
            scan_status="none",
        )
        Image.objects.create(
            name=image_name,
            digest="sha256:abc123",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )

        result = deduplicate_images_by_identity()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["summary"]["duplicate_groups_merged"], 1)
        self.assertEqual(result["summary"]["duplicate_images_deleted"], 1)
        self.assertEqual(
            Image.objects.filter(name=image_name, digest="sha256:abc123").count(),
            1,
        )


class VulnerabilityDataCollectorTests(TestCase):
    def test_collect_vulnerability_data_bulk_merges_epss_and_exploit_sources(self):
        collector = VulnerabilityDataCollector()
        now = timezone.now()

        with patch.object(
            collector,
            "get_epss_data_bulk",
            return_value={
                "CVE-2026-1111": {
                    "epss_score": 0.61,
                    "epss_percentile": 0.93,
                    "epss_date": date(2026, 3, 1),
                    "data_source": "FIRST-EPSS",
                }
            },
        ), patch.object(
            collector,
            "get_cve_details_bulk",
            return_value={
                "CVE-2026-1111": {
                    "cve_details_summary": "Bulk fetched summary",
                    "cve_details_score": 8.9,
                }
            },
        ), patch.object(
            collector,
            "_check_cisa_kev_bulk",
            return_value={"CVE-2026-1111": {"cisa_kev_known_exploited": True}},
        ), patch.object(
            collector,
            "_check_exploit_db_bulk",
            return_value={
                "CVE-2026-1111": {
                    "exploit_available": True,
                    "exploit_verified": True,
                    "links": ["https://www.exploit-db.com/exploits/1"],
                    "exploit_count": 1,
                    "verified_count": 1,
                    "working_count": 1,
                }
            },
        ), patch.object(
            collector,
            "_check_nvd_bulk",
            return_value={
                "CVE-2026-1111": {
                    "links": ["https://nvd.nist.gov/vuln/detail/CVE-2026-1111"],
                }
            },
        ):
            cve_details, exploit_info = collector.collect_vulnerability_data_bulk(
                ["CVE-2026-1111"]
            )["CVE-2026-1111"]

        self.assertEqual(cve_details["cve_details_summary"], "Bulk fetched summary")
        self.assertEqual(cve_details["epss_score"], 0.61)
        self.assertEqual(cve_details["epss_percentile"], 0.93)
        self.assertEqual(cve_details["epss_data_source"], "FIRST-EPSS")
        self.assertEqual(cve_details["epss_date"], date(2026, 3, 1))
        self.assertIsNotNone(cve_details["epss_last_updated"])
        self.assertLess(abs((cve_details["epss_last_updated"] - now).total_seconds()), 5)
        self.assertTrue(exploit_info["cisa_kev_known_exploited"])
        self.assertTrue(exploit_info["exploit_db_available"])
        self.assertEqual(exploit_info["exploit_db_count"], 1)
        self.assertEqual(
            exploit_info["exploit_db_links"],
            ["https://www.exploit-db.com/exploits/1"],
        )
        self.assertIn(
            "https://nvd.nist.gov/vuln/detail/CVE-2026-1111",
            exploit_info["exploit_links"],
        )


class VulnerabilityEnrichmentTaskTests(TestCase):
    def test_bulk_update_persists_detail_fields_without_per_row_get_or_create(self):
        vulnerability = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-2001",
            vulnerability_type="CVE",
            severity="HIGH",
            epss=0.0,
        )
        mocked_now = timezone.now()

        with patch(
            "core.utils.vulnerability_sources.collect_vulnerability_data_bulk",
            return_value={
                "CVE-2026-2001": (
                    {
                        "cve_details_summary": "Example summary",
                        "cve_details_score": 9.1,
                        "epss_score": 0.87,
                        "epss_percentile": 0.99,
                        "epss_date": date(2026, 3, 5),
                        "epss_data_source": "FIRST-EPSS",
                        "epss_last_updated": mocked_now,
                    },
                    {
                        "exploit_available": True,
                        "exploit_public": True,
                        "exploit_verified": True,
                        "exploit_links": ["https://nvd.nist.gov/vuln/detail/CVE-2026-2001"],
                        "cisa_kev_known_exploited": True,
                        "exploit_db_available": True,
                        "exploit_db_verified": True,
                        "exploit_db_count": 2,
                        "exploit_db_verified_count": 1,
                        "exploit_db_working_count": 1,
                        "exploit_db_links": ["https://www.exploit-db.com/exploits/42"],
                    },
                )
            },
        ), patch.object(
            VulnerabilityDetails.objects,
            "get_or_create",
            side_effect=AssertionError("bulk updater should not use per-row get_or_create"),
        ):
            result = update_vulnerability_details_bulk([str(vulnerability.uuid)], batch_size=25)

        vulnerability.refresh_from_db()
        details = vulnerability.details

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["success_count"], 1)
        self.assertEqual(details.cve_details_summary, "Example summary")
        self.assertEqual(details.cve_details_score, 9.1)
        self.assertEqual(details.epss_score, 0.87)
        self.assertEqual(details.epss_percentile, 0.99)
        self.assertEqual(details.epss_date, date(2026, 3, 5))
        self.assertEqual(details.epss_data_source, "FIRST-EPSS")
        self.assertEqual(details.epss_last_updated, mocked_now)
        self.assertTrue(details.exploit_available)
        self.assertTrue(details.cisa_kev_known_exploited)
        self.assertTrue(details.exploit_db_available)
        self.assertEqual(details.exploit_db_count, 2)
        self.assertEqual(vulnerability.epss, 0.87)
        self.assertEqual(
            details.data_source,
            "FIRST-EPSS + CVE-CIRCL + CISA-KEV + Exploit-DB + NVD",
        )

    @patch("core.tasks.update_vulnerability_details.delay")
    @patch("core.tasks.update_vulnerability_details_bulk.apply_async")
    def test_update_all_schedules_bulk_batches_only(
        self,
        bulk_apply_async,
        single_delay,
    ):
        supported = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-3001",
            vulnerability_type="CVE",
            severity="HIGH",
        )
        unsupported = Vulnerability.objects.create(
            vulnerability_id="GHSA-abcd-1234",
            vulnerability_type="GHSA",
            severity="HIGH",
        )
        VulnerabilityDetails.objects.create(
            vulnerability=supported,
            data_source="manual",
        )
        VulnerabilityDetails.objects.create(
            vulnerability=unsupported,
            data_source="manual",
        )
        stale_time = timezone.now() - timedelta(days=2)
        VulnerabilityDetails.objects.filter(
            vulnerability__in=[supported, unsupported]
        ).update(last_updated=stale_time)
        bulk_apply_async.return_value = SimpleNamespace(id="bulk-task-1")

        result = update_all_vulnerability_details()

        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["summary"]["scheduled_count"], 1)
        self.assertEqual(result["summary"]["total_batches"], 1)
        single_delay.assert_not_called()
        bulk_apply_async.assert_called_once()
        args = bulk_apply_async.call_args.kwargs["args"][0]
        self.assertEqual(args, [str(supported.uuid)])

    @patch("core.tasks.update_vulnerability_details.delay")
    @patch("core.tasks.update_vulnerability_details_bulk.apply_async")
    def test_update_critical_schedules_bulk_batches_only(
        self,
        bulk_apply_async,
        single_delay,
    ):
        critical = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-4001",
            vulnerability_type="CVE",
            severity="CRITICAL",
        )
        high = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-4002",
            vulnerability_type="CVE",
            severity="HIGH",
        )
        VulnerabilityDetails.objects.create(
            vulnerability=high,
            data_source="manual",
        )
        VulnerabilityDetails.objects.filter(vulnerability=high).update(
            last_updated=timezone.now() - timedelta(days=8)
        )
        bulk_apply_async.return_value = SimpleNamespace(id="bulk-task-2")

        result = update_critical_vulnerability_details()

        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["summary"]["scheduled_count"], 2)
        single_delay.assert_not_called()
        self.assertEqual(bulk_apply_async.call_count, 1)
        args = bulk_apply_async.call_args.kwargs["args"][0]
        self.assertCountEqual(args, [str(critical.uuid), str(high.uuid)])

    def test_cleanup_only_deletes_stale_orphaned_detail_records(self):
        old_orphan = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-5001",
            vulnerability_type="CVE",
            severity="LOW",
        )
        old_linked = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-5002",
            vulnerability_type="CVE",
            severity="LOW",
        )
        orphan_details = VulnerabilityDetails.objects.create(
            vulnerability=old_orphan,
            data_source="manual",
        )
        linked_details = VulnerabilityDetails.objects.create(
            vulnerability=old_linked,
            data_source="manual",
        )
        cutoff_time = timezone.now() - timedelta(days=100)
        VulnerabilityDetails.objects.filter(pk__in=[orphan_details.pk, linked_details.pk]).update(
            last_updated=cutoff_time
        )

        component = Component.objects.create(name="openssl", type="deb")
        component_version = ComponentVersion.objects.create(component=component, version="3.0.0")
        ComponentVersionVulnerability.objects.create(
            component_version=component_version,
            vulnerability=old_linked,
            fixable=True,
        )

        result = cleanup_old_vulnerability_data()

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["summary"]["deleted_records"], 1)
        self.assertFalse(VulnerabilityDetails.objects.filter(pk=orphan_details.pk).exists())
        self.assertTrue(VulnerabilityDetails.objects.filter(pk=linked_details.pk).exists())


class LatestVersionLookupTests(TestCase):
    @patch("core.tasks.requests.get")
    def test_update_components_latest_versions_uses_debian_package_pages_for_deb_purls(
        self,
        requests_get_mock,
    ):
        cache.clear()
        image = Image.objects.create(
            name="registry.example.com/debian-app:latest",
            scan_status="success",
        )
        component = Component.objects.create(name="openssl", type="deb")
        component_version = ComponentVersion.objects.create(
            component=component,
            version="3.0.14-1~deb12u2",
            purl="pkg:deb/debian/openssl@3.0.14-1~deb12u2?arch=amd64&distro=debian-12",
        )
        component_version.images.add(image)

        requests_get_mock.return_value = SimpleNamespace(
            ok=True,
            text="<html><body><h1># Package: openssl (3.0.17-1~deb12u1)</h1></body></html>",
        )

        result = update_components_latest_versions(str(image.uuid))

        component_version.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(component_version.latest_version, "3.0.17-1~deb12u1")
        self.assertIsNotNone(component_version.latest_version_updated_at)
        requests_get_mock.assert_called_once_with(
            "https://packages.debian.org/bookworm/amd64/openssl",
            timeout=10,
        )

    @patch("core.tasks.requests.get")
    def test_update_all_components_latest_versions_uses_same_debian_lookup(
        self,
        requests_get_mock,
    ):
        cache.clear()
        component = Component.objects.create(name="openssl", type="deb")
        component_version = ComponentVersion.objects.create(
            component=component,
            version="3.0.14-1~deb12u2",
            purl="pkg:deb/debian/openssl@3.0.14-1~deb12u2?arch=amd64&distro=debian-12",
        )

        requests_get_mock.return_value = SimpleNamespace(
            ok=True,
            text="<html><body><h1># Package: openssl (3.0.17-1~deb12u1)</h1></body></html>",
        )

        result = update_all_components_latest_versions()

        component_version.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(component_version.latest_version, "3.0.17-1~deb12u1")
        requests_get_mock.assert_called_once_with(
            "https://packages.debian.org/bookworm/amd64/openssl",
            timeout=10,
        )

    @patch("core.tasks.requests.get")
    def test_update_deb_components_latest_versions_updates_only_deb_components(
        self,
        requests_get_mock,
    ):
        cache.clear()
        deb_component = Component.objects.create(name="openssl", type="deb")
        deb_component_version = ComponentVersion.objects.create(
            component=deb_component,
            version="3.0.14-1~deb12u2",
            purl="pkg:deb/debian/openssl@3.0.14-1~deb12u2?arch=amd64&distro=debian-12",
        )
        npm_component = Component.objects.create(name="left-pad", type="npm")
        npm_component_version = ComponentVersion.objects.create(
            component=npm_component,
            version="1.0.0",
            purl="pkg:npm/left-pad@1.0.0",
            latest_version="1.0.0",
        )

        requests_get_mock.return_value = SimpleNamespace(
            ok=True,
            text="<html><body><h1># Package: openssl (3.0.17-1~deb12u1)</h1></body></html>",
        )

        result = update_deb_components_latest_versions()

        deb_component_version.refresh_from_db()
        npm_component_version.refresh_from_db()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["updated_count"], 1)
        self.assertEqual(result["total_processed"], 1)
        self.assertEqual(deb_component_version.latest_version, "3.0.17-1~deb12u1")
        self.assertEqual(npm_component_version.latest_version, "1.0.0")
        requests_get_mock.assert_called_once_with(
            "https://packages.debian.org/bookworm/amd64/openssl",
            timeout=10,
        )


class RepositoryTagProcessingStatusSyncTests(TestCase):
    def test_marks_tag_in_process_while_any_image_is_pending(self):
        repository = Repository.objects.create(
            name="demo-repo",
            url="registry.example.com/demo",
            repository_type="docker",
        )
        tag = RepositoryTag.objects.create(
            repository=repository,
            tag="1.0.0",
            processing_status="success",
        )
        image = Image.objects.create(
            name="registry.example.com/demo:1.0.0",
            scan_status="pending",
        )
        tag.images.add(image)

        _sync_repository_tag_processing_statuses([tag.pk])

        tag.refresh_from_db()
        self.assertEqual(tag.processing_status, "in_process")

    def test_marks_tag_success_when_all_images_finish_successfully(self):
        repository = Repository.objects.create(
            name="demo-repo-finished",
            url="registry.example.com/demo-finished",
            repository_type="docker",
        )
        tag = RepositoryTag.objects.create(
            repository=repository,
            tag="2.0.0",
            processing_status="in_process",
        )
        image = Image.objects.create(
            name="registry.example.com/demo-finished:2.0.0",
            scan_status="success",
        )
        tag.images.add(image)

        _sync_repository_tag_processing_statuses([tag.pk])

        tag.refresh_from_db()
        self.assertEqual(tag.processing_status, "success")
