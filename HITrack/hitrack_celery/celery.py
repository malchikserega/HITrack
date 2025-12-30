from __future__ import absolute_import, unicode_literals
from django.conf import settings
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'HITrack.settings')

celery_app = Celery('hitrack_celery')
celery_app.config_from_object('django.conf:settings', namespace='CELERY')
celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)