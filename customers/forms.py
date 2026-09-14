import re

from django import forms
from django.forms import inlineformset_factory

from customers.models import Customer, HouseholdMember

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
PHONE_WIDGET = forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "off"})


class CustomerForm(forms.ModelForm):
    household_income = forms.CharField(required=False, label="Household income (annual $)")

    class Meta:
        model = Customer
        fields = [
            "first_name", "middle_name", "last_name", "gender", "date_of_birth", "email",
            "phone_primary", "phone_secondary", "emergency_contact_name", "emergency_contact_phone",
            "preferred_language", "immigration_status", "household_income",
            "res_street", "res_apt", "res_city", "res_state", "res_zip",
            "mailing_same_as_residential", "mail_street", "mail_apt", "mail_city", "mail_state", "mail_zip",
        ]
        labels = {
            "phone_primary": "Primary phone (gets SMS)",
            "phone_secondary": "Second phone",
            "res_street": "Street", "res_apt": "Apt", "res_city": "City", "res_state": "State", "res_zip": "ZIP",
            "mail_street": "Street", "mail_apt": "Apt", "mail_city": "City", "mail_state": "State", "mail_zip": "ZIP",
            "mailing_same_as_residential": "Mailing address is the same as residential",
        }
        widgets = {
            "date_of_birth": DATE_WIDGET,
            "phone_primary": PHONE_WIDGET,
            "phone_secondary": PHONE_WIDGET,
            "emergency_contact_phone": PHONE_WIDGET,
        }

    def clean_household_income(self):
        """Accept what staff actually type: '$45,000', '45000', '45,000.00'."""
        raw = re.sub(r"[^\d.]", "", self.cleaned_data.get("household_income") or "")
        if not raw:
            return None
        try:
            return int(round(float(raw)))
        except ValueError:
            raise forms.ValidationError("Enter a dollar amount, e.g. 45000")


class SpouseForm(forms.ModelForm):
    class Meta:
        model = HouseholdMember
        fields = ["first_name", "middle_name", "last_name", "gender", "date_of_birth", "phone", "immigration_status"]
        widgets = {"date_of_birth": DATE_WIDGET, "phone": PHONE_WIDGET}


class DependentForm(forms.ModelForm):
    class Meta:
        model = HouseholdMember
        fields = [
            "first_name", "middle_name", "last_name", "gender", "date_of_birth", "phone",
            "immigration_status", "public_coverage",
        ]
        widgets = {"date_of_birth": DATE_WIDGET, "phone": PHONE_WIDGET}


# fk_name is required: HouseholdMember has two FKs to Customer (customer, linked_customer).
# Blank extra rows are ignored on save. A family with more dependents saves, and the
# edit page offers two more blank rows. No JavaScript needed.
SpouseFormSet = inlineformset_factory(
    Customer, HouseholdMember, fk_name="customer", form=SpouseForm,
    extra=1, max_num=1, validate_max=True, can_delete=False,
)
DependentFormSet = inlineformset_factory(
    Customer, HouseholdMember, fk_name="customer", form=DependentForm, extra=2, can_delete=False,
)
