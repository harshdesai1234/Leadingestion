from django.apps import AppConfig


class LeadIngestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lead_ingestion'
    verbose_name = 'Lead Ingestion'

    def ready(self):
        import lead_ingestion.signals  # noqa: F401 — registers signal
