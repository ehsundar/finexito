# Pane — Apps & Price Estimation

**Status:** draft, 2026-09-21

The product is a price estimator with an order book attached, not an ERP. Every
decision below follows from that.

## Apps

```
orders      The spine. Order, status, totals, the contact it belongs to.
panes       Glass and mirror cut to size. Priced by area.
frames      Framing and mouldings. Priced by perimeter.
contracts   General work. A ticket, not a priced line — the owner rings them back.
```

`panes` and `frames` each own **one line type and one estimator**. They do not
know about each other, and `orders` does not know how either is priced — it sums
what they report. Adding a fourth kind of priced work later (UPVC, aluminium,
sand-blasting) is a new app with a line model and an estimator, and no change to
`orders`.

`contracts` is not like the other two. It holds no line type and no estimator at
all — see below.

## Orders

```python
class OrderStatus(models.TextChoices):
    ESTIMATE  = "estimate"    # priced, not committed
    CONFIRMED = "confirmed"   # customer said yes
    IN_WORK   = "in_work"
    READY     = "ready"
    COLLECTED = "collected"
    CANCELLED = "cancelled"

class Order(BaseModel):
    contact      = FK(contacts.Contact, on_delete=PROTECT, related_name="orders")
    number       = CharField(unique=True)        # human-facing, sequential
    status       = CharField(choices=OrderStatus, default=ESTIMATE)
    promised_for = DateField(null=True, blank=True)
    notes        = TextField(blank=True)

    discount     = MoneyField(default=0)
    discount_reason = CharField(blank=True)
    deposit      = MoneyField(default=0)

    subtotal     = MoneyField(default=0)   # denormalised, recomputed on line change
    total        = MoneyField(default=0)
```

**An estimate is an order in the `estimate` state.** There is no separate
`Estimate` model — that would duplicate every line type and every pricing path
for no gain. An estimate the customer declines simply stays in that state, and
is still worth having.

### The line base

In `orders`, abstract, inherited by each product app:

```python
class OrderLine(BaseModel):
    class Meta:
        abstract = True

    order       = FK(Order, related_name="%(class)s_lines", on_delete=CASCADE)
    position    = PositiveIntegerField(default=0)
    quantity    = PositiveIntegerField(default=1)
    description = CharField(blank=True)     # what prints on the bench slip

    unit_price  = MoneyField()              # snapshot, see below
    line_total  = MoneyField()
    breakdown   = JSONField(default=dict)   # how unit_price was reached

    def estimate(self) -> Estimate: ...     # each app implements
```

`Order.lines()` gathers across the concrete line models and sorts by `position`.
Three small queries beats a generic foreign key.

## Price estimation

This is the part that has to be right.

### One rule: prices are snapshotted

An estimator is a **pure function** of its inputs and the price list as it
stands *now*. The moment a line is saved, the computed `unit_price` and a full
`breakdown` are written onto the line.

Why this matters more than anything else here: the glass supplier raises prices
next month. Every past order must keep the price it was quoted at, and reopening
a six-week-old order must not silently reprice it. Recalculation happens only
when someone edits the line, and the UI says so.

`breakdown` is the audit trail and the thing that makes the number explicable to
a customer standing at the counter:

```json
{
  "material": "mirror-4mm", "rate_per_sqm": 4200000,
  "width_mm": 900, "height_mm": 600,
  "area_sqm": 0.54, "billed_area_sqm": 0.56,
  "base": 2352000,
  "extras": [{"code": "bevel", "qty_m": 3.0, "amount": 900000}],
  "minimum_charge_applied": false,
  "rounding": -2000,
  "unit_price": 3250000
}
```

### The shared vocabulary

In `orders` (or `common`), used by all three estimators:

- **`Money`** — integer Toman. No floats anywhere near a price.
- **`PriceList` / rate lookup** — each app owns its own rate table, but they
  share the convention: a rate is versioned by `effective_from`, never edited in
  place, so a snapshot can always be explained after the fact.
- **`Extra`** — a named add-on with a unit (`per_item`, `per_metre`, `per_sqm`,
  `flat`) and a rate. Bevelling, drilled holes, polished edge, backing board,
  fitting. Each app declares which extras apply to it.
- **Rounding** — one rule, configured per deployment, applied last.

### `panes` — priced by area

```python
class GlassMaterial(BaseModel):     # "4mm mirror", "6mm clear", "10mm tempered"
    name, thickness_mm, kind (glass|mirror|laminated|tempered)
    rate_per_sqm, minimum_charge, min_billed_sqm
    waste_factor = DecimalField(default=1.0)

class PaneLine(OrderLine):
    material   = FK(GlassMaterial, on_delete=PROTECT)
    width_mm   = PositiveIntegerField()
    height_mm  = PositiveIntegerField()
    shape      = CharField(choices=rect|circle|oval|arch|custom, default=rect)
    extras     = M2M through PaneLineExtra
```

