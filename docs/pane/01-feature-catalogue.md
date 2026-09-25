# Pane — Feature Catalogue

Every feature worth considering, graded. Grades are about *this* customer, a
single-site workshop, not about a general product.

- **Must** — without it the app is not worth opening.
- **Should** — the reason he keeps using it after month one.
- **Later** — real value, but only once the basics stick.
- **No** — tempting, wrong for him. Written down so we stop re-proposing them.

> **Scope note (2026-09-21).** This catalogue is the long list — everything
> worth considering eventually. The actual build is much narrower: four apps
> (`orders`, `panes`, `frames`, `contracts`) with price estimation as the point.
> See [Apps & Price Estimation](03-apps-and-pricing.md) for what is being built.
> Read this file as the backlog, not the plan.

---

## 1. Orders — the spine

### Must

**Take an order.** Customer name + phone, one or more items, promised date,
notes. Nothing else required. Must be completable in under a minute on a phone.

**Line items with real measurements.** Each item is: type (mirror, table top,
counter, window pane, frame, shelf), material, width mm, height mm, quantity.
Area and price computed from those, never typed by hand. Shapes beyond
rectangles (circle, oval, arch, free-form) carry a diameter or a note plus a
photo.

**Order status.** A fixed, short pipeline the whole shop shares:
`draft → confirmed → in workshop → ready → collected`. Plus `cancelled`.
No configurable workflows.

**Search and find.** By customer name, phone, order number, or date. This is
what replaces "let me check the notebook".

**Order note + photo attachment.** A phone photo of a sketch, an old frame, or
the room, attached to the order. This is the single highest-value field for a
framing shop and costs almost nothing to build.

### Should

**Deposit and balance.** Amount paid up front, amount owing, marked paid on
collection. Not accounting — just "does he still owe me money?".

**Promised-date board.** Today / this week / overdue. The overdue list is the
one screen that prevents an angry customer.

**Reprint/reshare the order slip.** A clean printable summary with the
measurements, for the workshop bench and for the customer.

### Later

**Repeat order.** Duplicate a past order for a customer who wants the same again
— common with shops and offices ordering replacement glass.

**Multi-stage jobs.** Cut → bevel → drill → polish → frame, each ticked off by
whoever did it. Only useful once more than two people work the bench.

---

## 2. Pricing and quoting

### Must

**Material price list.** Each material (4 mm mirror, 6 mm clear, 10 mm tempered,
MDF frame profile no. 12 …) has a price per m², or per metre for mouldings.
Editing one number re-prices every future quote — this alone is worth the app.

**Automatic price calculation.** area × rate, plus per-item extras (bevelling,
drilled holes, polished edge, backing board, mounting), plus a minimum charge
for small pieces. Rounding rule set once, applied everywhere.

**Manual override with a reason.** He *will* discount for a friend. Let him, and
record it, so the reports still make sense.

### Should

**Quote before order.** A quote that can be sent by SMS/WhatsApp link and turned
into an order with one tap if accepted. Quotes that are never accepted are
themselves useful data.

**Waste factor.** Charge on the glass actually consumed, not only the finished
size, for awkward cuts. This is where shops quietly lose money.

### Later

**Price tiers.** Trade price for the carpenters and builders who come weekly vs
walk-in price. Simple flag on the customer.

---

## 3. Materials, stock and off-cuts

### Should

**Sheet stock.** How many full sheets of each material are in the rack, with a
low-stock warning. Kept deliberately crude: counts, not a warehouse system.

**Off-cut register.** The genuinely distinctive feature for a glass shop: every
usable remnant recorded as material + width × height + where it is stored, and
searchable as *"do I have something at least 600 × 400 in 4 mm mirror?"* before
cutting a new sheet. Turns scrap back into money and is the feature most likely
to make him say "ah, I see".

### Later

**Consume stock on order.** Deduct sheets/off-cuts when a job is cut, so stock
figures stay true on their own.

**Supplier orders.** What he ordered from the glass supplier, when it is due.

### No

Barcodes, batch tracking, serial numbers. A one-site workshop will never scan
anything.

---

## 4. Customers

### Must

**Customer record.** Name, phone, and their order history on one screen. Backed
by the platform's shared `Contact` (mobile, landline, addresses) — see
[Contacts & Identity](../platform/01-contacts-and-identity.md). Typing a phone
number on an order finds the existing person or creates a provisional account
for them. Phone number is the identity, whether or not the customer ever signs in — the shop
creates the record by typing a phone number, and a later login attaches to the
same record rather than making a second one.

### Should

