from django import forms


class VaultUploadForm(forms.Form):
    file = forms.FileField(required=False)
