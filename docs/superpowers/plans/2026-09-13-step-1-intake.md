# Step 1: Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Staff can log in with 2FA, enter a Customer with spouse and dependents, attach documents to the Vault, search, and see duplicate warnings. Admin can archive.

**Architecture:** One Django project (`maian`) with three apps. `core` holds the user, roles, archive, and audit pieces. `customers` holds Customer and Household Member, intake, search, and duplicates. `vault` holds document storage. Pages are rendered on the server. HTMX is used in one place, the live duplicate warning. A single middleware requires a 2FA-verified session on every page, so new views are protected by default.

**Tech Stack:** Python 3.14, Django 5.2 LTS, PostgreSQL, django-two-factor-auth, django-axes, django-storages (S3 API → Cloudflare R2), whitenoise, gunicorn, htmx 2.0.4 (vendored), pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-09-13-intake-and-send-design.md`

## Global Constraints

- Vocabulary from `CONTEXT.md`: Customer, Household Member, Vault, Archive. Never "client", "lead", "contact", "delete".
- Nothing is hard-deleted. Archivable models filter `archived_at` in the default manager.
- No SSN or card-number fields, anywhere.
- Almost every field is optional. Save never refuses incomplete data; a checklist on the record shows what's missing.
- Only the Admin role archives. Both roles see and edit all Customers.
- No new services, queues, caches, or JS build steps. Dependencies are exactly those listed in `requirements.txt` below.
- Secrets come only from environment variables. `.env` is gitignored. Real customer data is never used locally.
- Tests cover only permissions in this step (ADR-0014). Templates and forms are not tested.
- Timezone `America/Chicago`.
- Vault accepts `.pdf .jpg .jpeg .png` only, 10 MB max, stored under a random key, downloaded with `Content-Disposition: attachment`, presigned links expire after 300 seconds.

## File map

```
requirements.txt, requirements-dev.txt, pytest.ini, .env.example, manage.py, conftest.py
maian/settings.py, urls.py, wsgi.py
core/models.py        User, ArchivableModel, AuditEvent
core/roles.py         ADMIN_GROUP, STAFF_GROUP, is_admin()
core/archive.py       archive(), restore()
core/middleware.py    RequireVerifiedMiddleware
core/context_processors.py
core/admin.py         User admin with audit logging
core/migrations/0002_groups.py
core/tests/test_permissions.py
customers/models.py   Customer, HouseholdMember, choices, missing_items()
customers/phones.py   normalize_phone(), format_phone()
customers/forms.py    CustomerForm, SpouseForm, DependentForm, formsets
customers/search.py   search_customers()
customers/duplicates.py find_possible_duplicates()
customers/views.py, urls.py, admin.py
customers/templatetags/customer_tags.py
customers/management/commands/seed.py
vault/models.py, forms.py, services.py, views.py, urls.py, admin.py
templates/base.html, templates/two_factor/_base.html, templates/customers/*.html
static/app.css, static/htmx.min.js
docs/deploy.md, .github/dependabot.yml, build.sh
```

---

### Task 1: Project skeleton, settings, custom User

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.env.example`, `manage.py`, `maian/__init__.py`, `maian/settings.py`, `maian/urls.py`, `maian/wsgi.py`, `core/__init__.py`, `core/apps.py`, `core/models.py`, `static/app.css`, `static/htmx.min.js`, `templates/base.html`
- Modify: `.gitignore` (add `.vault-dev/`)

**Interfaces:**
- Produces: `core.User` (email login, no username); `settings.ADMIN_PATH`; storage alias `"vault"`; `templates/base.html` with blocks `title` and `content`.

- [ ] **Step 1: Local PostgreSQL (user action).** Install PostgreSQL with Postgres.app or `brew install postgresql@17 && brew services start postgresql@17`, then run `createdb maian`.

- [ ] **Step 2: Write requirements**

`requirements.txt`:
```
Django==5.2.17
psycopg[binary]==3.3.5
dj-database-url==3.1.2
django-two-factor-auth==1.18.1
django-axes==8.3.1
django-storages[s3]==1.14.6
boto3==1.43.93
whitenoise==6.12.0
gunicorn==26.2.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest==9.1.1
pytest-django==4.14.0
```

`pytest.ini`:
```ini
[pytest]
DJANGO_SETTINGS_MODULE = maian.settings
python_files = test_*.py
addopts = -q
```

`.env.example`:
```
# Copy to .env for local development. Never commit .env.
DEBUG=1
SECRET_KEY=dev-only-not-secret
DATABASE_URL=postgres://localhost/maian
ALLOWED_HOSTS=localhost,127.0.0.1
ADMIN_PATH=dev-admin/
# Leave R2_BUCKET empty locally: Vault files go to .vault-dev/
R2_BUCKET=
R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
```

- [ ] **Step 3: Create venv and install**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cp .env.example .env`

Expected: installs without error.

- [ ] **Step 4: Write `manage.py`, `maian/wsgi.py`, `maian/__init__.py` (empty), `core/__init__.py` (empty)**

`manage.py`:
```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maian.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

`maian/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "maian.settings")
application = get_wsgi_application()
```

- [ ] **Step 5: Write `maian/settings.py`**

```python
"""Settings for Maian. Every secret comes from an environment variable.

Locally, variables are read from .env (see .env.example). In production, the
hosting platform sets them. There is one settings file; DEBUG decides the rest.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


DEBUG = env("DEBUG", "0") == "1"
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]
ADMIN_PATH = env("ADMIN_PATH", "dev-admin/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "axes",
    "core",
    "customers",
    "vault",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware.RequireVerifiedMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "maian.urls"
WSGI_APPLICATION = "maian.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.roles",
            ],
        },
    },
]

DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"), conn_max_age=600)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth (ADR-0012) ---
AUTH_USER_MODEL = "core.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "customers:list"
LOGOUT_REDIRECT_URL = "two_factor:login"
SESSION_COOKIE_AGE = 12 * 60 * 60  # 12 hours absolute, no idle timeout
SESSION_SAVE_EVERY_REQUEST = False
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(hours=1)
AXES_LOCKOUT_PARAMETERS = ["username"]  # the whole office shares one IP
AXES_RESET_ON_SUCCESS = True
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Vault storage (ADR-0007) ---
if env("R2_BUCKET", ""):
    VAULT_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env("R2_BUCKET"),
            "endpoint_url": env("R2_ENDPOINT_URL"),
            "access_key": env("R2_ACCESS_KEY_ID"),
            "secret_key": env("R2_SECRET_ACCESS_KEY"),
            "region_name": "auto",
            "signature_version": "s3v4",
            "querystring_expire": 300,
            "file_overwrite": False,
            "default_acl": None,
        },
    }
elif DEBUG:
    VAULT_STORAGE = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": BASE_DIR / ".vault-dev"},
    }
else:
    raise RuntimeError("R2_BUCKET must be set when DEBUG is off")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "vault": VAULT_STORAGE,
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# --- Production hardening (docs/security-baseline.md) ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

In tests, whitenoise's manifest storage fails without `collectstatic`. Add this at the bottom of settings:
```python
import sys

if "pytest" in sys.modules:
    STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
```

- [ ] **Step 6: Write `core/apps.py` and `core/models.py` (User only for now)**

`core/apps.py`:
```python
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
```

`core/models.py`:
```python
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Staff login. Email instead of username. Deactivate, never archive or remove (ADR-0012)."""

    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.email
```

- [ ] **Step 7: Temporary stubs so `check` passes.** Create `customers/__init__.py`, `customers/apps.py` (`name = "customers"`), `vault/__init__.py`, `vault/apps.py` (`name = "vault"`), `core/middleware.py`, `core/context_processors.py`, and `maian/urls.py`. They're filled in by later tasks.

`core/middleware.py` (stub, replaced in Task 2):
```python
class RequireVerifiedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
```

`core/context_processors.py` (stub, replaced in Task 2):
```python
def roles(request):
    return {}
```

`maian/urls.py` (stub):
```python
from django.conf import settings
from django.contrib import admin
from django.urls import path

urlpatterns = [path(settings.ADMIN_PATH, admin.site.urls)]
```

- [ ] **Step 8: Static files and base template**

Run: `mkdir -p static templates && curl -sSfo static/htmx.min.js https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js`

`templates/base.html`:
```html
{% load static %}<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Maian{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'app.css' %}">
  <script src="{% static 'htmx.min.js' %}" defer></script>
</head>
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% if user.is_authenticated %}
  <header class="topbar">
    <a class="brand" href="{% url 'customers:list' %}">Maian</a>
    <nav>
      <a href="{% url 'customers:list' %}">Customers</a>
      <a href="{% url 'customers:new' %}">New customer</a>
      {% if is_admin and user.is_staff %}<a href="/{{ admin_path }}">Admin</a>{% endif %}
    </nav>
    <form method="post" action="{% url 'logout' %}" class="logout">
      {% csrf_token %}<span>{{ user.email }}</span> <button type="submit" class="link">Log out</button>
    </form>
  </header>
  {% endif %}
  <main>
    {% for message in messages %}<p class="flash {{ message.tags }}">{{ message }}</p>{% endfor %}
    {% block main %}{% block content %}{% endblock %}{% endblock %}
  </main>
</body>
</html>
```

`static/app.css`:
```css
:root { --ink:#1d2330; --muted:#5b6475; --line:#d7dbe3; --bg:#f6f7f9; --accent:#1f5fbf; --warn:#fff4d6; --warn-line:#e0b43c; --bad:#b3261e; --good:#1e7a3c; }
* { box-sizing: border-box; }
body { margin:0; font: 16px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }
a { color:var(--accent); }
.topbar { display:flex; gap:1.5rem; align-items:center; padding:.6rem 1.25rem; background:#fff; border-bottom:1px solid var(--line); }
.topbar nav { display:flex; gap:1rem; flex:1; }
.brand { font-weight:700; text-decoration:none; color:var(--ink); }
.logout span { color:var(--muted); font-size:.9rem; }
main { max-width: 980px; margin: 1.25rem auto; padding: 0 1.25rem; }
h1 { font-size:1.5rem; margin:.25rem 0 1rem; }
h2 { font-size:1.15rem; margin:1.25rem 0 .5rem; }
.flash { padding:.6rem .8rem; border-radius:6px; background:#e8f1ff; }
.flash.error { background:#fde8e7; color:var(--bad); }
.flash.success { background:#e6f4ea; color:var(--good); }
.card { background:#fff; border:1px solid var(--line); border-radius:8px; padding:1rem 1.25rem; margin-bottom:1rem; }
details.card > summary { font-weight:600; cursor:pointer; font-size:1.05rem; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap:.75rem 1rem; margin-top:.75rem; }
.field label { display:block; font-size:.85rem; color:var(--muted); margin-bottom:.2rem; }
.field input, .field select { width:100%; padding:.45rem .55rem; font-size:1rem; border:1px solid var(--line); border-radius:6px; background:#fff; }
.field .errorlist { color:var(--bad); margin:.2rem 0 0; padding:0; list-style:none; font-size:.85rem; }
.member { border-top:1px dashed var(--line); padding-top:.75rem; margin-top:.75rem; }
button, .button { font:inherit; padding:.5rem 1rem; border-radius:6px; border:1px solid var(--accent); background:var(--accent); color:#fff; cursor:pointer; text-decoration:none; display:inline-block; }
button.secondary { background:#fff; color:var(--accent); }
button.danger { background:#fff; color:var(--bad); border-color:var(--bad); }
button.link { background:none; border:none; color:var(--accent); padding:0; }
.actions { position:sticky; bottom:0; background:var(--bg); padding:.75rem 0; display:flex; gap:.75rem; }
.warning { background:var(--warn); border:1px solid var(--warn-line); border-radius:8px; padding:.6rem .9rem; margin-bottom:1rem; }
.checklist li { color:var(--bad); }
.checklist.complete { color:var(--good); }
table { width:100%; border-collapse:collapse; background:#fff; }
th, td { text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--line); }
th { font-size:.85rem; color:var(--muted); font-weight:600; }
.search { display:flex; gap:.5rem; margin-bottom:1rem; }
.search input { flex:1; padding:.55rem .7rem; font-size:1.05rem; border:1px solid var(--line); border-radius:6px; }
dl.facts { display:grid; grid-template-columns: max-content 1fr; gap:.3rem 1rem; margin:0; }
dl.facts dt { color:var(--muted); }
dl.facts dd { margin:0; }
.muted { color:var(--muted); }
```

- [ ] **Step 9: Add `.vault-dev/` to `.gitignore`, make migrations, migrate**

Run: `.venv/bin/python manage.py makemigrations core && .venv/bin/python manage.py migrate && .venv/bin/python manage.py check`

Expected: `System check identified no issues`. Templates that reference `customers:list` are not rendered yet, so `check` passes.

- [ ] **Step 10: Commit**

```bash
git add -A && git commit -m "Scaffold Django project with email login user and env-based settings"
```

---

### Task 2: 2FA enforcement and roles

**Files:**
- Modify: `core/middleware.py`, `core/context_processors.py`, `maian/urls.py`
- Create: `core/roles.py`, `core/migrations/0002_groups.py`, `templates/two_factor/_base.html`, `conftest.py`, `core/tests/__init__.py`, `core/tests/test_permissions.py`

**Interfaces:**
- Consumes: `core.User`
- Produces: `core.roles.is_admin(user) -> bool`, `ADMIN_GROUP = "Admin"`, `STAFF_GROUP = "Staff"`; pytest fixtures `make_user(email, group) -> User` and `login_verified(user) -> Client`; template variables `is_admin` and `admin_path`.

- [ ] **Step 1: Write the fixtures and failing tests**

`conftest.py`:
```python
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
```

`core/tests/test_permissions.py`:
```python
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
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/bin/pytest core/tests/test_permissions.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.roles'`.

- [ ] **Step 3: Implement roles, groups migration, middleware, context processor, and URLs**

`core/roles.py`:
```python
"""The two roles (ADR-0012). Both see and edit every Customer; only Admin archives,
exports, and manages users. Roles are plain Django groups."""

ADMIN_GROUP = "Admin"
STAFF_GROUP = "Staff"


def is_admin(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()
```

`core/migrations/0002_groups.py`:
```python
from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ("Admin", "Staff"):
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]
```

`core/middleware.py`:
```python
from urllib.parse import quote

from django.shortcuts import redirect


class RequireVerifiedMiddleware:
    """Every page requires a logged-in user who passed 2FA in this session.

    New views are protected without anyone remembering a decorator. The only
    exceptions are listed here, in one place.
    """

    OPEN_PREFIXES = ("/account/login/", "/static/")
    SETUP_PREFIXES = ("/account/two_factor/setup/", "/account/two_factor/qrcode/", "/account/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(self.OPEN_PREFIXES):
            return self.get_response(request)
        if not request.user.is_authenticated:
            return redirect(f"/account/login/?next={quote(path)}")
        if not request.user.is_verified():
            if path.startswith(self.SETUP_PREFIXES):
                return self.get_response(request)
            return redirect("/account/two_factor/setup/")
        return self.get_response(request)
```

`core/context_processors.py`:
```python
from django.conf import settings

from core.roles import is_admin


def roles(request):
    return {"is_admin": is_admin(request.user), "admin_path": settings.ADMIN_PATH}
```

`maian/urls.py`:
```python
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path
from two_factor.urls import urlpatterns as two_factor_urls

urlpatterns = [
    path("", include(two_factor_urls)),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path(settings.ADMIN_PATH, admin.site.urls),
    path("vault/", include("vault.urls")),
    path("", include("customers.urls")),
]
```

Task 2 can't resolve `customers.urls` or `vault.urls` yet, so create minimal stubs. `customers/urls.py`:
```python
from django.http import HttpResponse
from django.urls import path

app_name = "customers"
urlpatterns = [
    path("", lambda request: HttpResponse("Customers"), name="list"),
    path("customers/new/", lambda request: HttpResponse("New"), name="new"),
]
```
`vault/urls.py`:
```python
app_name = "vault"
urlpatterns = []
```

`templates/two_factor/_base.html` (so 2FA pages use our layout). two_factor's `_base_focus.html` overrides `content_wrapper` and nests `content` inside it, so this template must offer both. It overrides `main` from `base.html`, which means `content` appears only once in this file:
```html
{% extends "base.html" %}
{% block main %}<div class="card" style="max-width:480px;margin:2rem auto">{% block content_wrapper %}{% block content %}{% endblock %}{% endblock %}</div>{% endblock %}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python manage.py migrate && .venv/bin/pytest core/tests/test_permissions.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Require 2FA-verified session on every page; add Admin and Staff roles"
```

---

### Task 3: Archive, audit, Customer and Household Member models

**Files:**
- Modify: `core/models.py`, `core/tests/test_permissions.py`
- Create: `core/archive.py`, `core/admin.py`, `customers/models.py`, `customers/phones.py`, `customers/admin.py`

**Interfaces:**
- Consumes: `is_admin`
- Produces: `core.models.ArchivableModel` (managers `objects` = active only, `all_objects` = everything), `core.models.AuditEvent` with `Action` choices, `core.archive.archive(obj, user)` and `restore(obj, user)`, which raise `PermissionDenied` for non-Admin. Also `customers.models.Customer`, `HouseholdMember`, choice classes `Gender`, `ImmigrationStatus`, `Language`, `Relationship`, `PublicCoverage`, `Customer.missing_items() -> list[str]`, `Customer.PHONE_FIELDS`, and `customers.phones.normalize_phone(str) -> str`, `format_phone(str) -> str`, `is_us_phone(str) -> bool`.

- [ ] **Step 1: Write the failing tests** (append to `core/tests/test_permissions.py`)

```python
import pytest
from django.core.exceptions import PermissionDenied

from core.archive import archive
from core.models import AuditEvent
from customers.models import Customer, HouseholdMember, Relationship


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
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/bin/pytest core/tests/test_permissions.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.archive'`.

- [ ] **Step 3: Add `ArchivableModel` and `AuditEvent` to `core/models.py`** (below `User`)

```python
class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class ArchivableModel(models.Model):
    """Soft delete (ADR-0011). `objects` hides archived rows everywhere by default;
    `all_objects` is for Django admin and restore only."""

    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"


class AuditEvent(models.Model):
    """Append-only record of meaningful actions (ADR-0010). Never updated or removed."""

    class Action(models.TextChoices):
        ARCHIVE = "archive"
        RESTORE = "restore"
        USER_CREATED = "user_created"
        USER_CHANGED = "user_changed"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=40, choices=Action.choices)
    target_type = models.CharField(max_length=50)
    target_id = models.CharField(max_length=50)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditEvent rows are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditEvent rows are append-only")
```

- [ ] **Step 4: Write `core/archive.py`**

```python
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from core.models import AuditEvent
from core.roles import is_admin


def archive(obj, user):
    """Hide a record everywhere. Admin only; checked here so no view can forget."""
    if not is_admin(user):
        raise PermissionDenied("Only Admin can archive records.")
    obj.archived_at = timezone.now()
    obj.archived_by = user
    obj.save(update_fields=["archived_at", "archived_by"])
    _log(user, AuditEvent.Action.ARCHIVE, obj)


def restore(obj, user):
    if not is_admin(user):
        raise PermissionDenied("Only Admin can restore records.")
    obj.archived_at = None
    obj.archived_by = None
    obj.save(update_fields=["archived_at", "archived_by"])
    _log(user, AuditEvent.Action.RESTORE, obj)


def _log(user, action, obj):
    AuditEvent.objects.create(
        actor=user, action=action, target_type=obj._meta.model_name, target_id=str(obj.pk)
    )
```

- [ ] **Step 5: Write `customers/phones.py`**

```python
import re


def normalize_phone(raw):
    """'(281) 555-0100' and '+1 281.555.0100' both become '2815550100'.

    Anything that is not a 10-digit US number comes back as its bare digits, so
    nothing staff typed is lost. The record checklist flags it.
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def is_us_phone(digits):
    return len(digits or "") == 10


def format_phone(digits):
    if is_us_phone(digits):
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits or ""
```

- [ ] **Step 6: Write `customers/models.py`**

```python
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
```

`missing_items` references `self.documents`, which Task 5 creates. Until then, write that line as `if self.pk and hasattr(self, "documents") and not self.documents.exists():`. Task 5 removes the `hasattr` guard.

- [ ] **Step 7: Admin registrations**

`core/admin.py`:
```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.models import AuditEvent, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Name", {"fields": ("first_name", "last_name")}),
        ("Access", {"fields": ("is_active", "is_staff", "groups")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "groups", "is_staff")}),)

    def has_delete_permission(self, request, obj=None):
        return False  # deactivate, never remove (ADR-0012)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action=AuditEvent.Action.USER_CHANGED if change else AuditEvent.Action.USER_CREATED,
            target_type="user",
            target_id=str(obj.pk),
            detail=", ".join(form.changed_data)[:255],
        )


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id", "detail"]
    list_filter = ["action", "target_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

`customers/admin.py`:
```python
from django.contrib import admin, messages

from core.archive import restore
from customers.models import Customer, HouseholdMember


class ArchivableAdmin(admin.ModelAdmin):
    """Admin sees archived rows too, and can restore them. Nothing can be removed."""

    actions = ["restore_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Restore selected archived records")
    def restore_selected(self, request, queryset):
        for obj in queryset.filter(archived_at__isnull=False):
            restore(obj, request.user)
        messages.success(request, "Restored.")


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    fk_name = "customer"
    extra = 0
    can_delete = False


@admin.register(Customer)
class CustomerAdmin(ArchivableAdmin):
    list_display = ["last_name", "first_name", "date_of_birth", "phone_primary", "sms_opt_out", "archived_at"]
    search_fields = ["last_name", "first_name", "phone_primary", "phone_secondary"]
    list_filter = ["preferred_language", "sms_opt_out"]
    inlines = [HouseholdMemberInline]


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(ArchivableAdmin):
    list_display = ["last_name", "first_name", "relationship", "customer", "archived_at"]
```

- [ ] **Step 8: Migrate and run tests**

Run: `.venv/bin/python manage.py makemigrations core customers && .venv/bin/python manage.py migrate && .venv/bin/pytest`
Expected: 8 passed.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "Add Customer, Household Member, soft-delete archive with audit log"
```

---

### Task 4: Intake form, record page, search, duplicate warning

**Files:**
- Create: `customers/forms.py`, `customers/search.py`, `customers/duplicates.py`, `customers/views.py`, `customers/templatetags/__init__.py`, `customers/templatetags/customer_tags.py`, `templates/customers/list.html`, `templates/customers/form.html`, `templates/customers/detail.html`, `templates/customers/_duplicates.html`, `templates/customers/_field.html`
- Modify: `customers/urls.py` (replace stub), `core/tests/test_permissions.py`

**Interfaces:**
- Consumes: `Customer`, `HouseholdMember`, `archive`, `normalize_phone`, `format_phone`
- Produces: URL names `customers:list`, `customers:new`, `customers:detail(pk)`, `customers:edit(pk)`, `customers:duplicates`, `customers:archive(pk)`, `customers:member_archive(pk)`. `search_customers(query) -> QuerySet`, `find_possible_duplicates(*, phones, last_name, date_of_birth, exclude_pk=None) -> QuerySet`. Template filter `phone`. Task 5 adds the Vault section to `form.html` and `detail.html`, and the intake view calls `vault.services.store_document` and `vault.forms.VaultUploadForm`.

- [ ] **Step 1: Write the failing tests** (append; these are view-level permission tests)

```python
def test_staff_gets_403_archiving_customer_through_the_page(make_user, login_verified):
    client = login_verified(make_user("staff@example.com", STAFF_GROUP))
    customer = Customer.objects.create(first_name="Lan")
    response = client.post(f"/customers/{customer.pk}/archive/")
    assert response.status_code == 403
    assert Customer.objects.filter(pk=customer.pk).exists()


def test_staff_gets_403_archiving_member_through_the_page(make_user, login_verified):
    client = login_verified(make_user("staff@example.com", STAFF_GROUP))
    customer = Customer.objects.create(first_name="Lan")
    member = HouseholdMember.objects.create(customer=customer, relationship=Relationship.DEPENDENT)
    response = client.post(f"/customers/members/{member.pk}/archive/")
    assert response.status_code == 403
    assert HouseholdMember.objects.filter(pk=member.pk).exists()


def test_staff_can_open_intake_and_record(make_user, login_verified):
    client = login_verified(make_user("staff@example.com", STAFF_GROUP))
    customer = Customer.objects.create(first_name="Lan")
    assert client.get("/customers/new/").status_code == 200
    assert client.get(f"/customers/{customer.pk}/").status_code == 200
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/bin/pytest core/tests/test_permissions.py`
Expected: the 3 new tests FAIL (404 / stub responses).

- [ ] **Step 3: Write `customers/forms.py`**

```python
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
```

- [ ] **Step 4: Write `customers/search.py` and `customers/duplicates.py`**

`customers/search.py`:
```python
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
```

`customers/duplicates.py`:
```python
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
```

- [ ] **Step 5: Add `unaccent` extension migration**

Run: `.venv/bin/python manage.py makemigrations customers --empty -n unaccent`, then edit the file:
```python
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("customers", "0001_initial")]
    operations = [UnaccentExtension()]
```

- [ ] **Step 6: Write `customers/templatetags/customer_tags.py`**

```python
from django import template

from customers.phones import format_phone

register = template.Library()


@register.filter
def phone(value):
    return format_phone(value)
```

- [ ] **Step 7: Write `customers/views.py`**

```python
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
        "documents": customer.documents.all(),
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
    matches = find_possible_duplicates(
        phones=[request.POST.get("phone_primary"), request.POST.get("phone_secondary")],
        last_name=request.POST.get("last_name", ""),
        date_of_birth=dob,
        exclude_pk=request.GET.get("exclude") or None,
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
```

- [ ] **Step 8: Write `customers/urls.py`** (replaces stub)

```python
from django.urls import path

from customers import views

app_name = "customers"
urlpatterns = [
    path("", views.customer_list, name="list"),
    path("customers/new/", views.customer_new, name="new"),
    path("customers/duplicates/", views.duplicates_check, name="duplicates"),
    path("customers/<int:pk>/", views.customer_detail, name="detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="edit"),
    path("customers/<int:pk>/archive/", views.customer_archive, name="archive"),
    path("customers/members/<int:pk>/archive/", views.member_archive, name="member_archive"),
]
```

- [ ] **Step 9: Write templates**

`templates/customers/_field.html`:
```html
<div class="field">{{ field.label_tag }}{{ field }}{{ field.errors }}</div>
```

`templates/customers/_duplicates.html`:
```html
{% load customer_tags %}{% if duplicates %}
<div class="warning">
  <strong>Possible duplicate.</strong> Check before continuing:
  <ul>{% for c in duplicates %}
    <li><a href="{% url 'customers:detail' c.pk %}" target="_blank">{{ c }}</a> · DOB {{ c.date_of_birth|default:"—" }} · {{ c.phone_primary|phone|default:"no phone" }}</li>
  {% endfor %}</ul>
</div>
{% endif %}
```

`templates/customers/list.html`:
```html
{% extends "base.html" %}{% load customer_tags %}
{% block title %}Customers · Maian{% endblock %}
{% block content %}
<h1>Customers</h1>
<form class="search" method="get">
  <input type="search" name="q" value="{{ query }}" placeholder="Name, phone, or date of birth (MM/DD/YYYY)" autofocus>
  <button type="submit">Search</button>
</form>
{% if not query %}<p class="muted">Recently updated</p>{% endif %}
<table>
  <thead><tr><th>Name</th><th>Date of birth</th><th>Primary phone</th><th>Language</th></tr></thead>
  <tbody>
  {% for c in customers %}
    <tr>
      <td><a href="{% url 'customers:detail' c.pk %}">{{ c.last_name }}{% if c.last_name and c.first_name %}, {% endif %}{{ c.first_name }}{% if not c.first_name and not c.last_name %}{{ c }}{% endif %}</a></td>
      <td>{{ c.date_of_birth|date:"m/d/Y"|default:"—" }}</td>
      <td>{{ c.phone_primary|phone|default:"—" }}</td>
      <td>{{ c.get_preferred_language_display|default:"—" }}</td>
    </tr>
  {% empty %}
    <tr><td colspan="4" class="muted">No customers found.</td></tr>
  {% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/customers/form.html`:
```html
{% extends "base.html" %}
{% block title %}{% if is_new %}New customer{% else %}Edit {{ customer }}{% endif %} · Maian{% endblock %}
{% block content %}
<h1>{% if is_new %}New customer{% else %}Edit {{ customer }}{% endif %}</h1>
<form method="post" enctype="multipart/form-data">
  {% csrf_token %}
  <div id="duplicate-warning"></div>

  <details class="card" open>
    <summary>Customer</summary>
    <div class="grid"
         hx-post="{% url 'customers:duplicates' %}{% if customer.pk %}?exclude={{ customer.pk }}{% endif %}"
         hx-trigger="change"
         hx-target="#duplicate-warning"
         hx-include="[name=phone_primary],[name=phone_secondary],[name=last_name],[name=date_of_birth]">
      {% include "customers/_field.html" with field=form.first_name %}
      {% include "customers/_field.html" with field=form.middle_name %}
      {% include "customers/_field.html" with field=form.last_name %}
      {% include "customers/_field.html" with field=form.gender %}
      {% include "customers/_field.html" with field=form.date_of_birth %}
      {% include "customers/_field.html" with field=form.email %}
      {% include "customers/_field.html" with field=form.phone_primary %}
      {% include "customers/_field.html" with field=form.phone_secondary %}
      {% include "customers/_field.html" with field=form.preferred_language %}
      {% include "customers/_field.html" with field=form.immigration_status %}
      {% include "customers/_field.html" with field=form.household_income %}
      {% include "customers/_field.html" with field=form.emergency_contact_name %}
      {% include "customers/_field.html" with field=form.emergency_contact_phone %}
    </div>
  </details>

  <details class="card" open>
    <summary>Residential address</summary>
    <div class="grid">
      {% include "customers/_field.html" with field=form.res_street %}
      {% include "customers/_field.html" with field=form.res_apt %}
      {% include "customers/_field.html" with field=form.res_city %}
      {% include "customers/_field.html" with field=form.res_state %}
      {% include "customers/_field.html" with field=form.res_zip %}
    </div>
    <p><label>{{ form.mailing_same_as_residential }} {{ form.mailing_same_as_residential.label }}</label></p>
  </details>

  <details class="card" {% if not form.instance.mailing_same_as_residential %}open{% endif %}>
    <summary>Mailing address (only if different)</summary>
    <div class="grid">
      {% include "customers/_field.html" with field=form.mail_street %}
      {% include "customers/_field.html" with field=form.mail_apt %}
      {% include "customers/_field.html" with field=form.mail_city %}
      {% include "customers/_field.html" with field=form.mail_state %}
      {% include "customers/_field.html" with field=form.mail_zip %}
    </div>
  </details>

  <details class="card" open>
    <summary>Spouse</summary>
    {{ spouse_formset.management_form }}{{ spouse_formset.non_form_errors }}
    {% for member_form in spouse_formset %}
      <div class="grid">{{ member_form.id }}{% for field in member_form.visible_fields %}{% include "customers/_field.html" %}{% endfor %}</div>
    {% endfor %}
  </details>

  <details class="card" open>
    <summary>Dependents</summary>
    {{ dependent_formset.management_form }}
    {% for member_form in dependent_formset %}
      <div class="grid member">{{ member_form.id }}{% for field in member_form.visible_fields %}{% include "customers/_field.html" %}{% endfor %}</div>
    {% endfor %}
    <p class="muted">More dependents? Save, then edit again to get more blank rows.</p>
  </details>

  <details class="card" open>
    <summary>Vault</summary>
    {% include "customers/_field.html" with field=upload_form.file %}
  </details>

  <div class="actions">
    <button type="submit">Save</button>
    {% if customer.pk %}<a href="{% url 'customers:detail' customer.pk %}">Cancel</a>{% endif %}
  </div>
</form>
{% endblock %}
```
In `_field.html` used in a loop, `field` comes from the `for` context, so `{% include "customers/_field.html" %}` without `with` works.

`templates/customers/detail.html`:
```html
{% extends "base.html" %}{% load customer_tags %}
{% block title %}{{ customer }} · Maian{% endblock %}
{% block content %}
<h1>{{ customer }}</h1>
<p><a class="button" href="{% url 'customers:edit' customer.pk %}">Edit</a></p>

{% include "customers/_duplicates.html" %}

<div class="card">
  <h2>Checklist</h2>
  {% if missing %}<ul class="checklist">{% for item in missing %}<li>{{ item }}</li>{% endfor %}</ul>
  {% else %}<p class="checklist complete">Complete.</p>{% endif %}
  {% if customer.sms_opt_out %}<p class="warning">Opted out of SMS on {{ customer.sms_opt_out_at|date:"m/d/Y" }}. Call instead.</p>{% endif %}
</div>

<div class="card">
  <dl class="facts">
    <dt>Date of birth</dt><dd>{{ customer.date_of_birth|date:"m/d/Y"|default:"—" }}</dd>
    <dt>Gender</dt><dd>{{ customer.get_gender_display|default:"—" }}</dd>
    <dt>Primary phone</dt><dd>{{ customer.phone_primary|phone|default:"—" }}</dd>
    <dt>Second phone</dt><dd>{{ customer.phone_secondary|phone|default:"—" }}</dd>
    <dt>Email</dt><dd>{{ customer.email|default:"—" }}</dd>
    <dt>Emergency contact</dt><dd>{{ customer.emergency_contact_name|default:"—" }} {{ customer.emergency_contact_phone|phone }}</dd>
    <dt>Residential</dt><dd>{{ customer.res_street }} {{ customer.res_apt }}, {{ customer.res_city }} {{ customer.res_state }} {{ customer.res_zip }}</dd>
    <dt>Mailing</dt><dd>{% if customer.mailing_same_as_residential %}Same as residential{% else %}{{ customer.mail_street }} {{ customer.mail_apt }}, {{ customer.mail_city }} {{ customer.mail_state }} {{ customer.mail_zip }}{% endif %}</dd>
    <dt>Preferred language</dt><dd>{{ customer.get_preferred_language_display|default:"—" }}</dd>
    <dt>Immigration status</dt><dd>{{ customer.get_immigration_status_display|default:"—" }}</dd>
    <dt>Household income</dt><dd>{% if customer.household_income is not None %}${{ customer.household_income }}{% else %}—{% endif %}</dd>
  </dl>
</div>

<div class="card">
  <h2>Household</h2>
  <table>
    <thead><tr><th>Name</th><th>Relationship</th><th>DOB</th><th>Immigration</th><th>Public coverage</th><th></th></tr></thead>
    <tbody>
    {% for m in customer.household_members.all %}
      <tr>
        <td>{{ m.first_name }} {{ m.last_name }}</td><td>{{ m.get_relationship_display }}</td>
        <td>{{ m.date_of_birth|date:"m/d/Y"|default:"—" }}</td><td>{{ m.get_immigration_status_display|default:"—" }}</td>
        <td>{{ m.get_public_coverage_display|default:"—" }}</td>
        <td>{% if is_admin %}<form method="post" action="{% url 'customers:member_archive' m.pk %}">{% csrf_token %}<button class="danger">Archive</button></form>{% endif %}</td>
      </tr>
    {% empty %}<tr><td colspan="6" class="muted">No spouse or dependents.</td></tr>{% endfor %}
    </tbody>
  </table>
</div>

{% block vault %}{% endblock %}

{% if is_admin %}
<form method="post" action="{% url 'customers:archive' customer.pk %}">{% csrf_token %}
  <button class="danger">Archive this customer</button>
</form>
{% endif %}
{% endblock %}
```
Task 5 replaces `{% block vault %}{% endblock %}` with the Vault card.

- [ ] **Step 10: Stub the vault imports so this task runs before Task 5.** Create `vault/forms.py` with a `VaultUploadForm(forms.Form)` that has one `file = forms.FileField(required=False)`, and `vault/services.py` with `def store_document(customer, uploaded_file, user): raise NotImplementedError`. In `customer_detail`, write `"documents": []` until Task 5.

- [ ] **Step 11: Migrate, test, look at it**

Run: `.venv/bin/python manage.py migrate && .venv/bin/pytest`
Expected: 11 passed.

Run: `.venv/bin/python manage.py createsuperuser` (email + password), add the superuser to the Admin group in `/dev-admin/`, then `.venv/bin/python manage.py runserver`. Log in, set up the authenticator, create a Customer with a spouse and two dependents, and edit it. Typing an existing phone should show the duplicate warning.

- [ ] **Step 12: Commit**

```bash
git add -A && git commit -m "Add intake form, customer record with checklist, search, duplicate warning"
```

---

### Task 5: Vault

**Files:**
- Create: `vault/models.py`, `vault/views.py`, `vault/admin.py`
- Modify: `vault/forms.py`, `vault/services.py`, `vault/urls.py`, `customers/views.py` (restore `customer.documents`), `customers/models.py` (remove `hasattr` guard), `templates/customers/detail.html`, `core/tests/test_permissions.py`

**Interfaces:**
- Consumes: `Customer`, `ArchivableModel`, `archive`
- Produces: `vault.models.VaultDocument` (related_name `documents`), `vault.forms.ALLOWED_EXTENSIONS: dict[str, str]`, `MAX_UPLOAD_BYTES`, `VaultUploadForm`, `vault.services.store_document(customer, uploaded_file, user) -> VaultDocument`, URL names `vault:upload(customer_pk)`, `vault:download(pk)`, `vault:archive(pk)`.

- [ ] **Step 1: Write the failing test** (append)

```python
from vault.models import VaultDocument


def test_staff_cannot_archive_vault_document(make_user, login_verified):
    staff = make_user("staff@example.com", STAFF_GROUP)
    client = login_verified(staff)
    customer = Customer.objects.create(first_name="Lan")
    doc = VaultDocument.objects.create(
        customer=customer, file="customers/1/test.pdf", original_filename="plan.pdf",
        content_type="application/pdf", size_bytes=10, uploaded_by=staff,
    )
    response = client.post(f"/vault/{doc.pk}/archive/")
    assert response.status_code == 403
    assert VaultDocument.objects.filter(pk=doc.pk).exists()
```

- [ ] **Step 2: Run and confirm failure**

Run: `.venv/bin/pytest core/tests/test_permissions.py::test_staff_cannot_archive_vault_document`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'VaultDocument'`.

- [ ] **Step 3: Write `vault/models.py`**

```python
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import storages
from django.db import models

from core.models import ArchivableModel


def vault_storage():
    return storages["vault"]


def vault_key(instance, filename):
    """Random stored name. The uploaded filename is never used in the path (ADR-0015)."""
    return f"customers/{instance.customer_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class VaultDocument(ArchivableModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="documents")
    file = models.FileField(upload_to=vault_key, storage=vault_storage, max_length=255)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta(ArchivableModel.Meta):
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename
```

- [ ] **Step 4: Replace `vault/forms.py` and `vault/services.py`**

`vault/forms.py`:
```python
from pathlib import Path

from django import forms

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class VaultUploadForm(forms.Form):
    file = forms.FileField(
        required=False,
        label="Upload a document (PDF, JPG, PNG, up to 10 MB)",
        widget=forms.ClearableFileInput(attrs={"accept": ",".join(ALLOWED_EXTENSIONS)}),
    )

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            return None
        if Path(uploaded.name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError("Only PDF, JPG, and PNG files can be uploaded.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The file is larger than 10 MB.")
        return uploaded
```

`vault/services.py`:
```python
from pathlib import Path

from vault.forms import ALLOWED_EXTENSIONS
from vault.models import VaultDocument


def store_document(customer, uploaded_file, user):
    """Save an already-validated upload to the Vault. Content type comes from our
    whitelist, not from what the browser claims."""
    extension = Path(uploaded_file.name).suffix.lower()
    document = VaultDocument(
        customer=customer,
        original_filename=Path(uploaded_file.name).name[:255],
        content_type=ALLOWED_EXTENSIONS[extension],
        size_bytes=uploaded_file.size,
        uploaded_by=user,
    )
    document.file.save(uploaded_file.name, uploaded_file, save=True)
    return document
```

- [ ] **Step 5: Write `vault/views.py`, `vault/urls.py`, `vault/admin.py`**

`vault/views.py`:
```python
import logging

from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from core.archive import archive
from customers.models import Customer
from vault.forms import VaultUploadForm
from vault.models import VaultDocument
from vault.services import store_document

logger = logging.getLogger(__name__)


@require_POST
def upload(request, customer_pk):
    customer = get_object_or_404(Customer, pk=customer_pk)
    form = VaultUploadForm(request.POST, request.FILES)
    if not form.is_valid() or not form.cleaned_data.get("file"):
        messages.error(request, " ".join(form.errors.get("file", ["Choose a file first."])))
        return redirect("customers:detail", pk=customer.pk)
    try:
        store_document(customer, form.cleaned_data["file"], request.user)
        messages.success(request, "Document uploaded.")
    except Exception:
        logger.exception("Vault upload failed for customer %s", customer.pk)
        messages.error(request, "The upload failed. Try again.")
    return redirect("customers:detail", pk=customer.pk)


def download(request, pk):
    """Reached only by a verified user (middleware). Production redirects to a
    5-minute presigned R2 link; development streams the local file."""
    document = get_object_or_404(VaultDocument, pk=pk)
    storage = document.file.storage
    if hasattr(storage, "bucket_name"):
        url = storage.url(document.file.name, parameters={
            "ResponseContentDisposition": content_disposition_header(True, document.original_filename),
            "ResponseContentType": document.content_type,
        })
        return redirect(url)
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.original_filename)


@require_POST
def archive_document(request, pk):
    document = get_object_or_404(VaultDocument, pk=pk)
    archive(document, request.user)
    messages.success(request, "Document archived.")
    return redirect("customers:detail", pk=document.customer_id)
```

`vault/urls.py`:
```python
from django.urls import path

from vault import views

app_name = "vault"
urlpatterns = [
    path("upload/<int:customer_pk>/", views.upload, name="upload"),
    path("<int:pk>/download/", views.download, name="download"),
    path("<int:pk>/archive/", views.archive_document, name="archive"),
]
```

`vault/admin.py`:
```python
from django.contrib import admin

from customers.admin import ArchivableAdmin
from vault.models import VaultDocument


@admin.register(VaultDocument)
class VaultDocumentAdmin(ArchivableAdmin):
    list_display = ["original_filename", "customer", "uploaded_by", "uploaded_at", "archived_at"]
    readonly_fields = ["file", "content_type", "size_bytes", "uploaded_by", "uploaded_at"]
```

- [ ] **Step 6: Restore the real code paths.** In `customers/views.py`, set `"documents": customer.documents.all()`. In `customers/models.py`, remove the `hasattr` guard in `missing_items`. In `templates/customers/detail.html`, replace `{% block vault %}{% endblock %}` with:

```html
<div class="card">
  <h2>Vault</h2>
  <table>
    <thead><tr><th>File</th><th>Uploaded</th><th>By</th><th></th></tr></thead>
    <tbody>
    {% for d in documents %}
      <tr>
        <td><a href="{% url 'vault:download' d.pk %}">{{ d.original_filename }}</a></td>
        <td>{{ d.uploaded_at|date:"m/d/Y" }}</td><td>{{ d.uploaded_by }}</td>
        <td>{% if is_admin %}<form method="post" action="{% url 'vault:archive' d.pk %}">{% csrf_token %}<button class="danger">Archive</button></form>{% endif %}</td>
      </tr>
    {% empty %}<tr><td colspan="4" class="muted">No documents yet.</td></tr>{% endfor %}
    </tbody>
  </table>
  <form method="post" action="{% url 'vault:upload' customer.pk %}" enctype="multipart/form-data" style="margin-top:.75rem">
    {% csrf_token %}{% include "customers/_field.html" with field=upload_form.file %}
    <button type="submit" class="secondary">Upload</button>
  </form>
</div>
```

- [ ] **Step 7: Migrate and test**

Run: `.venv/bin/python manage.py makemigrations vault && .venv/bin/python manage.py migrate && .venv/bin/pytest`
Expected: 12 passed. Then, in the browser, upload a PDF from the intake form and from the record page, download it (it should save as a file, not open in a tab), and confirm that uploading a `.txt` shows the error message while the Customer stays saved.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "Add Vault: upload, attachment download, admin-only archive"
```

---

### Task 6: Seed script

**Files:**
- Create: `customers/management/__init__.py`, `customers/management/commands/__init__.py`, `customers/management/commands/seed.py`

**Interfaces:**
- Consumes: `Customer`, `HouseholdMember`, choices, `core.User`, groups
- Produces: `python manage.py seed` creates ~200 fake Customers plus `admin@example.com` and `staff@example.com` (dev password printed). It refuses to run when `DEBUG` is off.

- [ ] **Step 1: Write the command**

```python
"""Fake data for local development (ADR-0013). Never real customers."""
import random
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import User
from customers.models import (
    Customer, Gender, HouseholdMember, ImmigrationStatus, Language, PublicCoverage, Relationship,
)

VI_LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng", "Bùi", "Đỗ"]
VI_FIRST_F = ["Thị Lan", "Ngọc Anh", "Thu Hà", "Mai", "Kim Chi", "Hồng Nhung", "Bích Ngọc"]
VI_FIRST_M = ["Văn Minh", "Quốc Bảo", "Đức Anh", "Hoàng Nam", "Thanh Tùng", "Minh Khoa"]
EN_LAST = ["Johnson", "Williams", "Brown", "Garcia", "Martinez", "Davis", "Lopez", "Wilson", "Hernandez"]
EN_FIRST_F = ["Maria", "Jennifer", "Linda", "Sofia", "Ashley", "Guadalupe"]
EN_FIRST_M = ["James", "Robert", "Jose", "Michael", "Carlos", "David"]
STREETS = ["Texas Pkwy", "Cartwright Rd", "Murphy Rd", "Sienna Pkwy", "Hampton Dr", "Lexington Blvd"]
CITIES = [("Missouri City", "77459"), ("Sugar Land", "77478"), ("Houston", "77072"), ("Stafford", "77477")]
DEV_PASSWORD = "dev-password-change-me"


class Command(BaseCommand):
    help = "Create ~200 fake Customers and two dev users. Development only."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    def handle(self, *args, count, **options):
        if not settings.DEBUG:
            raise CommandError("Refusing to seed: DEBUG is off. Seed data never goes to production.")
        rng = random.Random(2026)
        self._users()
        created = []
        for _ in range(count):
            created.append(self._customer(rng))
        for original in rng.sample(created, 10):
            self._near_duplicate(rng, original)
        for customer in rng.sample(created, 5):
            customer.sms_opt_out = True
            customer.sms_opt_out_at = timezone.now()
            customer.save()
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {count + 10} customers. Log in as admin@example.com or staff@example.com / {DEV_PASSWORD}"
        ))

    def _users(self):
        for email, group, is_staff in [("admin@example.com", "Admin", True), ("staff@example.com", "Staff", False)]:
            user, made = User.objects.get_or_create(email=email, defaults={"is_staff": is_staff})
            if made:
                user.set_password(DEV_PASSWORD)
                user.save()
            user.groups.add(Group.objects.get(name=group))

    def _messy_phone(self, rng):
        area = rng.choice(["281", "832", "713", "346"])
        n = f"{area}{rng.randint(2000000, 9999999)}"
        return rng.choice([
            n, f"({n[:3]}) {n[3:6]}-{n[6:]}", f"{n[:3]}.{n[3:6]}.{n[6:]}", f"+1 {n[:3]}-{n[3:6]}-{n[6:]}",
            f"{n[3:6]}-{n[6:]}",  # missing area code: flagged by the checklist
        ])

    def _person(self, rng, vietnamese, female):
        if vietnamese:
            return rng.choice(VI_LAST), rng.choice(VI_FIRST_F if female else VI_FIRST_M)
        return rng.choice(EN_LAST), rng.choice(EN_FIRST_F if female else EN_FIRST_M)

    def _customer(self, rng):
        vietnamese = rng.random() < 0.6
        female = rng.random() < 0.5
        last, first = self._person(rng, vietnamese, female)
        city, zip_code = rng.choice(CITIES)
        language = Language.VI if vietnamese and rng.random() < 0.8 else rng.choice([Language.EN, Language.ES])
        customer = Customer.objects.create(
            first_name=first, last_name=last,
            gender=Gender.FEMALE if female else Gender.MALE,
            date_of_birth=None if rng.random() < 0.15 else date(1950, 1, 1) + timedelta(days=rng.randint(0, 20000)),
            email="" if rng.random() < 0.4 else f"{first.split()[0].lower()}{rng.randint(1, 99)}@example.com",
            res_street=f"{rng.randint(100, 9999)} {rng.choice(STREETS)}", res_city=city, res_zip=zip_code,
            phone_primary="" if rng.random() < 0.05 else self._messy_phone(rng),
            phone_secondary=self._messy_phone(rng) if rng.random() < 0.3 else "",
            preferred_language="" if rng.random() < 0.1 else language,
            immigration_status=rng.choice([c for c, _ in ImmigrationStatus.choices] + [""]),
            household_income=None if rng.random() < 0.2 else rng.randrange(18000, 95000, 500),
        )
        if rng.random() < 0.45:
            s_last, s_first = self._person(rng, vietnamese, not female)
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.SPOUSE, first_name=s_first, last_name=s_last,
                immigration_status=rng.choice([c for c, _ in ImmigrationStatus.choices]),
            )
        for _ in range(rng.choice([0, 0, 1, 2, 3])):
            d_first = self._person(rng, vietnamese, rng.random() < 0.5)[1]
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.DEPENDENT, first_name=d_first, last_name=last,
                date_of_birth=date(2008, 1, 1) + timedelta(days=rng.randint(0, 6000)),
                public_coverage=rng.choice([PublicCoverage.NONE, PublicCoverage.CHIP, PublicCoverage.MEDICAID]),
            )
        if rng.random() < 0.05:
            HouseholdMember.objects.create(
                customer=customer, relationship=Relationship.DEPENDENT, first_name="Văn Hùng", last_name=last,
                date_of_birth=date(1948, 3, 9), public_coverage=PublicCoverage.MEDICARE,
            )
        return customer

    def _near_duplicate(self, rng, original):
        """Same person entered twice by two staff: name without diacritics, same phone."""
        plain = original.last_name.replace("ễ", "e").replace("ầ", "a").replace("ạ", "a").replace("à", "a")
        Customer.objects.create(
            first_name=original.first_name, last_name=plain,
            date_of_birth=original.date_of_birth, phone_primary=original.phone_primary,
        )
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python manage.py seed`
Expected: `Seeded 210 customers. …`. In the browser, search for `nguyen` and confirm it finds `Nguyễn` (unaccent). Open a near-duplicate and confirm the warning shows.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "Add development seed script with messy, realistic fake customers"
```

---

### Task 7: Production readiness and deploy guide

**Files:**
- Create: `build.sh`, `.python-version`, `.github/dependabot.yml`, `docs/deploy.md`

**Interfaces:**
- Consumes: settings env vars from Task 1
- Produces: a repo Render can build and run; the user's step-by-step hosting guide.

- [ ] **Step 1: Write build files**

`build.sh`:
```bash
#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
```
Run: `chmod +x build.sh`

`.python-version`:
```
3.14
```

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
```

- [ ] **Step 2: Verify deploy settings locally**

Run: `DEBUG=0 SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(50))') R2_BUCKET=x R2_ENDPOINT_URL=https://x R2_ACCESS_KEY_ID=x R2_SECRET_ACCESS_KEY=x ALLOWED_HOSTS=maian.onrender.com .venv/bin/python manage.py check --deploy`
Expected: no errors. If `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` warnings appear, they're acceptable on an `onrender.com` subdomain; note that in `docs/deploy.md`.

- [ ] **Step 3: Write `docs/deploy.md`.** Cover, in order:
  1. **Cloudflare R2:** create a bucket named `maian-vault` (leave public access **disabled**). Create an R2 API token with "Object Read & Write" scoped to that bucket only. Record the Access Key ID, Secret Access Key, and the S3 endpoint `https://<account-id>.r2.cloudflarestorage.com`.
  2. **Render PostgreSQL:** New → PostgreSQL, region Ohio or Oregon (US), a paid plan with backups. Copy the *Internal Database URL*.
  3. **Render Web Service:** connect the GitHub repo, branch `main`, region matching the DB, build command `./build.sh`, start command `gunicorn maian.wsgi --workers 2 --timeout 60`.
  4. **Environment variables:** `DEBUG=0`, `SECRET_KEY` (generate a 50-char random value), `DATABASE_URL`, `ALLOWED_HOSTS=<service>.onrender.com`, `ADMIN_PATH=<random-word>-<random-word>/`, `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `PYTHON_VERSION=3.14.x` (only if `.python-version` isn't honored).
  5. **First admin:** Render Shell → `python manage.py createsuperuser`, then open `/<ADMIN_PATH>`, add yourself to the Admin group, log in on the site, and set up the authenticator.
  6. **Security checklist gate:** go through every box in `docs/security-baseline.md` → "Required configuration" against the live site *before* the first real Customer is saved. Include: `/nonexistent` shows a plain 404 (not a debug page), the R2 bucket URL is not publicly reachable, and 6 wrong passwords lock the account.
  7. **Staff accounts:** in Django admin, add a user with email and a temporary password, put them in the Staff group, leave `is_staff` unchecked. They log in and enroll 2FA on first login. Lost phone: Admin removes their TOTP device under "OTP_TOTP › TOTP devices" and they enroll again.
  8. **Enable Dependabot** in GitHub repo settings.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "Add build script, Dependabot, and Render + R2 deploy guide"
```

---

## Self-review notes

- Spec coverage for step 1: auth + 2FA + axes + sessions (Tasks 1–2); roles (2); Customer and Household Member fields incl. immigration status on all members and `public_coverage` (3); archive + AuditEvent + restore (3); intake + checklist + search + unaccent + duplicates (4); Vault (5); seed (6); security checklist gate + hosting guide (7). Send is the next plan.
- Deviation from spec: the "add another dependent" button uses blank rows instead of HTMX, which means no JavaScript. Recorded in `customers/forms.py`.
- Tests are limited to permissions, per ADR-0014. When appending tests to `core/tests/test_permissions.py`, move the new imports to the top of the file.
