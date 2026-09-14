from django.conf import settings

from core.roles import ADMIN_GROUP, STAFF_GROUP, is_admin


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
