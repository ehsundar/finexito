# Contacts & Identity — Design

**Status:** draft, 2026-09-21
**Scope:** platform (`accounts`, new `contacts` app). Driven by Pane, but shared.

## The requirement

The shop owner types a phone number while taking an order. That order must end
up attached to a `User` — the existing one if that phone is already known, a
newly created one if not. The customer may later sign in with that same phone
by SMS code and find their history waiting. They may also never sign in, and
nothing should break.

Separately, a person has more contact detail than a login has: mobile, landline,
address, maybe a second address for a building site. That does not belong on
`User`.

## Shape

```
User            identity. Can authenticate. Thin.
  └─ Contact    how to reach that person. One per user.
       ├─ ContactChannel   mobile / landline / email / telegram / …
       └─ Address          home, shop, site, …
```

`Contact` is platform-level, not Pane-level: every program that deals with real
people needs a phone number and an address, and none of them should invent their
own. Program-specific facts about a person still go on `Profile`.

## Models

### `accounts.User` — changes

```python
class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(null=True, blank=True, unique=True, db_index=True)
    name  = models.CharField(max_length=150, blank=True)
    ...
```

Three changes, each one load-bearing:

1. **`email` becomes optional.** A customer created from a phone number has no
   email and may never have one. `unique=True` with `null=True` is fine in
   Postgres — several rows may hold `NULL`, so the constraint still does its job
   for real addresses. `UserManager._create_user` must stop raising on a missing
   email, and gain a sibling that creates from a phone instead.
2. **`name` is added, and is optional.** This contradicts the README's rule that
   display names live on `Profile`, so it is worth being explicit about why:
   a customer the shop typed in has no profile in any program yet, and "unknown
   person, 0912…" is a bad thing to show a shop owner. The rule becomes: `User.name`
   is the person's actual name, one value everywhere; `Profile.display_name`
   stays as the per-program handle that may differ from it. If we would rather
   not touch `User`, the alternative is `Contact.full_name` and no `name` on
   `User` at all — cleaner by the README's letter, but every caller then has to
   join through `Contact` for something as ordinary as a name.
3. **Phone is reachable but not stored here.** `User.phone` is a property that
   returns the primary mobile channel on the contact, or `None`. Optional by
   construction, and there is exactly one place the value actually lives.

`USERNAME_FIELD` stays `email`. Phone login is an additional authentication
backend, not a change of primary key.

### `contacts.Contact`

```python
class Contact(BaseModel):
    user  = models.OneToOneField(User, null=True, blank=True,
                                 related_name="contact", on_delete=models.CASCADE)
    notes = models.TextField(blank=True)
```

`user` is nullable so an address book entry that is not a person with an account
(a supplier, a delivery firm) can exist later. For Pane customers it is always
set.

### `contacts.ContactChannel`

```python
class ChannelKind(models.TextChoices):
    MOBILE   = "mobile"
    LANDLINE = "landline"
    EMAIL    = "email"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"

class ContactChannel(BaseModel):
    contact     = models.ForeignKey(Contact, related_name="channels", on_delete=models.CASCADE)
    kind        = models.CharField(max_length=20, choices=ChannelKind)
    value       = models.CharField(max_length=128)     # normalised, E.164 for phones
    label       = models.CharField(max_length=50, blank=True)   # "work", "home"
    is_primary  = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
```

Constraints that matter:

- **Normalise on save.** `0912 345 6789`, `+98 912 345 6789` and `00989123456789`
  are one number. Store E.164, normalise in `clean()`, never trust the caller.
  Without this the whole "find the existing user" step silently fails.
- **`(kind, value)` unique for `mobile` and `email`.** This is what makes lookup
  deterministic and prevents two users owning one phone number. Landlines are
  *not* unique — a household or an office shares one.
- **One primary per `(contact, kind)`.**
- `verified_at` is set when an OTP to that number succeeds. Contrast: a number
  typed by the shop is unverified, which is exactly the distinction that decides
  whether someone may log in as that person.

### `contacts.Address`

```python
class Address(BaseModel):
    contact     = models.ForeignKey(Contact, related_name="addresses", on_delete=models.CASCADE)
    label       = models.CharField(max_length=50, blank=True)   # "home", "site"
    line1       = models.CharField(max_length=255)
    line2       = models.CharField(max_length=255, blank=True)
    city        = models.CharField(max_length=100, blank=True)
    province    = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    plus_code   = models.CharField(max_length=32, blank=True)   # or lat/lng
    notes       = models.TextField(blank=True)   # "blue door, ring twice"
    is_primary  = models.BooleanField(default=False)
```

Only `line1` is required. Iranian addressing is not well served by a rigid
schema, and a delivery driver needs `notes` more than it needs `postal_code`.

## The flow: order for a phone number

`contacts.services.resolve_by_phone(phone, name=None) -> Contact`

1. Normalise the number. Reject anything that is not a plausible mobile.
2. Look up `ContactChannel(kind=MOBILE, value=normalised)`.
   - **Found** → return its contact. If `name` was given and `user.name` is
     blank, fill it in. Never overwrite a name the person set themselves.
   - **Not found** → in one transaction: create a `User` with no email, no
     usable password, `name=name or ""`; create its `Contact`; create the
     primary mobile `ContactChannel`, unverified.
3. **The order stores `FK → Contact`.** Decided: not `User`. A `Contact` is what
   the shop is actually pointing at, it survives a contact that never gets an
   account, and it is where the phone number and address the order needs already
   live. Reach the account, when there is one, through `order.contact.user`.
   Nothing in Pane should hold `FK → User` for a *customer*; staff records still
   go through `Profile` as usual.

Properties this gives us:

- **Idempotent.** Typing the same number tomorrow returns the same person.
- **Racy-safe.** The unique constraint on `(kind, value)` means a double submit
  raises `IntegrityError` rather than creating a twin; catch and re-fetch.
- **No orphans.** Every order has a real person behind it from day one, so the
  later login has something to attach to.
- **Survives an unclaimed person.** Because the order points at the contact, a
  customer who never signs in is not a special case anywhere in the order code.

### Claiming the account

A user created this way is a **provisional account**: no password, no verified
channel, cannot log in. It becomes claimable when an OTP is sent to that mobile
and succeeds — at which point `verified_at` is set and the person now controls
an account that already holds their history. No merging, no duplicate records,
no "link your orders" step.

Two rules worth writing down now, because they are the security story:

- **Only a verified channel grants a session.** The shop typing a number never
  authenticates anybody.
- **The shop can edit a contact it created; it cannot edit one that has been
  claimed**, beyond adding its own program-local notes. Once the person owns the
  account, their name and number are theirs.

## What this does not do

- No contact merging UI. Duplicates will happen (a landline typed as a mobile,
  a second number for the same person). Merging is a later tool, not a v1.
- No sharing of contacts between programs' *views* — the `Contact` row is
  shared, but whether a given program may read it is a permissions question
  deliberately left until a second program needs the same person.
- No import from the phone's address book.

## Order of work

1. `accounts` migration: `email` nullable, add `name`, manager for phone-created
   users. Touches existing rows — the one genuinely risky step.
2. `contacts` app: three models, normalisation, constraints, admin.
3. `resolve_by_phone`, with tests for the duplicate and race cases.
4. Pane orders point at `Contact` (`on_delete=PROTECT` — a contact with orders
   against it must not be deletable).
5. OTP login and claiming — after Pane's first release, per the Pane plan.
