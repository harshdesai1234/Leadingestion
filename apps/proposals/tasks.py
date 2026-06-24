"""
Celery tasks for the Proposals module.

Provides async AI generation via Celery when PROPOSALS_ENABLE_CELERY=True.
When Celery is not enabled, generation falls back to synchronous execution.
"""
try:
    from celery import shared_task
except ImportError:
    # Celery not installed — define a no-op decorator so imports don't break
    def shared_task(bind=False, **kwargs):
        def decorator(func):
            return func
        return decorator

import time
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30, acks_late=True)
def generate_document_task(self, document_id, user_id, target_pages=None, generation_type='simple'):
    """
    Celery task: generate a full document via AI.

    Updates the AIJob status as it progresses and stores the result.
    This task is called when PROPOSALS_ENABLE_CELERY is True;
    otherwise, the same logic is called synchronously via
    services.ai_text.generate_document_sync().
    """
    from proposals.models import Document, AIJob
    from proposals.services.ai_text import generate_document_sync

    job = None
    try:
        document = Document.objects.get(pk=document_id)
        job = AIJob.objects.filter(
            document=document,
            job_type=AIJob.JOB_FULL_DOCUMENT,
            status__in=[AIJob.STATUS_PENDING, AIJob.STATUS_RUNNING],
        ).order_by('-created_at').first()

        if job:
            job.status = AIJob.STATUS_RUNNING
            job.save(update_fields=['status', 'updated_at'])

        # Run the synchronous generation logic
        generate_document_sync(document, user_id, job=job, target_pages=target_pages, generation_type=generation_type)

    except Document.DoesNotExist:
        logger.error(f'Document {document_id} not found for generation task.')
    except Exception as e:
        logger.exception(f'Document generation failed for doc {document_id}: {e}')
        if job:
            job.status = AIJob.STATUS_FAILED
            job.error_message = str(e)
            job.save(update_fields=['status', 'error_message', 'updated_at'])
        try:
            raise self.retry(exc=e)
        except AttributeError:
            # Not a celery task instance fallback
            pass
