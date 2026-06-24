"""
Settings views — per-tenant AI model configuration.
"""
from django.shortcuts import render, redirect
from proposals.permissions import proposal_permission_required
from proposals.models import ModuleSettings


@proposal_permission_required(action='update')
def proposal_settings(request):
    """View and update per-organisation AI model settings."""
    org = getattr(request, 'organization', None)
    if not org:
        return redirect('proposals:document_list')

    # Get or create settings for this org
    settings_obj, created = ModuleSettings.objects.get_or_create(
        organisation=org,
        defaults={
            'text_model_provider': ModuleSettings.PROVIDER_ANTHROPIC,
            'text_model_name': 'claude-sonnet-4-6',
            'image_model_provider': ModuleSettings.PROVIDER_GOOGLE,
            'image_model_name': 'gemini-2.0-flash-exp',
        }
    )

    if request.method == 'POST':
        settings_obj.text_model_provider = request.POST.get(
            'text_model_provider', settings_obj.text_model_provider
        )
        settings_obj.text_model_name = request.POST.get(
            'text_model_name', settings_obj.text_model_name
        )
        settings_obj.image_model_provider = request.POST.get(
            'image_model_provider', settings_obj.image_model_provider
        )
        settings_obj.image_model_name = request.POST.get(
            'image_model_name', settings_obj.image_model_name
        )
        settings_obj.fallback_text_model = request.POST.get(
            'fallback_text_model', settings_obj.fallback_text_model
        )
        max_tokens = request.POST.get('max_tokens_per_generation')
        if max_tokens:
            try:
                settings_obj.max_tokens_per_generation = int(max_tokens)
            except ValueError:
                pass
        settings_obj.enable_async_generation = request.POST.get('enable_async') == 'on'
        settings_obj.save()
        return redirect('proposals:proposal_settings')

    context = {
        'settings_obj': settings_obj,
        'page_title': 'Proposal Builder Settings',
        'text_providers': ModuleSettings.TEXT_PROVIDER_CHOICES,
        'image_providers': ModuleSettings.IMAGE_PROVIDER_CHOICES,
    }
    return render(request, 'proposals/settings/settings.html', context)
