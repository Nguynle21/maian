import pytest
from django.contrib.auth.models import Group
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import User


@pytest.fixture
def make_user(db):
    def _make(email, group):
        user = User.objects.create_user(email=email, password="pw-for-tests-only-123")
        user.groups.add(Group.objects.get(name=group))
        return user

    return _make


@pytest.fixture
def login_verified(client):
    """Log a user in as if they had passed the 2FA step."""

    def _login(user):
        device = TOTPDevice.objects.create(user=user, name="test", confirmed=True)
        client.force_login(user)
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()
        return client

    return _login
