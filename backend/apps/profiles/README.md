# profiles

Everything the app knows about a person beyond their identity. Each
[`accounts.User`](../accounts/README.md) has exactly one `Profile`
(`user.profile`).

## Model

`Profile` extends `common.models.BaseModel`, so it has a UUID primary key,
timestamps and `extra`.

| Field                        | Meaning                                                  |
| ---------------------------- | -------------------------------------------------------- |
| `display_name`               | Defaults to the part of the email before the `@`.        |
| `avatar_url`, `bio`          | Free text, editable by the owner.                        |
| `locale`, `timezone`         | Default `en-gb` and `UTC`.                               |
| `role`                       | `member` / `moderator` / `admin`. Not editable via the API. |
| `status`                     | `active` / `pending` / `suspended`. Not editable via the API. |
| `enrolled_at`                | When the profile was created.                            |
| `extra`                      | App-specific attributes; see [common](../common/README.md). |

## Creating profiles

Always go through `services.create_profile(user, display_name=…)`.
Registration calls it. Accounts made another way (`createsuperuser`, the admin)
have no profile until they first hit `profiles/me/`, which creates one for them.

A `suspended` profile gets `403` from `profiles/me/` and is left out of
`members/`.

## API — `/api/v1/`

| Method    | Path              | Purpose                                              |
| --------- | ----------------- | ---------------------------------------------------- |
| GET/PATCH | `profiles/me/`    | The caller's profile. PATCH replaces `extra` whole. |
| GET       | `members/`        | Active profiles, by `display_name`. Filter `?role=`. |
| GET       | `members/{id}/`   | One active profile                                   |

`members/` returns `PublicProfileSerializer` (`id`, `display_name`,
`avatar_url`, `bio`, `role`). Email and settings are never exposed to other
members.

## Where things live

| File             | What                                         |
| ---------------- | -------------------------------------------- |
| `models.py`      | `Profile`, `ProfileRole`, `ProfileStatus`    |
| `services.py`    | `create_profile`                             |
| `serializers.py` | Own profile vs. public profile               |
| `views.py`       | `ProfileViewSet`, `MemberViewSet`            |
