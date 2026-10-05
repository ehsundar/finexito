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
| `brand/mark-mono.svg` | One-colour mark (`currentColor`). |
| `frontend/src/components/app/mark.tsx` | The mark (a door left open), drawn once: in the app header, and in the app's icons. |
| `frontend/src/app/colours.css` | Every colour: the palette, and the light and dark themes made from it. The only file with colour values in it. The mark and the app's icons (favicon, iPhone, installed app) take theirs from it too: the icons are drawn when the app is built (`frontend/src/app/brand-icon.tsx`), so a new palette needs no new image files. The guide reads it too. |
| `frontend/src/app/layout.tsx` | The typeface, loaded with `next/font`. |

## Finexito at a glance

- **Idea:** a door left open — the financial exit.
- **Colours:** navy, sky and azure (the door), cobalt, paper and cream, slate,
  and gain, loss and caution; their values are in `colours.css`. Blue is only
  ever the door and the primary action; gain stays green.
- **Type:** Inter 400/500/600; headings in 500; tabular figures for money.
- **Voice:** plain, calm, real numbers, no exclamation marks.
