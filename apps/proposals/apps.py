from django.apps import AppConfig


class ProposalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'proposals'
    verbose_name = 'Proposal Builder'

    def ready(self):
        # Import signals when the app is ready
        try:
            import proposals.signals  # noqa: F401
        except ImportError:
            pass
