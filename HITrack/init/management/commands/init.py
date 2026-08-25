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
        name = os.getenv('SUPERUSER_NAME')
        password = os.getenv('SUPERUSER_PSWD')
        if not name and not password:
            logger.warning(
                'No active superuser exists. Set SUPERUSER_NAME and SUPERUSER_PSWD '
                'or run `python manage.py createsuperuser`.'
            )
            return
        if not name or not password:
            raise ValueError('SUPERUSER_NAME and SUPERUSER_PSWD must be set together')
        user_model.objects.create_superuser(username=name, password=password, email='')
        logger.info('Configured superuser %s successfully created', name)

    def handle(self, *args, **options):
        self._create_superuser()
