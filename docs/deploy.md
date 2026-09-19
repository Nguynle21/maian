# Deploying Maian

One deployable on Render, one PostgreSQL database, one private R2 bucket. There is no
staging environment (ADR-0013), so this is the only place Maian runs besides a laptop.

Work through this in order. Step 6 is a gate: do not save a real Customer before it passes.

---

## 1. Cloudflare R2 (Vault storage)

1. Cloudflare dashboard → **R2** → **Create bucket**, name it `maian-vault`, location
   North America.
2. Leave **Public access disabled**. Do not connect a custom domain and do not enable the
   `r2.dev` public URL. Every file is served through Maian with a presigned link that
   expires in 300 seconds (ADR-0007).
3. **Manage R2 API Tokens** → **Create API token**:
   - Permission: **Object Read & Write**
   - Specify bucket: **`maian-vault` only** (not "all buckets")
   - TTL: forever
4. Record three values, once — Cloudflare shows the secret only at creation:
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`
   - **Endpoint** `https://<account-id>.r2.cloudflarestorage.com` → `R2_ENDPOINT_URL`

   The bucket name `maian-vault` goes in `R2_BUCKET`.

---

## 2. Render PostgreSQL

1. Render dashboard → **New** → **PostgreSQL**.
2. Name `maian-db`, region **Ohio** or **Oregon** (US, per ADR-0003).
3. Pick a **paid plan** — the free tier expires after 90 days and has no backups. This
   database holds the only copy of the agency's customer records.
4. Copy the **Internal Database URL** (starts `postgres://`). That is `DATABASE_URL`.

---

## 3. Render Web Service

**New** → **Web Service** → connect the GitHub repo `Nguynle21/maian`.

| Setting | Value |
|---|---|
| Branch | `main` |
| Region | the same one as the database |
| Runtime | Python 3 |
| Build command | `./build.sh` |
| Start command | `gunicorn maian.wsgi --workers 2 --timeout 60` |
| Instance type | a paid one (free instances sleep and lose the disk) |

`build.sh` installs dependencies, runs `collectstatic`, and applies migrations on every
deploy.

---

## 4. Environment variables

Set these on the web service under **Environment**. Nothing secret is ever in the repo.

| Variable | Value |
|---|---|
| `DEBUG` | `0` |
| `SECRET_KEY` | generate: `python3 -c 'import secrets; print(secrets.token_urlsafe(50))'` |
| `DATABASE_URL` | the Internal Database URL from step 2 |
| `ALLOWED_HOSTS` | `<service-name>.onrender.com` (add the custom domain later, comma-separated) |
| `ADMIN_PATH` | `<random-word>-<random-word>/` — **keep the trailing slash** |
| `R2_BUCKET` | `maian-vault` |
| `R2_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` | from step 1 |
| `R2_SECRET_ACCESS_KEY` | from step 1 |
| `PYTHON_VERSION` | only if `.python-version` is not honored; then `3.14.x` |

`ADMIN_PATH` is not a security boundary on its own — Staff are blocked from Django admin
in code — but it keeps the admin login page off the scanners' list.

With `DEBUG=0` the app refuses to start unless `R2_BUCKET` is set, so a misconfigured
deploy fails loudly instead of quietly writing Vault files to a disk that disappears.

---

## 5. First admin account

1. Render → the web service → **Shell**.
2. `python manage.py createsuperuser` — use your own email and a real password.
3. Open `https://<service>.onrender.com/<ADMIN_PATH>` and log in.
4. **Users → your user → Groups**: add **Admin**. Save.
5. Log in on the site itself. It will force you through 2FA setup: scan the QR code with
   Google Authenticator or 1Password and **save the backup tokens somewhere offline**.

---

## 6. Security checklist gate — before the first real Customer

Go through every box in `docs/security-baseline.md` → "Required configuration" against
the live site. These four are the ones worth checking by hand:

- [ ] `https://<service>.onrender.com/nonexistent` shows a plain **404**, not a yellow
      Django debug page. (A debug page here means `DEBUG` is not `0`.)
- [ ] The R2 bucket is not publicly reachable: a bucket object URL without a signature
      returns an error, and the Vault download link in Maian stops working after five
      minutes.
- [ ] Five wrong passwords in a row lock that email out for an hour (django-axes,
      `AXES_FAILURE_LIMIT = 5`; the lockout follows the email, not the IP, because the
      office shares one). Confirm with a throwaway account, then clear the lockout with
      `python manage.py axes_reset_username <email>` in the Render shell.
- [ ] Logging out and hitting any URL sends you to the login page, and a logged-in
      session that has not passed 2FA lands on the setup page.

The two `check --deploy` warnings that remain — `SECURE_HSTS_INCLUDE_SUBDOMAINS` and
`SECURE_HSTS_PRELOAD` — are **accepted** while the site lives on an `onrender.com`
subdomain: Render controls the parent domain, so those are not ours to assert. Revisit
both if Maian moves to its own domain.

---

## 7. Staff accounts

To add a staff member:

1. Django admin → **Users** → **Add user**.
2. Email, a temporary password, group **Staff**. Leave **is_staff unchecked** — that flag
   is Django-admin access, not the Staff role.
3. Send them the temporary password out of band. On first login they enroll 2FA
   themselves, and they should change the password.

**Lost phone:** Admin → **OTP_TOTP → TOTP devices** → remove that user's device. Their
next login sends them through setup again. Accounts are never removed, only deactivated
(uncheck **Active**) — ADR-0012.

---

## 8. Dependabot

GitHub repo → **Settings** → **Code security** → enable **Dependabot alerts** and
**security updates**. `.github/dependabot.yml` already asks for weekly pip updates; the
pull requests it opens are the reminder to apply them.

---

## Restoring from backup

Render keeps automatic daily backups on paid PostgreSQL plans (**Recovery** tab →
point-in-time restore). Nothing in Maian is hard-deleted (ADR-0011), so the usual
recovery is restoring an archived record in Django admin, not restoring the database.
The database backup is for the case where the whole instance is lost.
