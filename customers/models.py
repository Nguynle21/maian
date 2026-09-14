from django.conf import settings
from django.db import models

from core.models import ArchivableModel
from customers.phones import is_us_phone, normalize_phone


class Gender(models.TextChoices):
    FEMALE = "female", "Female"
    MALE = "male", "Male"


class ImmigrationStatus(models.TextChoices):
    US_CITIZEN = "us_citizen", "US citizen"
    GREEN_CARD = "green_card", "Green card holder"
    VISA = "visa", "Visa"
    WORK_PERMIT = "work_permit", "Work permit"


class Language(models.TextChoices):
    EN = "en", "English"
    VI = "vi", "Vietnamese"
    ES = "es", "Spanish"


class Relationship(models.TextChoices):
    SPOUSE = "spouse", "Spouse"
    DEPENDENT = "dependent", "Dependent"


class PublicCoverage(models.TextChoices):
    NONE = "none", "None"
    CHIP = "chip", "CHIP"
    MEDICAID = "medicaid", "Medicaid"
    MEDICARE = "medicare", "Medicare"


def _text(max_length=100):
    return models.CharField(max_length=max_length, blank=True)


class Customer(ArchivableModel):
    """A person the agency serves. Every field is optional: intake gets interrupted.
    No SSN, ever. No enrollment status here: that belongs on Application (ADR-0005)."""

    PHONE_FIELDS = ("phone_primary", "phone_secondary", "emergency_contact_phone")

    first_name = _text()
    middle_name = _text()
    last_name = _text()
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)

    res_street = _text(200)
    res_apt = _text(50)
    res_city = _text()
    res_state = models.CharField(max_length=2, blank=True, default="TX")
    res_zip = _text(10)

    mailing_same_as_residential = models.BooleanField(default=True)
    mail_street = _text(200)
    mail_apt = _text(50)
    mail_city = _text()
    mail_state = models.CharField(max_length=2, blank=True)
    mail_zip = _text(10)

    phone_primary = _text(20)
    phone_secondary = _text(20)
    emergency_contact_name = _text(200)
    emergency_contact_phone = _text(20)

    preferred_language = models.CharField(max_length=2, choices=Language.choices, blank=True)
    immigration_status = models.CharField(max_length=20, choices=ImmigrationStatus.choices, blank=True)
    household_income = models.PositiveIntegerField(null=True, blank=True, help_text="Annual, USD")

    # Set only by the Twilio STOP webhook (ADR-0009). Never on the intake form.
    sms_opt_out = models.BooleanField(default=False)
    sms_opt_out_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta(ArchivableModel.Meta):
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["phone_primary"]),
            models.Index(fields=["phone_secondary"]),
            models.Index(fields=["last_name", "date_of_birth"]),
        ]

    def __str__(self):
        return " ".join(p for p in (self.first_name, self.last_name) if p) or f"Customer #{self.pk}"

    def save(self, *args, **kwargs):
        for field in self.PHONE_FIELDS:
            setattr(self, field, normalize_phone(getattr(self, field)))
        super().save(*args, **kwargs)

    def missing_items(self):
        """What the completeness checklist on the record page shows."""
        missing = []
        if not (self.first_name and self.last_name):
            missing.append("Full name")
        if not self.date_of_birth:
            missing.append("Date of birth")
        if not self.phone_primary:
            missing.append("Primary phone")
        elif not is_us_phone(self.phone_primary):
            missing.append("Primary phone is not a 10-digit US number")
        if not (self.res_street and self.res_city and self.res_zip):
            missing.append("Residential address")
        if not self.preferred_language:
            missing.append("Preferred language")
        if not self.immigration_status:
            missing.append("Immigration status")
        if self.household_income is None:
            missing.append("Household income")
        if self.pk and not self.documents.exists():
            missing.append("Health plan document in the Vault")
        return missing


class HouseholdMember(ArchivableModel):
    """A spouse or dependent. One entity with a relationship field (CONTEXT.md)."""

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="household_members")
    relationship = models.CharField(max_length=10, choices=Relationship.choices)
    first_name = _text()
    middle_name = _text()
    last_name = _text()
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = _text(20)
    immigration_status = models.CharField(max_length=20, choices=ImmigrationStatus.choices, blank=True)
    public_coverage = models.CharField(max_length=10, choices=PublicCoverage.choices, blank=True)
    linked_customer = models.ForeignKey(
        Customer, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(ArchivableModel.Meta):
        ordering = ["relationship", "date_of_birth"]

    def __str__(self):
        name = " ".join(p for p in (self.first_name, self.last_name) if p) or "Unnamed"
        return f"{name} ({self.get_relationship_display()})"

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)
