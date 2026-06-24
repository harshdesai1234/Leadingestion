import re

from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def source_class(value):
    """Map a source string to a CSS class name.

    Examples:
      'linkedin'        -> 'source-linkedin'
      'Google Ads'      -> 'source-google'
      'csv_upload: ...' -> 'source-csv'
      'facebook/meta'   -> 'source-facebook'
    """
    v = value.lower().strip()

    if v in ('linkedin', 'linkedin ads'):
        return 'source-linkedin'
    if v in ('facebook', 'meta', 'facebook/meta'):
        return 'source-facebook'
    if v in ('instagram',):
        return 'source-instagram'
    if v in ('google', 'google ads', 'google_ads'):
        return 'source-google'
    if v in ('youtube', 'youtube ads'):
        return 'source-youtube'
    if v in ('website', 'web', 'site'):
        return 'source-website'
    if v == 'webhook':
        return 'source-webhook'
    if v == 'email':
        return 'source-email'
    if v.startswith('csv_upload'):
        return 'source-csv'

    return 'source-other'


@register.filter
@stringfilter
def source_label(value):
    """Map a source string to the exact labeled name."""
    v = value.lower().strip()
    if 'linkedin' in v:
        return 'LinkedIn'
    if 'instagram' in v:
        return 'Instagram'
    if 'facebook' in v or 'meta' in v:
        return 'Facebook'
    if 'google' in v:
        return 'Google Ads'
    if 'youtube' in v:
        return 'YouTube'
    if 'webhook' in v:
        return 'Webhook'
    if 'website' in v or 'web' in v or 'site' in v:
        return 'Website'
    if v.startswith('csv_upload'):
        return 'CSV Upload'
    return 'Other'


@register.filter
@stringfilter
def source_svg(value):
    """Return an inline SVG logo for the source."""
    v = value.lower().strip()
    if 'linkedin' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>'
    if 'instagram' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>'
    if 'facebook' in v or 'meta' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"></path></svg>'
    if 'google' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'
    if 'youtube' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33 2.78 2.78 0 0 0 1.94 2c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.33 29 29 0 0 0-.46-5.33z"></path><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"></polygon></svg>'
    if 'webhook' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>'
    if 'website' in v or 'web' in v or 'site' in v:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>'
    if v.startswith('csv_upload'):
        return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>'
    return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="source-icon"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M8 12h8"></path><path d="M12 8v8"></path></svg>'
