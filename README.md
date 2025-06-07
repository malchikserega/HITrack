# HITrack - Container Security & Vulnerability Management Platform

HITrack is a comprehensive container security and vulnerability management platform that helps organizations track, analyze, and manage security vulnerabilities in their container images and repositories.

## Features

- **Container Image Analysis**: Scan and analyze container images for security vulnerabilities
- **Vulnerability Management**: Track and manage vulnerabilities across your container ecosystem
- **Repository Integration**: Connect and monitor container repositories
- **Component Tracking**: Monitor software components and their versions
- **Vulnerability Scoring**: Track vulnerability severity and EPSS scores
- **Fix Management**: Track fixable vulnerabilities and their remediation paths

## Technical Stack

- Python 3.12
- Django REST Framework
- Docker
- Syft (for SBOM generation)
- Grype (for vulnerability scanning)

## Getting Started

### Prerequisites

- Docker
- Python 3.12
- Docker CLI

### Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd HITrack
```

2. Build and run using Docker Compose:
```bash
docker compose build
docker compose up
```

## API Endpoints

The platform provides RESTful APIs for:
- Repository management
- Image scanning and analysis
- Vulnerability tracking
- Component version management

## Security Features

- Vulnerability scanning for container images
- SBOM (Software Bill of Materials) generation
- Severity-based vulnerability tracking
- Fix tracking and remediation paths
- Component-level vulnerability analysis

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here] 