Estimator:

1. `area = w × h / 1e6`, per unit.
2. `billed_area = max(area × waste_factor, material.min_billed_sqm)` — a shop
   loses money on small awkward pieces, and this is where it stops.
3. `base = billed_area × rate_per_sqm × quantity`.
4. Add extras: `per_metre` ones bill against the perimeter (edge polishing,
   bevelling), `per_item` ones against `quantity` (each drilled hole).
5. `max(total, minimum_charge)`, then round.

Non-rectangular shapes bill on the bounding box, plus a shape surcharge — that
is what the trade actually does and it keeps one formula.

### `frames` — priced by perimeter

```python
class Moulding(BaseModel):
    name, code, width_mm, rate_per_metre, wastage_allowance_mm

class FrameLine(OrderLine):
    moulding   = FK(Moulding, on_delete=PROTECT)
    width_mm, height_mm
    mount      = FK(MountBoard, null=True)   # passepartout
    backing    = FK(BackingBoard, null=True)
    labour     = FK(LabourRate, null=True)
    extras     = M2M through FrameLineExtra
```

Estimator:

1. `perimeter = 2 × (w + h) / 1000`, in metres, of the *outer* frame — remember
   the moulding width adds to the opening on each side, which is the classic
   way to under-quote a frame.
2. `moulding_cost = (perimeter + wastage_allowance) × rate_per_metre` — mitre
   cuts waste moulding, and the allowance is per join, not a percentage.
3. Add mount and backing, both priced by area of the same opening.
4. Add labour: a flat assembly rate per frame, from a small table by size band.
5. × quantity, then round.

**Glass in a frame is a separate `PaneLine` on the same order.** Frames do not
reach into `panes`. The counter UI offers "add the glass for this" as a
shortcut that pre-fills a pane line with the same dimensions, but the two lines
stay independent and are priced independently.

### `contracts` — general work, not priced

Site work, installation, a shopfront, a balustrade: things nobody can price from
a form, and nobody should try to. So `contracts` does not price anything. It is
a **ticket that reminds the owner to ring someone back**.

```python
class ContractStatus(models.TextChoices):
    NEW     = "new"        # came in, nobody has called yet
    CALLED  = "called"     # spoken to them
    QUOTED  = "quoted"     # price given, verbally or on paper
    WON     = "won"
    LOST    = "lost"

class Contract(BaseModel):
    contact    = FK(contacts.Contact, on_delete=PROTECT, related_name="contracts")
    title      = CharField()                  # "balustrade, second-floor flat"
    body       = TextField()                  # whatever they said, in his words
    photos     = ...                          # a phone photo of the site
    status     = CharField(choices=ContractStatus, default=NEW)
    call_back_on = DateField(null=True, blank=True)
    rough_price  = MoneyField(null=True, blank=True)   # optional, typed by hand
    order      = FK(Order, null=True, blank=True, on_delete=SET_NULL)
```

Notes on the deliberate omissions:

- **No basis, no rate, no units.** If a job can be reduced to a rate × a
  quantity, it is a pane line or a frame line, not a contract.
- **`rough_price` is typed, never computed.** It exists only so the number he
  quoted on the phone is written down somewhere before he forgets it.
- **`order` is optional and set later.** When a contract turns into real work,
  he raises an order in the usual way; the link just keeps the history joined up.
- The only screen it needs is a list: **who is waiting for a call**, oldest
  first, with overdue callbacks at the top. That is the entire feature.

`Contract` is a sibling of `Order`, not a line on one. Trying to make it a line
would drag pricing, quantities and statuses into something that is really just a
note with a phone number attached.

## The estimator API

One endpoint, callable without saving anything:

```
POST /api/pane/estimate
{ "kind": "pane", "material": "<uuid>", "width_mm": 900, "height_mm": 600,
  "quantity": 2, "extras": [{"code": "bevel"}] }

→ { "unit_price": 3250000, "line_total": 6500000, "breakdown": {...} }
```

This is what makes the app worth opening: the owner types two numbers and gets a
price he can say out loud, before any customer has committed to anything and
before a record exists. The order form uses the same endpoint on every keystroke,
so the price updates live as he types the dimensions.

## Deliberately not now

Off-cut register, stock levels, SMS, customer login, reports. All still wanted
(see the catalogue), all after the estimator earns its keep.
