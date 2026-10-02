# accounts

Identity: who someone is and how they sign in. Nothing else.

## Model

`User` is email-based (`USERNAME_FIELD = "email"`, no username) and uses a UUID
primary key from `common.models.UUIDModel`. Nobody has a password.

| Field         | Meaning                                                   |
| ------------- | --------------------------------------------------------- |
| `email`       | Unique, stored lower-cased. Kept in step with Google.     |
| `google_sub`  | Google's stable account id; what sign-in matches on.      |
| `is_active`   | `False` blocks sign-in.                                   |
| `is_staff`    | Can use the Django admin.                                 |
| `date_joined` | When the account was created.                             |

Keep `User` thin. A display name, avatar, preference or any app-specific fact
belongs on the [profile](../profiles/README.md), never here.

**The system user** has the fixed id `User.SYSTEM_ID`
(`00000000-0000-0000-0000-000000000001`) and the address `system@invalid`. A
migration creates it, so it exists in every database, tests included. It owns
whatever the site does on its own behalf and can never sign in.

## Signing in

Google is the only way in, and the first sign-in creates the account and its
profile (display name from Google).

1. The frontend's `/auth/google` calls `google/start/`, which returns Google's
   authorisation URL with a fresh `state` and PKCE `code_verifier`. The
   frontend keeps both in a short-lived cookie and redirects there.
2. Google sends the visitor to `{PUBLIC_ORIGIN}/auth/google/callback`, the
   redirect URI registered on the OAuth client. The frontend checks `state`
   and posts `code` and `code_verifier` to `google/`.
3. Django exchanges the code for an ID token and checks its audience, issuer,
   expiry and `email_verified`. It finds the account by `google_sub`, else by
   email (linking it), else creates it, and returns a JWT pair.

Settings: `ACCOUNTS_GOOGLE_CLIENT_ID` and `ACCOUNTS_GOOGLE_CLIENT_SECRET`.

## The admin

There are no passwords, so the admin's login page signs in whoever the frontend
has signed in: it reads the `access_token` cookie (same host, so Django gets
it), and a staff member gets a Django session. Anyone else is sent to the
frontend to sign in. Locally that round trip ends on `:3000`; open
`localhost:8000/api/admin/` again afterwards.

## Commands

| Command                              | What                                                  |
| ------------------------------------ | ----------------------------------------------------- |
| `make_superuser <email> [--revoke]`  | Give an existing account staff and superuser rights.  |
| `login_as <email>`                   | Development only (`DEBUG`): create the account if needed and print a sign-in link for the frontend's `/auth/dev-login`. |

`createsuperuser` is refused: sign in with Google, then `make_superuser`.

## API — `/api/v1/auth/`

| Method | Path            | Auth | Purpose                                            |
| ------ | --------------- | ---- | -------------------------------------------------- |
| POST   | `google/start/` | —    | Authorisation URL + `state` + `code_verifier`      |
| POST   | `google/`       | —    | `code` + `code_verifier` → JWT pair + user          |
| POST   | `refresh/`      | —    | Rotate the refresh token → new pair                |
| POST   | `verify/`       | —    | Check a token                                      |
| POST   | `logout/`       | JWT  | Blacklist a refresh token                          |
| GET    | `me/`           | JWT  | The authenticated account                          |

Refresh tokens rotate (`ROTATE_REFRESH_TOKENS`), so `refresh/` returns both
tokens.
