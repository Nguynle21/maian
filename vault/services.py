from pathlib import Path

from vault.forms import ALLOWED_EXTENSIONS
from vault.models import VaultDocument


def store_document(customer, uploaded_file, user):
    """Save an already-validated upload to the Vault. Content type comes from our
    whitelist, not from what the browser claims."""
    extension = Path(uploaded_file.name).suffix.lower()
    document = VaultDocument(
        customer=customer,
        original_filename=Path(uploaded_file.name).name[:255],
        content_type=ALLOWED_EXTENSIONS[extension],
        size_bytes=uploaded_file.size,
        uploaded_by=user,
    )
    document.file.save(uploaded_file.name, uploaded_file, save=True)
    return document
