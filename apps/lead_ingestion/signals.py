import logging

from django.dispatch import Signal, receiver

logger = logging.getLogger(__name__)

# Emitted when a RawLead is successfully parsed and a ParsedLead is created.
# Arguments: sender, instance (the ParsedLead instance)
# Downstream modules (AI BDR, email campaigns) connect to this signal.
lead_parsed = Signal()


@receiver(lead_parsed)
def _log_lead_parsed(sender, instance, **kwargs):
    """Demo receiver — logs when a lead is parsed.
    Downstream modules should disconnect this and connect their own."""
    logger.info(
        "Lead parsed | id=%s | name=%s | email=%s | source=%s | action=%s | tenant=%s",
        instance.id,
        instance.customer_name or '(unnamed)',
        instance.email_address or '(no email)',
        instance.source or '(unknown)',
        instance.predefined_action or '(not set)',
        instance.tenant_id,
    )

@receiver(lead_parsed)
def handle_lead_parsed_for_calls(sender, instance, **kwargs):
    """
    Listens for parsed leads and triggers an AI outbound call 
    if the predefined action is set to 'ai_call'.
    """
    from .tasks import trigger_ai_outbound_call
    if instance.predefined_action == 'ai_call':
        logger.info(f"Triggering automated AI call task for lead {instance.id}")
        trigger_ai_outbound_call.delay(instance.id)
