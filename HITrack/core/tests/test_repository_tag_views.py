from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from core.models import (
    Component,
    ComponentLocation,
    ComponentVersion,
    ComponentVersionVulnerability,
    Image,
    Release,
    Repository,
    RepositoryTag,
    RepositoryTagRelease,
    Vulnerability,
)
from core.views import RepositoryTagViewSet


class RepositoryTagViewOptimizationsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="password123",
        )
        self.client.force_authenticate(self.user)
        self.factory = APIRequestFactory()

        self.repository = Repository.objects.create(
            name="sample-repo",
            url="https://example.com/sample-repo",
            repository_type="docker",
        )
        self.tag = RepositoryTag.objects.create(
            repository=self.repository,
            tag="1.0.0",
            image_path="backend/service",
        )
        self.other_tag = RepositoryTag.objects.create(
            repository=self.repository,
            tag="2.0.0",
            image_path="backend/worker",
        )

        self.image_with_finding = Image.objects.create(
            name="registry.example.com/service:1.0.0",
            digest="sha256:111",
            scan_status="success",
            sbom_data={"artifacts": []},
            grype_data={"matches": []},
        )
        self.image_without_finding = Image.objects.create(
            name="registry.example.com/worker:1.0.0",
            digest="sha256:222",
            scan_status="success",
        )
        self.tag.images.add(self.image_with_finding, self.image_without_finding)

        component = Component.objects.create(name="openssl", type="deb")
        version_with_finding = ComponentVersion.objects.create(component=component, version="1.0.0")
        version_without_finding = ComponentVersion.objects.create(component=component, version="2.0.0")
        version_with_finding.images.add(self.image_with_finding)
        version_without_finding.images.add(self.image_without_finding)

        vulnerability = Vulnerability.objects.create(
            vulnerability_id="CVE-2026-0001",
            vulnerability_type="CVE",
            severity="HIGH",
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version_with_finding,
            vulnerability=vulnerability,
            fixable=True,
            fix="1.0.1",
        )
        ComponentLocation.objects.create(
            component_version=version_with_finding,
            image=self.image_with_finding,
            path="/usr/lib/libssl.so",
            evidence_type="primary",
        )

        release = Release.objects.create(name="REL-1", description="Release 1")
        RepositoryTagRelease.objects.create(repository_tag=self.tag, release=release)

    def test_repository_tags_list_returns_bulk_hydrated_summary_fields(self):
        repository_response = self.client.get(reverse("repository-list"))
        self.assertEqual(repository_response.status_code, 200)

        response = self.client.get(
            reverse(
                "repository-tags-list",
                kwargs={"repository_uuid": self.repository.uuid},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        results_by_tag = {item["tag"]: item for item in response.data["results"]}
        main_tag = results_by_tag["1.0.0"]
        empty_tag = results_by_tag["2.0.0"]

        self.assertEqual(main_tag["findings"], 1)
        self.assertEqual(main_tag["components"], 2)
        self.assertCountEqual(
            main_tag["image_names"],
            [
                "registry.example.com/service:1.0.0",
                "registry.example.com/worker:1.0.0",
            ],
        )
        self.assertEqual(len(main_tag["releases"]), 1)
        self.assertEqual(main_tag["releases"][0]["name"], "REL-1")

        self.assertEqual(empty_tag["findings"], 0)
        self.assertEqual(empty_tag["components"], 0)
        self.assertEqual(empty_tag["image_names"], [])
        self.assertEqual(empty_tag["releases"], [])

    def test_repository_list_reports_in_process_while_related_tag_is_active(self):
        self.repository.scan_status = "success"
        self.repository.save(update_fields=["scan_status", "updated_at"])
        self.tag.processing_status = "pending"
        self.tag.save(update_fields=["processing_status", "updated_at"])

        response = self.client.get(reverse("repository-list"))

        self.assertEqual(response.status_code, 200)
        repository_item = next(item for item in response.data["results"] if item["uuid"] == str(self.repository.uuid))
        self.assertEqual(repository_item["scan_status"], "in_process")

    def test_repository_tags_list_reports_in_process_while_related_images_are_scanning(self):
        self.tag.processing_status = "success"
        self.tag.save(update_fields=["processing_status", "updated_at"])
        self.image_with_finding.scan_status = "pending"
        self.image_with_finding.save(update_fields=["scan_status", "updated_at"])

        response = self.client.get(
            reverse(
                "repository-tags-list",
                kwargs={"repository_uuid": self.repository.uuid},
            )
        )

        self.assertEqual(response.status_code, 200)
        results_by_tag = {item["tag"]: item for item in response.data["results"]}
        self.assertEqual(results_by_tag["1.0.0"]["processing_status"], "in_process")

    def test_repository_tag_retrieve_returns_optimized_summary_fields(self):
        response = self.client.get(f"/api/repository-tags/{self.tag.uuid}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tag"], "1.0.0")
        self.assertEqual(response.data["findings"], 1)
        self.assertEqual(response.data["components"], 2)
        self.assertEqual(response.data["vulnerabilities_count"], 1)
        self.assertEqual(len(response.data["releases"]), 1)
        self.assertEqual(response.data["releases"][0]["name"], "REL-1")
        self.assertEqual(len(response.data["images"]), 2)
        images_by_name = {item["name"]: item for item in response.data["images"]}
        self.assertEqual(images_by_name["registry.example.com/service:1.0.0"]["findings"], 1)
        self.assertEqual(images_by_name["registry.example.com/service:1.0.0"]["components_count"], 1)

    def test_repository_tag_images_support_search_and_ordering_on_summary_fields(self):
        request = self.factory.get(
            "/api/repository-tags/images/",
            {"ordering": "-findings", "search": "registry.example.com"},
        )
        force_authenticate(request, user=self.user)
        view = RepositoryTagViewSet.as_view({"get": "images"})

        with patch.object(RepositoryTagViewSet, "get_object", return_value=self.tag):
            response = view(
                request,
                uuid=str(self.tag.uuid),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        first_image = response.data["results"][0]
        second_image = response.data["results"][1]

        self.assertEqual(first_image["name"], "registry.example.com/service:1.0.0")
        self.assertEqual(first_image["findings"], 1)
        self.assertEqual(first_image["components_count"], 1)
        self.assertTrue(first_image["has_sbom"])
        self.assertTrue(first_image["has_grype"])

        self.assertEqual(second_image["name"], "registry.example.com/worker:1.0.0")
        self.assertEqual(second_image["findings"], 0)
        self.assertEqual(second_image["components_count"], 1)
        self.assertFalse(second_image["has_sbom"])
        self.assertFalse(second_image["has_grype"])

    def test_image_detail_returns_aggregated_summary_fields(self):
        response = self.client.get(f"/api/images/{self.image_with_finding.uuid}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["findings"], 1)
        self.assertEqual(response.data["unique_findings"], 1)
        self.assertEqual(response.data["components_count"], 1)
        self.assertEqual(response.data["fully_fixable_components_count"], 1)
        self.assertEqual(response.data["fixable_findings"], 1)
        self.assertEqual(response.data["fixable_unique_findings"], 1)
        self.assertEqual(response.data["severity_counts"]["HIGH"], 1)
        self.assertEqual(response.data["unique_severity_counts"]["HIGH"], 1)
        self.assertEqual(response.data["fixable_unique_severity_counts"]["HIGH"], 1)
        self.assertTrue(response.data["has_sbom"])
        self.assertTrue(response.data["has_grype"])
        self.assertEqual(response.data["repository_info"]["repository_name"], "sample-repo")
        self.assertEqual(response.data["repository_info"]["tag"], "1.0.0")

    def test_image_components_endpoint_returns_prefetched_component_details(self):
        response = self.client.get(f"/api/images/{self.image_with_finding.uuid}/components/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        item = response.data["results"][0]
        self.assertEqual(item["component"]["name"], "openssl")
        self.assertEqual(item["version"], "1.0.0")
        self.assertEqual(item["vulnerabilities_count"], 1)
        self.assertEqual(item["used_count"], 1)
        self.assertEqual(len(item["vulnerabilities"]), 1)
        self.assertEqual(item["vulnerabilities"][0]["vulnerability_id"], "CVE-2026-0001")
        self.assertEqual(len(item["locations"]), 1)
        self.assertEqual(item["locations"][0]["path"], "/usr/lib/libssl.so")

    def test_process_endpoint_rejects_duplicate_processing_while_tag_images_are_active(self):
        self.tag.processing_status = "success"
        self.tag.save(update_fields=["processing_status", "updated_at"])
        self.image_with_finding.scan_status = "in_process"
        self.image_with_finding.save(update_fields=["scan_status", "updated_at"])

        response = self.client.post(f"/api/repository-tags/{self.tag.uuid}/process/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Tag is already queued for processing")

    @patch("core.tasks.scan_image_with_grype.delay")
    def test_rescan_grype_endpoint_marks_image_pending_before_queueing(self, delay_mock):
        self.image_with_finding.scan_status = "success"
        self.image_with_finding.save(update_fields=["scan_status", "updated_at"])

        response = self.client.post(f"/api/images/{self.image_with_finding.uuid}/rescan-grype/")

        self.assertEqual(response.status_code, 200)
        self.image_with_finding.refresh_from_db()
        self.assertEqual(self.image_with_finding.scan_status, "pending")
        delay_mock.assert_called_once_with(str(self.image_with_finding.uuid))

    def test_release_contents_returns_release_tag_scan_summary_by_uuid(self):
        release = Release.objects.get(name="REL-1")
        RepositoryTagRelease.objects.create(
            repository_tag=self.other_tag,
            release=release,
        )

        response = self.client.get(f"/api/releases/{release.uuid}/contents/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["total_tags"], 2)
        self.assertEqual(response.data["summary"]["success_tags"], 1)
        self.assertEqual(response.data["summary"]["unscanned_tags"], 1)
        tags_by_uuid = {item["uuid"]: item for item in response.data["tags"]}
        self.assertEqual(tags_by_uuid[str(self.tag.uuid)]["processing_status"], "success")
        self.assertEqual(tags_by_uuid[str(self.other_tag.uuid)]["processing_status"], "none")
        self.assertEqual(
            tags_by_uuid[str(self.tag.uuid)]["repository"]["name"],
            "sample-repo",
        )

    @patch("core.tasks.process_single_tag.apply_async")
    def test_release_scan_unscanned_queues_only_non_success_tags(self, process_single_tag_async):
        release = Release.objects.get(name="REL-1")
        RepositoryTagRelease.objects.create(
            repository_tag=self.other_tag,
            release=release,
        )

        response = self.client.post(f"/api/releases/{release.uuid}/scan-unscanned/")

        self.assertEqual(response.status_code, 200)
        self.other_tag.refresh_from_db()
        self.assertEqual(self.other_tag.processing_status, "pending")
        self.assertEqual(response.data["summary"]["queued_tags"], 1)
        self.assertEqual(response.data["summary"]["already_scanned_tags"], 1)
        process_single_tag_async.assert_called_once_with(
            args=[str(self.other_tag.uuid)],
            task_name="Process Single Tag",
        )
