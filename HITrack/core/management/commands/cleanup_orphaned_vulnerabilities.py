from __future__ import absolute_import, unicode_literals
from django.core.management.base import BaseCommand
from django.db.models import Count


class Command(BaseCommand):
    help = 'Remove vulnerabilities that have no linked component versions (and thus no images). Use after deleting images to keep statistics accurate.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report how many would be deleted, do not delete.',
        )

    def handle(self, *args, **options):
        from core.models import Vulnerability

        orphaned = Vulnerability.objects.annotate(
            n=Count('component_versions')
        ).filter(n=0)
        count = orphaned.count()

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'Would delete {count} orphaned vulnerability(ies). Run without --dry-run to delete.'))
            return

        orphaned.delete()
        self.stdout.write(self.style.SUCCESS(f'Removed {count} orphaned vulnerability(ies).'))
