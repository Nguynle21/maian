import logging
from datetime import date

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.archive import archive
from customers.duplicates import find_possible_duplicates
from customers.forms import CustomerForm, DependentFormSet, SpouseFormSet
from customers.models import Customer, HouseholdMember, Relationship
from customers.search import search_customers
from vault.forms import VaultUploadForm
from vault.services import store_document

logger = logging.getLogger(__name__)


def customer_list(request):
    query = request.GET.get("q", "")
    return render(request, "customers/list.html", {"customers": search_customers(query), "query": query})


def customer_new(request):
    return _intake(request, Customer())


def customer_edit(request, pk):
    return _intake(request, get_object_or_404(Customer, pk=pk))


def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    duplicates = find_possible_duplicates(
        phones=[customer.phone_primary, customer.phone_secondary],
        last_name=customer.last_name,
        date_of_birth=customer.date_of_birth,
        exclude_pk=customer.pk,
    )
    return render(request, "customers/detail.html", {
        "customer": customer,
        "documents": [],
        "missing": customer.missing_items(),
        "duplicates": duplicates,
        "upload_form": VaultUploadForm(),
    })


@require_POST
def duplicates_check(request):
    """HTMX partial for the live duplicate warning. POST keeps phone and DOB out of access logs."""
    try:
        dob = date.fromisoformat(request.POST.get("date_of_birth", ""))
    except ValueError:
        dob = None
    exclude = request.GET.get("exclude", "")
    matches = find_possible_duplicates(
        phones=[request.POST.get("phone_primary"), request.POST.get("phone_secondary")],
        last_name=request.POST.get("last_name", ""),
        date_of_birth=dob,
        exclude_pk=int(exclude) if exclude.isdigit() else None,
    )
    return render(request, "customers/_duplicates.html", {"duplicates": matches})


@require_POST
def customer_archive(request, pk):
    archive(get_object_or_404(Customer, pk=pk), request.user)
    messages.success(request, "Customer archived.")
    return redirect("customers:list")


@require_POST
def member_archive(request, pk):
    member = get_object_or_404(HouseholdMember, pk=pk)
    archive(member, request.user)
    messages.success(request, "Household member archived.")
    return redirect("customers:detail", pk=member.customer_id)


def _members(customer, relationship):
    if customer.pk is None:
        return HouseholdMember.objects.none()
    return HouseholdMember.objects.filter(customer=customer, relationship=relationship)


def _intake(request, customer):
    is_new = customer.pk is None
    data = request.POST if request.method == "POST" else None
    files = request.FILES if request.method == "POST" else None

    form = CustomerForm(data, instance=customer)
    spouse_formset = SpouseFormSet(
        data, instance=customer, prefix="spouse", queryset=_members(customer, Relationship.SPOUSE)
    )
    dependent_formset = DependentFormSet(
        data, instance=customer, prefix="dependents", queryset=_members(customer, Relationship.DEPENDENT)
    )
    upload_form = VaultUploadForm(data, files)

    if request.method == "POST":
        valid = [form.is_valid(), spouse_formset.is_valid(), dependent_formset.is_valid()]
        if all(valid):
            with transaction.atomic():
                customer = form.save(commit=False)
                if is_new:
                    customer.created_by = request.user
                customer.save()
                _save_members(spouse_formset, customer, Relationship.SPOUSE)
                _save_members(dependent_formset, customer, Relationship.DEPENDENT)
            messages.success(request, "Saved.")
            _handle_upload(request, upload_form, customer)
            return redirect("customers:detail", pk=customer.pk)
        messages.error(request, "Some fields need fixing. Nothing was saved yet.")

    return render(request, "customers/form.html", {
        "customer": customer,
        "is_new": is_new,
        "form": form,
        "spouse_formset": spouse_formset,
        "dependent_formset": dependent_formset,
        "upload_form": upload_form,
    })


def _save_members(formset, customer, relationship):
    formset.instance = customer
    for member in formset.save(commit=False):
        member.customer = customer
        member.relationship = relationship
        member.save()


def _handle_upload(request, upload_form, customer):
    """The Customer is already saved; a bad or failed upload must not lose that."""
    if not request.FILES.get("file"):
        return
    if not upload_form.is_valid():
        messages.error(request, "Document not uploaded: " + " ".join(upload_form.errors.get("file", [])))
        return
    try:
        store_document(customer, upload_form.cleaned_data["file"], request.user)
    except Exception:
        logger.exception("Vault upload failed for customer %s", customer.pk)
        messages.error(request, "Customer saved, but the document upload failed. Try again from this page.")
