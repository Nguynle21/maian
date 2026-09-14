import logging

from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from core.archive import archive
from customers.models import Customer
from vault.forms import VaultUploadForm
from vault.models import VaultDocument
from vault.services import store_document

logger = logging.getLogger(__name__)


@require_POST
def upload(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    form = VaultUploadForm(request.POST, request.FILES)
    if not form.is_valid() or not form.cleaned_data.get("file"):
        messages.error(request, " ".join(form.errors.get("file", ["Choose a file first."])))
        return redirect("customers:detail", pk=customer.pk)
    try:
        store_document(customer, form.cleaned_data["file"], request.user)
        messages.success(request, "Document uploaded.")
    except Exception:
        logger.exception("Vault upload failed for customer %s", customer.pk)
        messages.error(request, "The upload failed. Try again.")
    return redirect("customers:detail", pk=customer.pk)


def download(request, pk):
    """Reached only by a verified user (middleware). Production redirects to a
    5-minute presigned R2 link; development streams the local file."""
    document = get_object_or_404(VaultDocument, pk=pk)
    storage = document.file.storage
    if hasattr(storage, "bucket_name"):
        url = storage.url(document.file.name, parameters={
            "ResponseContentDisposition": content_disposition_header(True, document.original_filename),
            "ResponseContentType": document.content_type,
        })
        return redirect(url)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.original_filename)


@require_POST
def archive_document(request, pk):
    document = get_object_or_404(VaultDocument, pk=pk)
    archive(document, request.user)
    messages.success(request, "Document archived.")
    return redirect("customers:detail", pk=document.customer_id)
