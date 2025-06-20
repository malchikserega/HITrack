# HITrack - Container Security & Vulnerability Management Platform

[![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-green.svg)](https://vuejs.org/)
[![Django](https://img.shields.io/badge/Django-5.0+-darkgreen.svg)](https://www.djangoproject.com/)

HITrack is a comprehensive container security and vulnerability management platform designed to help organizations track, analyze, and manage security vulnerabilities in their container images and repositories. Built with modern technologies, it provides real-time scanning, detailed vulnerability analysis, and comprehensive reporting capabilities.

## 🌟 Key Features

### 🔍 **Container Image Analysis**
- Automated scanning of container images for security vulnerabilities
- SBOM (Software Bill of Materials) generation using Syft
- Vulnerability detection using Grype scanner
- Support for multiple container registries (Docker public images, Azure ACR)

### 🛡️ **Vulnerability Management**
- Real-time vulnerability tracking and scoring
- EPSS (Exploit Prediction Scoring System) integration
- Severity-based vulnerability classification (Critical, High, Medium, Low)
- Fix tracking and remediation path identification

### 📊 **Component Tracking**
- Detailed component version management
- Component matrix visualization for comparison across images/repositories
- Latest version tracking and update recommendations
- PURL (Package URL) and CPE (Common Platform Enumeration) support

### 🔄 **Repository Integration**
- **Currently supports**: Azure Container Registry (ACR) integration
- Automated tag discovery and processing for ACR repositories
- Repository health monitoring
- Scan status tracking and history
- **Planned**: Multi-registry support with unified interface


### 📈 **Advanced Analytics**
- Component matrix generation for cross-repository analysis
- Export capabilities (Excel, PNG)
- Real-time dashboard with vulnerability statistics
- Historical scan data and trends

## 🏗️ Architecture

HITrack follows a modern microservices architecture with the following components:

- **Backend API**: Django REST Framework with PostgreSQL
- **Frontend**: Vue.js 3 with Vuetify 3 UI framework
- **Task Queue**: Celery with Redis for background processing
- **Containerization**: Docker and Docker Compose
- **Web Server**: Apache HTTP Server with reverse proxy

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Git
- At least 4GB RAM available
- **Azure Container Registry (ACR)** account for testing

### Current Support

**✅ Production Ready:**
- Azure Container Registry (ACR) - Full integration with authentication, repository discovery, and image scanning

**🔄 Planned Support:**
- Docker Hub - Public and private repository support
- Google Container Registry (GCR) - GCP integration  
- JFrog Artifactory - Enterprise artifact management
- Harbor - Open source container registry


### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/HITrack.git
   cd HITrack
   ```

2. **Configure environment variables**
   ```bash
   cp env.env.example env.env
   # Edit env.env with your configuration
   ```

3. **Build and start the application**
   ```bash
   docker compose build
   docker compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:1337
   - Admin: http://localhost:1337/admin/
   - API Documentation: http://localhost:1337/api/schema/


### Docker Configuration

The application uses Docker Compose with the following services:

- `hitrack-db`: PostgreSQL database
- `hitrack-redis`: Redis for caching and task queue
- `hitrack-api`: Django REST API
- `worker`: Celery background workers
- `hitrack-frontend`: Vue.js frontend
- `httpd`: Apache reverse proxy

## 🛠️ Development

### Local Development Setup

1. **Clone and setup**
   ```bash
   git clone https://github.com/malchikserega/HITrack.git
   cd HITrack
   ```

2. **Backend development**
   ```bash
   cd HITrack
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python manage.py runserver
   ```

3. **Frontend development**
   ```bash
   cd HITrack-frontend
   npm install
   npm run dev
   ```

### API Documentation

The API provides comprehensive endpoints for:

- **Repositories**: CRUD operations for container repositories
- **Images**: Image scanning and analysis
- **Components**: Component version tracking
- **Vulnerabilities**: Vulnerability management and scoring
- **Component Matrix**: Cross-repository component analysis

Access the interactive API documentation at `/api/schema/` when running the application.

## 📊 Monitoring and Logs

### Viewing Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs hitrack-api
docker compose logs worker
docker compose logs hitrack-frontend
```

## 📝 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License** (CC BY-NC-SA 4.0).

### License Terms

- **Attribution**: You must give appropriate credit to the original author
- **NonCommercial**: You may not use the material for commercial purposes
- **ShareAlike**: If you remix, transform, or build upon the material, you must distribute your contributions under the same license

### Commercial Use

For commercial use or licensing inquiries, please contact the project maintainers.

## 🙏 Acknowledgments

### Project Contributors
- **Sergei Ovchinnikov** ([@malchikserega](https://github.com/malchikserega))
- **vmvarga** ([@vmvarga](https://github.com/vmvarga))

### Open Source Tools
- [Syft](https://github.com/anchore/syft) for SBOM generation (Apache License 2.0)
- [Grype](https://github.com/anchore/grype) for vulnerability scanning (Apache License 2.0)
- [Django](https://www.djangoproject.com/) for the web framework
- [Vue.js](https://vuejs.org/) for the frontend framework
- [Vuetify](https://vuetifyjs.com/) for the UI components

## 👥 Main Contributors

### Project Maintainers

**Sergei Ovchinnikov** ([@malchikserega](https://github.com/malchikserega))
- **GitHub**: [github.com/malchikserega](https://github.com/malchikserega)
- **X (Twitter)**: [@malchikserega](https://twitter.com/malchikserega)

**vmvarga** ([@vmvarga](https://github.com/vmvarga))
- **GitHub**: [github.com/vmvarga](https://github.com/vmvarga)
- **X (Twitter)**: [@typecookie](https://twitter.com/typecookie)


## 📈 Roadmap

- [ ] JFrog integration
---

**Made with ❤️ for the security community**

*HITrack - Secure your images, track your vulnerabilities*