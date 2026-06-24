"""
Export views — DOCX and PDF export of documents.

Downloads are permission-checked and tenant-isolated.
"""
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from proposals.permissions import proposal_permission_required
from proposals.models import Document


@proposal_permission_required(action='read')
def export_docx(request, doc_id):
    """Export a document as a Word (.docx) file."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    try:
        from proposals.services.docx_builder import build_docx
        docx_buffer = build_docx(document)

        response = HttpResponse(
            docx_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        safe_title = document.title.replace('"', '').replace("'", '')[:100]
        response['Content-Disposition'] = f'attachment; filename="{safe_title}.docx"'
        return response
    except Exception as e:
        return HttpResponse(f'Export failed: {e}', status=500)


@proposal_permission_required(action='read')
def export_pdf(request, doc_id):
    """Export a document as a PDF file."""
    org = getattr(request, 'organization', None)
    document = get_object_or_404(Document, pk=doc_id, organisation=org)

    try:
        from proposals.services.pdf_builder import build_pdf
        pdf_buffer = build_pdf(document)

        response = HttpResponse(
            pdf_buffer.getvalue(),
            content_type='application/pdf',
        )
        safe_title = document.title.replace('"', '').replace("'", '')[:100]
        response['Content-Disposition'] = f'attachment; filename="{safe_title}.pdf"'
        return response
    except Exception as e:
        return HttpResponse(f'Export failed: {e}', status=500)
