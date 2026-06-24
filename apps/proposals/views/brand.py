"""
Brand guidelines views — CRUD for brand profiles.

All queries are filtered by request.organization for tenant isolation.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from proposals.permissions import proposal_permission_required
from proposals.models import BrandGuideline


@proposal_permission_required(action='read')
def brand_list(request):
    """List all brand guidelines for the current organisation."""
    org = getattr(request, 'organization', None)
    if not org:
        brands = BrandGuideline.objects.none()
    else:
        brands = BrandGuideline.objects.filter(organisation=org)

    context = {
        'brands': brands,
        'page_title': 'Brand Guidelines',
    }
    return render(request, 'proposals/brand/list.html', context)


@proposal_permission_required(action='create')
def brand_create(request):
    """Create a new brand guideline."""
    org = getattr(request, 'organization', None)
    if not org:
        return HttpResponseForbidden('No organisation found.')

    if request.method == 'POST':
        brand = BrandGuideline(
            organisation=org,
            created_by=request.user,
            name=request.POST.get('name', 'New Brand'),
            primary_color=request.POST.get('primary_color', '#000000'),
            secondary_color=request.POST.get('secondary_color', '#333333'),
            accent_color=request.POST.get('accent_color', '#ff3333'),
            background_color=request.POST.get('background_color', '#ffffff'),
            text_color=request.POST.get('text_color', '#0a0a0a'),
            heading_font=request.POST.get('heading_font', 'Inter'),
            body_font=request.POST.get('body_font', 'Inter'),
            custom_css=request.POST.get('custom_css', ''),
            is_default=request.POST.get('is_default') == 'on',
        )
        if 'logo' in request.FILES:
            brand.logo = request.FILES['logo']
        if 'logo_dark' in request.FILES:
            brand.logo_dark = request.FILES['logo_dark']
        if 'brand_guidelines_doc' in request.FILES:
            brand.brand_guidelines_doc = request.FILES['brand_guidelines_doc']
        brand.save()
        return redirect('proposals:brand_list')

    context = {
        'page_title': 'Create Brand Guideline',
        'brand': None,
    }
    return render(request, 'proposals/brand/form.html', context)


@proposal_permission_required(action='update')
def brand_edit(request, brand_id):
    """Edit an existing brand guideline."""
    org = getattr(request, 'organization', None)
    brand = get_object_or_404(BrandGuideline, pk=brand_id, organisation=org)

    if request.method == 'POST':
        brand.name = request.POST.get('name', brand.name)
        brand.primary_color = request.POST.get('primary_color', brand.primary_color)
        brand.secondary_color = request.POST.get('secondary_color', brand.secondary_color)
        brand.accent_color = request.POST.get('accent_color', brand.accent_color)
        brand.background_color = request.POST.get('background_color', brand.background_color)
        brand.text_color = request.POST.get('text_color', brand.text_color)
        brand.heading_font = request.POST.get('heading_font', brand.heading_font)
        brand.body_font = request.POST.get('body_font', brand.body_font)
        brand.custom_css = request.POST.get('custom_css', brand.custom_css)
        brand.is_default = request.POST.get('is_default') == 'on'
        if 'logo' in request.FILES:
            brand.logo = request.FILES['logo']
        if 'logo_dark' in request.FILES:
            brand.logo_dark = request.FILES['logo_dark']
        if 'brand_guidelines_doc' in request.FILES:
            brand.brand_guidelines_doc = request.FILES['brand_guidelines_doc']
        brand.save()
        return redirect('proposals:brand_list')

    context = {
        'page_title': f'Edit Brand — {brand.name}',
        'brand': brand,
    }
    return render(request, 'proposals/brand/form.html', context)


@proposal_permission_required(action='delete')
def brand_delete(request, brand_id):
    """Delete a brand guideline."""
    org = getattr(request, 'organization', None)
    brand = get_object_or_404(BrandGuideline, pk=brand_id, organisation=org)

    if request.method == 'POST':
        brand.delete()
        return redirect('proposals:brand_list')

    context = {
        'brand': brand,
        'page_title': f'Delete Brand — {brand.name}',
    }
    return render(request, 'proposals/brand/list.html', context)


@proposal_permission_required(action='read')
def brand_preview(request, brand_id):
    """Preview a brand guideline (live CSS rendering)."""
    org = getattr(request, 'organization', None)
    brand = get_object_or_404(BrandGuideline, pk=brand_id, organisation=org)

    context = {
        'brand': brand,
        'page_title': f'Preview — {brand.name}',
    }
    return render(request, 'proposals/brand/preview.html', context)
