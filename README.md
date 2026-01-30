<div align="center">
  <img src="docs/logo.png" alt="HITrack Logo" width="200" height="200">
  
  # HITrack - Container Security Platform
  
  [![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
  [![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-green.svg)](https://vuejs.org/)
  [![Django](https://img.shields.io/badge/Django-5.0+-darkgreen.svg)](https://www.djangoproject.com/)
</div>

HITrack is a container security platform that helps organizations track and manage vulnerabilities in their container images and repositories.

## ✨ Features

- **Container Scanning**: Automated vulnerability scanning using Grype
- **SBOM Generation**: Software Bill of Materials using Syft
- **Repository Integration**: Azure Container Registry (ACR) support
- **Vulnerability Management**: Real-time tracking with EPSS scoring
- **Component Tracking**: Version management and comparison
- **Analytics Dashboard**: Real-time statistics and reporting

<img src="docs/metrics.png" width="500" />
<img src="docs/vulnview.png" width="500" />

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Azure Container Registry account

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/HITrack.git
   cd HITrack
   ```

2.**Start the application**
   ```bash
   docker compose up -d
   ```

3.**Access the application**
   - Frontend: http://localhost:1337
   - Admin: http://localhost:1337/admin/

4. **Default credentials**
   - Login: admin
   - Password: P@ssw0rd

## 🏗️ Architecture

- **Backend**: Django REST Framework + PostgreSQL
- **Frontend**: Vue.js 3 + Vuetify 3
- **Task Queue**: Celery + Redis
TBD


## 🛠️ Development


### Backend
```bash
cd HITrack
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

#Celery BEAT
celery -A hitrack_celery beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
#Celery WORKER
celery -A hitrack_celery worker --loglevel=INFO -E --pool=threads
# DB & Redis
docker compose up hitrack-db hitrack-redis
python manage.py runserver
```


### Frontend
```bash
cd HITrack-frontend
npm install
npm run dev
```

## 📊 Monitoring

```bash
# View logs
docker compose logs

# Specific service
docker compose logs hitrack-api
```

## 🔧 Troubleshooting

### Artifactory: listing and adding repositories

Use the **Artifactory base URL** (no repo key) so HITrack can discover all Docker repos via the REST API, like your own script’s `GET /api/repositories`.

- **Correct:** `https://repo.example.com/artifactory`  
  → HITrack calls `GET .../api/repositories?packageType=docker` and shows all Docker repo keys (e.g. `a8n-docker`). You then select which repo keys to add.
- **Wrong:** `https://repo.example.com/artifactory/a8n-docker`  
  → That single-repo style is not used for the “list repos then select” flow.

In **Admin → Container Registries**, set your JFrog registry **API URL** to the base only, e.g. `https://repo.com.int.zone/artifactory`. Use the same login/password (or API key) as in your script. After that, “Add from Artifactory” will list Docker repo keys and let you select which to include.

### KeyError: 'fix' when running migrations

This error occurs when a migration tries to remove the `fix` field from a model that doesn't have it in the migration state. The `fix` field lives on **ComponentVersionVulnerability** (the through model), not on **Vulnerability**.

**Fix:**

1. Find the migration that removes `fix`, for example:
   ```bash
   grep -r "RemoveField\|name=.fix" HITrack/core/migrations/
   ```
2. Open that migration file. If it contains something like:
   `RemoveField(model_name='vulnerability', name='fix')` — that is wrong (Vulnerability never had `fix`).
3. Either **delete that migration file** (if you want to keep the `fix` field), or change the operation to the correct model only if you intend to remove the field from the through model:  
   `RemoveField(model_name='componentversionvulnerability', name='fix')`
4. If the broken migration was already applied to the database, fake-rollback then migrate again:
   ```bash
   python manage.py migrate core 0001_initial --fake
   python manage.py migrate
   ```

## 📝 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License** (CC BY-NC-SA 4.0).

## Roadmap
- [ ] JFrog support
- [ ] AWS ECR



## 👥 Contributors

- **Sergei Ovchinnikov** ([@malchikserega](https://github.com/malchikserega))
- **Ilya Kostyulin** ([@vmvarga](https://github.com/vmvarga))

## Publications
- https://medium.com/@malchikserega/humble-image-security-tracking-with-syft-grype-under-the-hood-76120e917029

## 🙏 Acknowledgments

- [Syft](https://github.com/anchore/syft) for SBOM generation
- [Grype](https://github.com/anchore/grype) for vulnerability scanning
- [Django](https://www.djangoproject.com/) and [Vue.js](https://vuejs.org/) frameworks

---

**Made with ❤️ for the security community**