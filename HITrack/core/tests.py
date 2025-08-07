from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import (
    Repository, RepositoryTag, Image, Component, ComponentVersion, 
    Vulnerability, ComponentLocation, ContainerRegistry
)
import uuid


class ComponentLocationTestCase(APITestCase):
    def setUp(self):
        # Create test data
        self.registry = ContainerRegistry.objects.create(
            name="Test Registry",
            provider="acr",
            api_url="https://test.azurecr.io"
        )
        
        self.repository = Repository.objects.create(
            name="test-repo",
            url="test.azurecr.io/test-repo",
            container_registry=self.registry
        )
        
        self.repository_tag = RepositoryTag.objects.create(
            repository=self.repository,
            tag="latest"
        )
        
        self.image = Image.objects.create(
            name="test.azurecr.io/test-repo:latest",
            artifact_reference="test.azurecr.io/test-repo:latest"
        )
        self.image.repository_tags.add(self.repository_tag)
        
        self.component = Component.objects.create(
            name="test-component",
            type="python"
        )
        
        self.component_version = ComponentVersion.objects.create(
            component=self.component,
            version="1.0.0",
            purl="pkg:pypi/test-component@1.0.0"
        )
        self.component_version.images.add(self.image)
        
        self.vulnerability = Vulnerability.objects.create(
            vulnerability_id="CVE-2023-1234",
            severity="HIGH",
            description="Test vulnerability"
        )
        
        # Create component location
        self.component_location = ComponentLocation.objects.create(
            component_version=self.component_version,
            image=self.image,
            path="/app/test-component-1.0.0.egg-info",
            layer_id="sha256:test-layer-id",
            access_path="/app/test-component-1.0.0.egg-info",
            evidence_type="primary",
            annotations={"evidence": "primary"}
        )

    def test_component_location_creation(self):
        """Test that component location is created correctly"""
        location = ComponentLocation.objects.get(
            component_version=self.component_version,
            image=self.image
        )
        
        self.assertEqual(location.path, "/app/test-component-1.0.0.egg-info")
        self.assertEqual(location.layer_id, "sha256:test-layer-id")
        self.assertEqual(location.evidence_type, "primary")
        self.assertEqual(location.annotations, {"evidence": "primary"})

    def test_component_locations_api_endpoint(self):
        """Test the component-locations API endpoint"""
        url = reverse('image-component-locations', kwargs={'uuid': self.image.uuid})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        self.assertEqual(data['image_uuid'], str(self.image.uuid))
        self.assertEqual(data['image_name'], self.image.name)
        self.assertIn('component_locations', data)
        
        # Check that our component location is included
        component_locations = data['component_locations']
        self.assertEqual(len(component_locations), 1)
        
        component_data = component_locations[0]
        self.assertEqual(component_data['component_name'], 'test-component')
        self.assertEqual(component_data['component_version'], '1.0.0')
        self.assertEqual(component_data['component_type'], 'python')
        self.assertEqual(component_data['purl'], 'pkg:pypi/test-component@1.0.0')
        
        # Check locations
        locations = component_data['locations']
        self.assertEqual(len(locations), 1)
        
        location_data = locations[0]
        self.assertEqual(location_data['path'], '/app/test-component-1.0.0.egg-info')
        self.assertEqual(location_data['layer_id'], 'sha256:test-layer-id')
        self.assertEqual(location_data['evidence_type'], 'primary')
        self.assertEqual(location_data['annotations'], {'evidence': 'primary'})

    def test_component_version_serializer_includes_locations(self):
        """Test that ComponentVersionSerializer includes location information"""
        from .serializers import ComponentVersionSerializer
        
        serializer = ComponentVersionSerializer(self.component_version)
        data = serializer.data
        
        self.assertIn('locations', data)
        locations = data['locations']
        self.assertEqual(len(locations), 1)
        
        location_data = locations[0]
        self.assertEqual(location_data['path'], '/app/test-component-1.0.0.egg-info')
        self.assertEqual(location_data['layer_id'], 'sha256:test-layer-id')
        self.assertEqual(location_data['evidence_type'], 'primary')
