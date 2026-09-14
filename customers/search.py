import re
from datetime import datetime

from django.db.models import Q

from customers.models import Customer
from customers.phones import normalize_phone

DATE_FORMATS = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y")


def _parse_date(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def search_customers(query):
    """One search box: a date searches DOB, digits search both phones, words search names."""
    query = (query or "").strip()
    customers = Customer.objects.all()
    if not query:
        return customers.order_by("-updated_at")[:50]

    dob = _parse_date(query)
    if dob:
        return customers.filter(date_of_birth=dob)

    if not re.search(r"[^\d\s().+-]", query):
        digits = normalize_phone(query)
        if len(digits) >= 4:
            return customers.filter(Q(phone_primary__contains=digits) | Q(phone_secondary__contains=digits))

    condition = Q()
    for term in query.split():
        condition &= (
            Q(first_name__unaccent__icontains=term)
            | Q(middle_name__unaccent__icontains=term)
            | Q(last_name__unaccent__icontains=term)
        )
    return customers.filter(condition)[:100]
