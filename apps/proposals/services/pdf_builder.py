"""
PDF Builder Service — exports documents to PDF using WeasyPrint.

Renders the document HTML with brand CSS and generates a styled PDF.
"""
import io
import logging
from proposals.services.brand_injector import get_brand_css_variables, get_brand_font_links

logger = logging.getLogger(__name__)


def build_pdf(document):
    """
    Build a PDF from a Document model instance.

    Returns an io.BytesIO buffer containing the PDF.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        raise ImportError(
            'WeasyPrint is not installed. Run: pip install weasyprint>=61.0'
        )

    sections = document.sections.filter(is_visible=True).order_by('order')
    brand = document.brand_guideline

    # Build full HTML document
    html_content = _build_pdf_html(document, sections, brand)

    # Generate PDF
    buffer = io.BytesIO()
    HTML(string=html_content).write_pdf(buffer)
    buffer.seek(0)
    return buffer


def _build_pdf_html(document, sections, brand):
    """Build a complete HTML document for PDF rendering."""
    brand_css = get_brand_css_variables(brand)
    font_links = get_brand_font_links(brand)

    heading_font = brand.heading_font if brand else 'Inter'
    body_font = brand.body_font if brand else 'Inter'
    primary_color = brand.primary_color if brand else '#0a0a0a'
    text_color = brand.text_color if brand else '#0a0a0a'

    sections_html = ''
    for section in sections:
        title_html = f'<h2 style="color: {primary_color}; font-family: {heading_font}, sans-serif;">{section.title}</h2>' if section.title else ''
        sections_html += f'''
        <div class="section">
            {title_html}
            <div class="section-content">{section.content_html}</div>
        </div>
        '''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {font_links}
    <style>
        {brand_css}

        @page {{
            size: A4;
            margin: 2.5cm;
        }}

        body {{
            font-family: '{body_font}', 'Inter', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: {text_color};
        }}

        h1 {{
            font-family: '{heading_font}', 'Inter', sans-serif;
            color: {primary_color};
            font-size: 24pt;
            text-align: center;
            margin-bottom: 10pt;
        }}

        h2 {{
            font-family: '{heading_font}', 'Inter', sans-serif;
            color: {primary_color};
            font-size: 16pt;
            margin-top: 20pt;
            margin-bottom: 8pt;
            border-bottom: 1px solid {primary_color};
            padding-bottom: 4pt;
        }}

        .cover-page {{
            text-align: center;
            padding-top: 200px;
            page-break-after: always;
        }}

        .recipient {{
            font-size: 14pt;
            color: #666;
            margin-top: 20pt;
        }}

        .section {{
            margin-bottom: 16pt;
        }}

        .section-content {{
            text-align: justify;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10pt 0;
        }}

        td, th {{
            border: 1px solid #ddd;
            padding: 6pt 8pt;
            text-align: left;
        }}

        th {{
            background-color: {primary_color};
            color: white;
        }}

        img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="cover-page">
        <h1>{document.title}</h1>
        {f'<p class="recipient">Prepared for: {document.recipient_name}</p>' if document.recipient_name else ''}
    </div>

    {sections_html}
</body>
</html>'''
