# accounts

Identity: who someone is and how they sign in. Nothing else.

## Model

`User` is email-based (`USERNAME_FIELD = "email"`, no username) and uses a UUID
primary key from `common.models.UUIDModel`.

| Field               | Meaning                                              |
| ------------------- | ---------------------------------------------------- |
| `email`             | Unique, stored lower-cased. The login.               |
| `is_active`         | `False` until the email is verified.                 |
| `is_email_verified` | Set when the verification link is followed.          |
| `is_staff`          | Can use the Django admin.                            |
| `date_joined`       | When the account was created.                        |

Keep `User` thin. A display name, avatar, preference or any app-specific fact
belongs on the [profile](../profiles/README.md), never here.

## Registration and verification

1. `register/` creates an **inactive** user and their profile, then emails a
   link to `{PUBLIC_ORIGIN}/verify-email?uid=…&token=…`. Creating the account and
   sending the mail happen in one transaction: if sending fails, the account is
   rolled back and the API answers `503 email_unavailable`, so the address can
   register again.
2. The frontend posts `uid` and `token` to `verify-email/`. That activates the
   account and returns a JWT pair, which signs the user in.
3. The token comes from Django's `default_token_generator`, which hashes
   `is_active`. It therefore stops working once the account is active, so each
   link works only once.

Signing in before verifying returns `403 email_not_verified`, but only if the
password is correct. With a wrong password the caller gets the generic
failure, so nobody can use login to find out which accounts are waiting on
verification. For the same reason, `verify-email/resend/` gives the same answer
whether or not the address has an account.

The email's subject and body use `SITE_NAME`, so the app never hard-codes a
product name.

## API — `/api/v1/auth/`

| Method | Path                   | Auth | Purpose                                         |
| ------ | ---------------------- | ---- | ----------------------------------------------- |
| POST   | `register/`            | —    | Create an inactive account and its profile      |
| POST   | `verify-email/`        | —    | Activate from the emailed link → JWT pair + user |
| POST   | `verify-email/resend/` | —    | Send a fresh link to an unverified account      |
| POST   | `login/`               | —    | Email + password → JWT pair + user              |
| POST   | `refresh/`             | —    | Rotate the refresh token → new pair             |
| POST   | `verify/`              | —    | Check a token                                   |
| POST   | `logout/`              | JWT  | Blacklist a refresh token                       |
| GET    | `me/`                  | JWT  | The authenticated account                       |
| POST   | `password/change/`     | JWT  | Change password                                 |

Refresh tokens rotate (`ROTATE_REFRESH_TOKENS`), so `refresh/` returns both
tokens. Some serializers in `serializers.py` exist only so that the OpenAPI
schema describes the real request and response bodies (`AuthResponseSerializer`,
`TokenRefresh*Serializer`, `RegisterResponseSerializer`).

## Where things live

| File             | What                                               |
| ---------------- | -------------------------------------------------- |
| `models.py`      | `User` and `UserManager`                           |
| `services.py`    | `send_verification_email`, `verify_email`          |
| `serializers.py` | Request validation, login, schema-only serializers |
| `views.py`       | The endpoints above                                |
