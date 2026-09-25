# Pane — Product Brief

**Status:** draft, 2026-09-21
**Customer:** a frame workshop and glass cutting shop, the first Pane customer.

## The name

**Pane** is a working codename for the product, not a brand for the shop. The
shop trades under its own name and that is the name that appears in the UI,
on printed slips and in customer SMS. Pane is what we call the codebase, the
repo directory and the Program record — deliberately generic, because the same
software should fit the next workshop without a rename.

## What Pane is

A web app that runs one workshop's order book: from the moment a customer walks
in with a measurement to the moment the finished piece is collected and paid for.

It is **not** a shop front and **not** accounting software. It is the thing that
replaces the paper notebook, the tape measure scribbles, and the "which job was
that glass for?" phone calls.

## Why this customer needs one

The shop owner has not asked for software and does not know what it would do for
him. So the brief starts from the problems a shop like his actually has:

| Everyday pain | What it costs him | What Pane does about it |
| --- | --- | --- |
| Orders live on paper slips | Slips get lost; jobs get forgotten | One order record per job, searchable |
| Measurements written by hand | Mis-cuts from a misread "7" vs "1" | Structured width × height × quantity fields |
| Price worked out in his head each time | Inconsistent quotes, undercharging | Price rules per material and per m² |
| Off-cuts pile up unused | Money sitting in the corner as scrap | Off-cut register, searchable by size |
| "Is my mirror ready?" phone calls | Interruptions all day | Status per order + SMS on ready |
| No idea what sells or what he earned | Cannot plan stock or price | Simple monthly figures |

## Who uses it

- **Owner** — sees everything: orders, prices, money, reports.
- **Workshop staff** — see today's job queue, mark work done. No prices.
- **Front desk** (may be the owner) — takes orders, quotes, takes payment.
- **Customer** — optional login. An SMS link tracks one order with no account
  at all; signing in with the same phone number (OTP) unlocks their full
  history. Never forced, never a barrier to placing an order.

## Success, after three months

1. Every new job is entered in Pane, no paper slip.
2. A quote takes under a minute and is the same price for the same job twice.
3. He can answer "is it ready?" without walking to the back.
4. He can see what he earned last month without adding anything up.

## Shape of the build

This is a **Program** on the existing platform, not a new codebase: it reuses
`User` for identity and a Pane `Profile` per staff member, and adds its own
domain models (Order, Item, Material, Price rule, Off-cut). The frontend is a
new route group in the Next.js app.

Persian UI, right-to-left, Jalali dates, Toman prices. Phone-first: the owner
will use this standing at a bench, not sitting at a desk.
