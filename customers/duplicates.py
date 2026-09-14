from django.db.models import Q

from customers.models import Customer
from customers.phones import is_us_phone, normalize_phone


def find_possible_duplicates(*, phones, last_name, date_of_birth, exclude_pk=None):
    """Existing Customers who might be the same person. A warning, never a block."""
    numbers = {normalize_phone(p) for p in phones if p}
    numbers = {n for n in numbers if is_us_phone(n)}

    condition = Q()
    if numbers:
        condition |= Q(phone_primary__in=numbers) | Q(phone_secondary__in=numbers)
    if last_name and date_of_birth:
        condition |= Q(last_name__unaccent__iexact=last_name.strip(), date_of_birth=date_of_birth)
    if not condition:
        return Customer.objects.none()

    matches = Customer.objects.filter(condition)
    if exclude_pk:
        matches = matches.exclude(pk=exclude_pk)
    return matches[:5]