**Notes per customer.** "Pays late", "always wants bevelled edges", the builder's
site address.

**Optional customer login.** Phone number + one-time code by SMS. No passwords,
no email, no sign-up form. Three deliberate rules:

1. **Never required.** An order can always be placed at the counter with nothing
   but a phone number, and the SMS tracking link always works without signing in.
   A customer who never logs in loses nothing except history.
2. **Same phone, same person.** Logging in claims the existing customer record
   the shop already created, along with every past order on it.
3. **Read-mostly.** Signed in, a customer sees their orders, statuses, promised
   dates, balance owing, and the photos and measurements on each job. They can
   update their own name and notes. They cannot change prices or measurements.

Why it is worth more than SMS alone: repeat customers — builders, carpenters,
offices — stop phoning to ask "what were the measurements last time?" and can
answer it themselves. It also gives the shop a real customer list rather than a
pile of phone numbers.

This reuses the platform's existing `User` — the account already exists, created
provisionally when the shop first took their order — plus a customer-role Pane
`Profile`. The work is the OTP flow that claims that account and the role split,
not a second auth system.

### Later

**Trade customers.** Multiple contacts under one business, monthly statement of
what is owed.

**Request a quote while signed in.** A returning customer submits measurements
themselves and the shop prices it. Only worth building once logins are actually
being used — otherwise it is a form nobody opens.

---

## 5. Communication

### Should

**"Your order is ready" SMS.** Sent on the status change, with a short tracking
link. Directly removes the phone calls that interrupt his day. Needs an Iranian
SMS gateway (Kavenegar / SMS.ir).

**Public order tracking page.** No login; the link in the SMS shows status,
promised date, and balance owing for that one order. One page, nothing else.
It carries a quiet "see all your orders" prompt that starts the optional login —
the only place we ever ask.

### Later

**Promised-date reminder** the day before, and a nudge on pieces uncollected for
two weeks — collected glass sitting in the shop is his floor space.

### No

In-app chat. He has WhatsApp and a phone; he does not want a second inbox.

---

## 6. Workshop view

### Should

**Job queue on a tablet.** Today's cuts, largest first, with measurements in big
type and a "done" button. No prices on this screen — staff should not see
margins.

### Later

**Per-person workload**, once there is more than one bench worker.

---

## 7. Money and reports

### Should

**This month at a glance.** Orders taken, value, collected, outstanding. Four
numbers on the home screen, not a dashboard.

**Outstanding balances list.** Who owes what. The report he will actually open.

### Later

**What sells.** Revenue by material and by item type over time — tells him what
to stock and where his margin really is.

**Off-cut savings.** Value of remnants reused. Proves the app paid for itself.

### No

Full accounting, VAT returns, payroll, integration with his accountant's
software. Out of scope, permanently.

---

## 8. Platform and admin

### Must

**Logins with three roles** — owner (everything), staff (job queue, no prices),
customer (own orders only, optional). All on the platform's existing auth;
staff sign in the usual way, customers by SMS one-time code.

**Persian, RTL, Jalali dates, Toman amounts.**

**Shop identity.** Shop name, logo, address and phone held
as settings, used on the printed slip, the tracking page and the SMS. "Pane" is
our codename and must never be visible to the shop or its customers.

**Works on a phone**, offline-tolerant enough to survive the shop's patchy wifi
for the length of one form.

### Later

**Audit trail** — who changed a price or a status, and when. Matters the moment
he has staff he does not fully trust.

**Data export** to Excel, so he never feels locked in. Cheap to build, good for
trust.

### No

Multi-branch, multi-currency, a customer-facing online shop, an "AI" anything.
Not until a second customer asks.

---

## What to build first

Narrower than everything above. The whole first release is the estimator plus
the thinnest order book that makes it useful:

1. Rate tables — glass per m², mouldings per metre, a handful of extras.
2. The estimate endpoint: type dimensions, get a price, save nothing.
3. Orders with `pane` and `frame` lines, priced and snapshotted.
4. Status pipeline and the today/overdue board.
5. Contact lookup by phone.
6. Printable bench slip.
7. Contracts: a call-back list for the general work that cannot be priced from
   a form.

Everything else on this page — off-cuts, stock, SMS, customer login, reports —
waits until he is pricing real jobs in it every day.

Customer login is explicitly *not* in that first release: the SMS tracking link
carries the same value for a tenth of the work, and it is the right thing to
build second, once there are real orders for a customer to log in and look at.

The one feature worth showing him early, to win him over, is the off-cut
register — it is the one he will not have imagined.
