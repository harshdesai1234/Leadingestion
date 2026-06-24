"""
Brand Injector Service — applies brand tokens to document CSS.

Generates CSS custom properties from a BrandGuideline model instance
and injects them into document templates for live preview and export.
"""


def get_brand_css_variables(brand_guideline):
    """
    Generate CSS custom property declarations from a BrandGuideline.

    Returns a string of CSS that can be injected into a <style> tag
    or used in an inline style block.
    """
    if not brand_guideline:
        return ''

    css_vars = {
        '--brand-primary': brand_guideline.primary_color,
        '--brand-secondary': brand_guideline.secondary_color,
        '--brand-accent': brand_guideline.accent_color,
        '--brand-bg': brand_guideline.background_color,
        '--brand-text': brand_guideline.text_color,
        '--brand-heading-font': f"'{brand_guideline.heading_font}', sans-serif",
        '--brand-body-font': f"'{brand_guideline.body_font}', sans-serif",
    }

    declarations = '\n'.join(
        f'  {key}: {value};' for key, value in css_vars.items()
    )

    css = f':root {{\n{declarations}\n}}'

    # Append custom CSS if provided
    if brand_guideline.custom_css:
        css += f'\n\n/* Custom brand CSS */\n{brand_guideline.custom_css}'

    return css


def get_brand_font_links(brand_guideline):
    """
    Generate Google Fonts <link> tags for the brand's fonts.

    Returns a list of HTML link tags to include in the document <head>.
    """
    if not brand_guideline:
        return ''

    fonts = set()
    if brand_guideline.heading_font:
        fonts.add(brand_guideline.heading_font)
    if brand_guideline.body_font:
        fonts.add(brand_guideline.body_font)

    if not fonts:
        return ''

    # Build Google Fonts URL
    font_families = '&family='.join(
        f.replace(' ', '+') + ':wght@400;600;700' for f in fonts
    )
    return (
        f'<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link href="https://fonts.googleapis.com/css2?family={font_families}&display=swap" rel="stylesheet">'
    )
