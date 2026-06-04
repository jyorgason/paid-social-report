# Fonts

Fabric uses two webfonts:

- **Fields** — BambooHR's proprietary display serif. Weights: **400** (Regular), **600** (SemiBold), **700** (Bold). Used for h1–h4.
- **Inter** — Open-source UI sans-serif. Weights: 400, 500, 600, 700. Used for all body copy, UI, and h5–h6.

## Where the files live

- **Fields** — bundled locally in this folder. Source formats shipped: `.woff2` (browser), `.ttf` (fallback), `.otf` (for design-tool use). `colors_and_type.css` loads the woff2 with a ttf fallback.
- **Inter** — loaded from Google Fonts via `@import` in `colors_and_type.css` (same font, open source — no substitution).
- **Source Code Pro** — loaded from Google Fonts alongside Inter. Used for the mono stack.

## Deprecated

- Lato, Ephesis — legacy Fabric fonts, do not use.
