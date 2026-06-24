from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from proposals.models import AIJob

class Command(BaseCommand):
    help = 'Mark stale RUNNING AIJobs as FAILED after a timeout'

    def handle(self, *args, **options):
        timeout_minutes = 60
        cutoff = timezone.now() - timedelta(minutes=timeout_minutes)
        stale = AIJob.objects.filter(
            status=AIJob.STATUS_RUNNING,
            updated_at__lt=cutoff,
        )
        count = stale.update(
            status=AIJob.STATUS_FAILED,
            error_message=f'Job timed out after {timeout_minutes} minutes',
        )
        self.stdout.write(f'Marked {count} stale jobs as FAILED')
