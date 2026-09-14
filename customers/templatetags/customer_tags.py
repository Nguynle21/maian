from django import template

from customers.phones import format_phone

register = template.Library()


@register.filter
def phone(value):
    return format_phone(value)
