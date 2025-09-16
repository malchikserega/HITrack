from __future__ import absolute_import, unicode_literals
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create superuser.'

    @staticmethod
    def _create_superuser():
        """
        Create superuser
        """
        user_model = get_user_model()
        has_admin = user_model.objects.filter(is_superuser=True, is_active=True).count()
        if has_admin:
            logger.info('Superuser already exists')
            return
        name = os.getenv('SUPERUSER_NAME', 'admin')
        password = os.getenv('SUPERUSER_PSWD', 'P@ssw0rd')
        user_model.objects.create_superuser(username=name, password=password, email='')
        logger.info('Default superuser: admin, successfully created')

    def handle(self, *args, **options):
        self._create_superuser()

