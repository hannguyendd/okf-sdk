# Asset brief for OK, Fine Memory (paste to Codex)

You are creating the original icon, illustration and brand asset set for
**OK, Fine Memory** (tagline: *“OK, fine, I’ll remember it for you.”*), a local
web UI for a markdown knowledge base. Work in `packages/okf-web2/` on branch
`okf-web-v2`.

**Read first. These are the source of truth:**

- `packages/okf-web2/brand/BRAND.md`: name, mascot, palette, type, style, voice.
- `packages/okf-web2/brand/brand-board.html`: visual board (open in a browser).
  Its inline snail is a rough placeholder; your Okie replaces it.

**Ignore** the repo-root folder `assets/branding/` (flat orange note-face
concept). It is a rejected direction; do not reuse its style, colours, or
character, and do not modify or delete it.

Only add files under the paths listed below. Do not modify source code,
`BRAND.md`, or `brand-board.html`.

---

## How to make the images

Use your **`image_gen`** tool for all artwork (icons, illustrations, logo).
Use code (SVG written by hand) only where noted (tiling pieces, favicon SVG).
Use `magick` (ImageMagick) and `rsvg-convert`, both installed, for slicing,
background removal, resizing and export.

### Style anchor: prepend to every image_gen prompt

> Children's marker-and-crayon doodle, as if drawn by a 7-year-old in a school
> notebook. Wobbly, slightly uneven dark navy ink outlines (#2b3a67) of even
> marker thickness with round ends; some lines drawn twice and slightly
> offset. Colour filled with visible crayon scribble strokes (zigzag
> hatching) that leave small gaps and spill a little past the outlines. Only
> these colours: navy ink #2b3a67, white, crayon yellow #ffd23f, pink #ff9fb6,
> green #9be564, blue #6aa8ff, coral red #ff7b6b, orange #ffb703, lavender
> #b79cff. Flat, no gradients, no shadows, no 3D, no texture background, no
> paper lines, no text, no letters, no watermark. Isolated on a plain flat pure
> white (#ffffff) background with generous margin. Charming, simple, original.

If `image_gen` supports transparent backgrounds, ask for transparent instead
of white and skip the background-removal step.

### Okie first: the character sheet

Before anything else, generate **`src/assets/doodles/_sources/okie-reference.png`**:
a character turnaround sheet of **Okie** (front-ish 3/4 view, side view, close-up
of the face), using the style anchor plus:

> Okie is a small garden snail. Shell: round, coloured with yellow crayon
> scribble, with a navy spiral whorl drawn like the spiral binding of a school
> notebook. Body: white with a dashed pink line along the belly. Two wobbly
> eye-stalks with round white eyes whose upper lids are half closed (a bored,
> unimpressed, mildly put-upon look, never angry or sad). Tiny flat mouth. A
> small sigh puff near the mouth. Behind the snail, a short trail drawn as a
> wavy navy line ending in a pencil check mark.

Then **pass `okie-reference.png` as the reference image to every later Okie
image** and keep proportions, colours and face identical. If a result drifts
(different face, missing shell, extra limbs, text), regenerate it.

### Sheets for small items

For icons and bullets, generate **sheets** (a 4 × 4 grid of separate items,
evenly spaced, one item per cell, same stroke weight across the sheet) so the
set looks consistent, then slice the cells. Keep every sheet in
`src/assets/doodles/_sources/` (`icons-sheet-1.png`, `icons-sheet-2.png`, …).

### Post-processing (every PNG)

1. **Remove the white background by flood-filling from the corners only**, so
   white inside the drawing (Okie's body, eyes) stays opaque:
   `magick in.png -alpha set -fuzz 10% -fill none -draw "color 0,0 floodfill" -draw "color %[fx:w-1],0 floodfill" -draw "color 0,%[fx:h-1] floodfill" -draw "color %[fx:w-1],%[fx:h-1] floodfill" out.png`
   (if `%[fx:…]` doesn't expand inside `-draw` in your ImageMagick version,
   read the size with `magick identify` and pass numbers). Never use a global
   `-transparent white`. Check for leftover white halos; trim with `-trim +repage`.
2. **Fit** to the target canvas: `-resize WxH -gravity center -background none -extent WxH`, keeping a small even margin.
3. **Optimise**: `-strip -define png:compression-level=9`. Stay within the size budgets.
4. **Look at the result** before moving on: correct item, no text, background gone, style matches.

---

## Deliverables

All PNGs have a transparent background unless stated. Sizes are the final
canvas (≈ 4× the display size, for sharp rendering on Retina).

### 1. UI icons: `src/assets/doodles/icons/` (PNG 128 × 128, < 12 KB each)

Bold simple silhouettes that still read at 20–32 px. Ink outline + one crayon.

| File | Content |
|---|---|
| `folder-closed.png` | closed folder, pink |
| `folder-open.png` | open folder with a page peeking out, pink |
| `page.png` | sheet with folded corner + 2 scribble lines, green |
| `notebook.png` | small spiral notebook, blue cover |
| `search.png` | magnifying glass, blue lens |
| `pencil.png` | pencil, yellow body, pink eraser |
| `move.png` | curly arrow hopping from one box to another |
| `eraser.png` | pink eraser with crumbs |
| `refresh.png` | two curved arrows in a loop |
| `plus.png` | chunky plus in a wobbly circle, green |
| `chevron.png` | hand-drawn arrow pointing right |
| `collapse.png` | two arrows squeezing together |
| `close.png` | scribbled X |
| `link.png` | two chain loops |
| `tag.png` | luggage tag with a hole |
| `palette.png` | three crayons fanned out |
| `warning.png` | wobbly triangle with an exclamation (a stroke + a dot, not a letter) |
| `check.png` | pencil check mark |

### 2. Bullets: `src/assets/doodles/bullets/` (PNG 64 × 64, < 6 KB each)

`star.png` (orange), `heart.png` (pink), `flower.png` (green petals, yellow
centre), `dot.png` (blue scribbled dot), `snail-shell.png` (tiny yellow spiral shell).

### 3. Okie poses: `src/assets/doodles/okie/` (PNG 960 × 720, < 120 KB each)

Same Okie as the reference sheet (BRAND.md §3):

| File | Pose / use |
|---|---|
| `okie-sigh.png` | eyes half-closed, sigh puff (default) |
| `okie-writing.png` | writing in a tiny notebook with a pencil (saved / created) |
| `okie-reading.png` | tiny round glasses, reading an open notebook (search) |
| `okie-asleep.png` | curled in the shell, "z" shapes drawn as squiggles (search off) |
| `okie-shrug.png` | eye-stalks drooping sideways, small empty notebook (empty, no results) |
| `okie-oops.png` | shell tipped over, crayons spilled (error) |
| `okie-wave.png` | one eye-stalk waving, other eye half-lidded (welcome) |
| `okie-lost-page.png` | watching a torn notebook page blow away (404) |
| `okie-loading.png` | crawling, short check-mark trail behind (loading) |

### 4. Margin decorations: `src/assets/doodles/decor/` (PNG, < 100 KB each)

| File | Canvas | Content |
|---|---|---|
| `sun.png` | 512 × 512 | smiling sun, orange rays |
| `cloud.png` | 640 × 384 | white cloud, ink outline |
| `house.png` | 512 × 512 | pink walls, red roof, blue door, yellow window |
| `flower.png` | 384 × 640 | tall stem, lavender petals |
| `rainbow.png` | 768 × 448 | five crayon arcs |
| `paper-plane.png` | 512 × 512 | paper plane with a dashed flight path |
| `tree.png` | 512 × 640 | green scribble crown, simple trunk |
| `balloon.png` | 384 × 640 | red balloon, wiggly string |
| `stars-cluster.png` | 512 × 512 | three stars of different sizes |
| `leaf.png` | 384 × 384 | green leaf (Okie can sit near it) |
| `kid-reading.png` | 512 × 512 | stick-figure kid reading a book |
| `kid-running.png` | 512 × 512 | stick-figure kid running |

### 5. Notebook pieces: `src/assets/doodles/notebook/`

| File | Format | Content |
|---|---|---|
| `spiral-ring.svg` | **SVG by hand**, viewBox `0 0 34 30` | one spiral-binding ring over a punched hole; must tile vertically with no seam. Ink `#2b3a67` outline, grey `#7c8598` wire |
| `name-label.png` | PNG 880 × 280 | blank school-notebook name label: scalloped edge, pink dashed border, white inside |
| `washi-yellow.png`, `washi-pink.png`, `washi-green.png`, `washi-blue.png` | PNG 480 × 112 | washi-tape strip, torn ends, simple stripes, light tints, slightly see-through look |
| `notebook-cover.png` | PNG 480 × 360 | closed spiral notebook, blue cover, small blank name label |
| `notebook-open.png` | PNG 640 × 360 | the same notebook open, lined pages |
| `sticky-note.png` | PNG 640 × 640 | blank sticky note (`#fff6b8`), slightly curled corner |

### 6. Brand: `brand/logo/`, `brand/`, `public/`

The wordmark is lettering, so for these files **text is allowed** and must be
spelled **exactly** `OK, Fine Memory` (capital O, K, F, M; one comma; no
period) and the tagline exactly `OK, fine, I’ll remember it for you.` Check the
spelling of every result character by character; regenerate on any mistake.
Lettering style: chunky friendly hand-lettering like a kid's best handwriting
with a marker, tilted about −2°, Ink colour, with a coral (`#ff7b6b`) double
crayon underline under the name.

| File | Format | Content |
|---|---|---|
| `brand/logo/mark.png` | PNG 1024 × 1024 | Okie, sigh pose, centred: the primary mark |
| `brand/logo/mark-mono-ink.png` | PNG 1024 × 1024 | same mark, navy ink lines only, no colour fills |
| `brand/logo/mark-mono-paper.png` | PNG 1024 × 1024 | same mark, `#fffef9` lines only, for dark backgrounds (show it on `#2b3a67` in the preview) |
| `brand/logo/mark.svg` | **SVG by hand**, viewBox `0 0 128 100` | a simplified vector Okie matching `mark.png` (shell + spiral, eye-stalks with half-lidded eyes, body), for scaling and the favicon |
| `brand/logo/wordmark.png` | PNG 2048 × 360 | hand-lettered `OK, Fine Memory` + coral underline |
| `brand/logo/lockup-horizontal.png` | PNG 2400 × 400 | mark left, wordmark right |
| `brand/logo/lockup-stacked.png` | PNG 1600 × 1100 | mark above wordmark above the tagline (smaller lettering) |
| `brand/logo/app-icon.png` | PNG 1024 × 1024, **opaque** | Okie mark centred on a `#fffef9` rounded square with faint blue notebook rules (`#c9dcf5`) and a pink double margin line (`#ff9fb6`), transparent outside the rounded square |
| `brand/social-card.png` | PNG 1200 × 630, **opaque** | lined-paper background (`#fffef9`, `#c9dcf5` rules, pink margin), stacked lockup left, `okie-writing` right, washi tape on two corners |
| `public/favicon.svg` | **SVG by hand**, viewBox `0 0 32 32` | Okie's shell + eye-stalks only, thick strokes, readable at 16 px |
| `public/favicon-32.png` | PNG 32 × 32 | from `favicon.svg` via `rsvg-convert` |
| `public/apple-touch-icon.png` | PNG 180 × 180, opaque | from `app-icon.png` |

### 7. Manifest + preview

- `src/assets/doodles/manifest.json`: `{ "<path relative to packages/okf-web2>": { "size": "WxH", "description": "..." } }` for every file you made (including `brand/` and `public/`, excluding `_sources/`).
- `src/assets/doodles/preview.html`: a static page showing every asset on
  lined paper (`#fffef9`, `#c9dcf5` rules every 32 px, pink margin line),
  grouped by folder, each labelled with its path; icons shown at 128 px and at
  32 px; brand marks also on an Ink (`#2b3a67`) background. Must open directly
  from disk with no build step.

---

## Done when

- Every file above exists at the exact path, with the given size and budget.
- Okie is clearly the **same character** in every pose, the logo and the app icon.
- No stray text anywhere except the brand lettering, and that is spelled exactly right.
- Backgrounds are clean (no white boxes or halos) when viewed on lined paper in `preview.html`.
- You report any file you could not produce and why, instead of silently skipping it.

Suggested order: §0 Okie reference → §6 brand → §3 Okie poses → §1 icons → §2
bullets → §5 notebook → §4 decor → §7 manifest & preview. Stop after §6 if
asked to work in batches.
