# Brand

The look of this deployment: logo, colours, type and voice. Open
[`guide.html`](guide.html) in a browser for the full guide.

This repository ships as Finexito, the showcase product. A fork becomes a new
product by replacing the files below; nothing else in the code carries the
brand, and the product's name always comes from `FINEXITO_SITE_NAME`.

## Files a fork replaces

| File | What it is |
| --- | --- |
| `brand/guide.html` | The brand guide: idea, logo rules, palette, type, voice. |
| `brand/colours.json` | The palette, and the light and dark themes built from it (same keys as `globals.css`). |
| `brand/logo-light.svg`, `brand/logo-dark.svg` | Logo with wordmark, for documents and marketing. |
| `brand/app-icon.svg` | App icon in its tile. |
| `brand/mark-mono.svg` | One-colour mark (`currentColor`). |
| `frontend/public/brand/mark.svg` | The mark beside the site name in the app header. |
| `frontend/src/app/icon.svg` | Favicon. |
| `frontend/public/brand/icon-192.png`, `icon-512.png` | App icon for the installed app (from `brand/app-icon.svg`). |
| `frontend/src/app/apple-icon.png` | App icon on an iPhone's home screen, 180×180. |
| `frontend/src/app/globals.css` | The palette, as the theme's colour variables (`:root` and `.dark`). |
| `frontend/src/app/layout.tsx` | The typeface, loaded with `next/font`. |

## Finexito at a glance

- **Idea:** a door left open — the financial exit.
- **Colours:** Navy `#0B1B33`, Sky `#5AA9FF` (the door on dark), Azure
  `#2F7BEA` (the door on light), Cobalt `#1A56C4` (blue text), Paper `#FBFAF6`,
  Cream `#F3EFE6`, Harbour `#17305A`; Slate `#3B4658` `#5F6B7D` `#C7CDD6` `#E6E9EE`;
  Gain `#12805C`, Loss `#C8413A`, Caution `#9C6500`. Blue is only ever the door
  and the primary action; gain stays green.
- **Type:** Inter 400/500/600; headings in 500; tabular figures for money.
- **Voice:** plain, calm, real numbers, no exclamation marks.
