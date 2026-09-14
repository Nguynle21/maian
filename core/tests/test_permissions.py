import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied

from core.archive import archive
from core.models import AuditEvent
from core.roles import ADMIN_GROUP, STAFF_GROUP, is_admin
from customers.models import Customer, HouseholdMember, Relationship


def test_anonymous_user_is_sent_to_login(client, db):
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"].startswith("/account/login/")


def test_logged_in_user_without_2fa_is_sent_to_setup(client, make_user):
    user = make_user("staff@example.com", STAFF_GROUP)
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/account/two_factor/setup/"


def test_role_helper(make_user):
    assert is_admin(make_user("admin@example.com", ADMIN_GROUP))
    assert not is_admin(make_user("staff@example.com", STAFF_GROUP))


def test_staff_cannot_open_django_admin(make_user, login_verified):
    client = login_verified(make_user("staff@example.com", STAFF_GROUP))
    response = client.get(f"/{settings.ADMIN_PATH}")
    assert response.status_code != 200


def test_staff_cannot_open_user_management(make_user, login_verified):
    client = login_verified(make_user("staff@example.com", STAFF_GROUP))
    response = client.get(f"/{settings.ADMIN_PATH}core/user/")
    assert response.status_code != 200


def test_staff_cannot_archive_customer_in_code(make_user):
    staff = make_user("staff@example.com", STAFF_GROUP)
    customer = Customer.objects.create(first_name="Lan")
    with pytest.raises(PermissionDenied):
        archive(customer, staff)
    assert Customer.objects.filter(pk=customer.pk).exists()
    assert not AuditEvent.objects.exists()


def test_admin_archive_hides_customer_and_logs_it(make_user):
    admin_user = make_user("admin@example.com", ADMIN_GROUP)
    customer = Customer.objects.create(first_name="Lan")
    archive(customer, admin_user)
    assert not Customer.objects.filter(pk=customer.pk).exists()
    assert Customer.all_objects.filter(pk=customer.pk).exists()
    event = AuditEvent.objects.get()
    assert (event.actor, event.action, event.target_type, event.target_id) == (
        admin_user, AuditEvent.Action.ARCHIVE, "customer", str(customer.pk)
    )


def test_staff_cannot_archive_household_member_in_code(make_user):
    staff = make_user("staff@example.com", STAFF_GROUP)
    customer = Customer.objects.create(first_name="Lan")
    member = HouseholdMember.objects.create(customer=customer, relationship=Relationship.SPOUSE)
    with pytest.raises(PermissionDenied):
        archive(member, staff)


def test_audit_events_cannot_be_changed_or_removed_in_bulk(make_user):
    admin_user = make_user("admin@example.com", ADMIN_GROUP)
    archive(Customer.objects.create(first_name="Lan"), admin_user)
    with pytest.raises(ValueError):
        AuditEvent.objects.all().update(detail="edited")
    with pytest.raises(ValueError):
        AuditEvent.objects.all().delete()
    assert AuditEvent.objects.get().detail == ""
