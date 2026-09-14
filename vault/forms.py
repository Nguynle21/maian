from pathlib import Path

from django import forms

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class VaultUploadForm(forms.Form):
    file = forms.FileField(
        required=False,
        label="Upload a document (PDF, JPG, PNG, up to 10 MB)",
        widget=forms.ClearableFileInput(attrs={"accept": ",".join(ALLOWED_EXTENSIONS)}),
    )

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            return None
        if Path(uploaded.name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Only PDF, JPG, and PNG files can be uploaded.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file is larger than 10 MB.")
        return uploaded
