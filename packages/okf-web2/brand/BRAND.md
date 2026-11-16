# OK, Fine Memory — Brand Kit

> **OK, fine, I’ll remember it for you.**

The source of truth for how OK, Fine Memory looks, sounds, and behaves. The app
(`packages/okf-web2`), its assets (`ASSETS_PROMPT.md`), docs, and anything
public-facing follow this file.

---

## 1. The idea

**OK, Fine Memory** is a memory for people and AI agents, kept as plain
markdown files in the [Open Knowledge Format](../../okf-core/SPEC.md). The name
is a backronym of **OKF**.

The brand is a **reluctant but completely reliable helper**: a kid's school
notebook that sighs, rolls its eyes a little, and then remembers everything,
perfectly, forever. The joke is the attitude. The product itself is dependable.

| | |
|---|---|
| **One-liner** | A notebook that remembers things for you and your agents. |
| **Tagline** | OK, fine, I’ll remember it for you. |
| **Short tagline** (≤ 20 chars) | Fine. Remembered. |
| **What it is** | Local-first knowledge base: markdown + YAML frontmatter in plain folders, browsable in a web UI, writable by agents over MCP. |
| **Who it's for** | Developers and teams who want their agents to keep notes they can read, diff, and own. |
| **Why it's different** | No database, no lock-in: if you can `cat` a file you can read your memory. |

### Personality

| We are | We are not |
|---|---|
| Dry, a bit reluctant, secretly delighted to help | Rude, sarcastic at the user, or lazy |
| Playful, hand-made, a little messy | Childish in substance, or sloppy with data |
| Plain-spoken and short | Jargon-heavy or wordy |
| Honest when things go wrong | Cute at the cost of clarity |

---

## 2. Name & wordmark

- Always write **OK, Fine Memory**: capital O, K, F, M; comma after *OK*; no period.
- Short form in tight spaces: **OK, Fine**. Technical contexts may say **OKF**.
- Never: *Ok Fine Memory*, *OK Fine Memory*, *OKFine*, *OK, fine memory*.
- The tagline is sentence case with a curly apostrophe: *OK, fine, I’ll remember it for you.*

---

## 3. Logo

### Concept: “Okie”, the reluctant snail

The mark is **Okie**, a small garden snail. Okie is slow, a little lazy, and
carries everything they remember on their back: the **shell is a spiral drawn
like the spiral binding of a school notebook**, with faint notebook rules
inside the whorl. Okie has **half-lidded eyes on wobbly eye-stalks**
(unimpressed), a **tiny flat mouth or a little sigh puff**, and often holds a
**pencil** or leaves a **pencil-drawn check mark** as their trail. They look
like they are about to say “fine.” They are never angry or sad, just mildly put
upon and completely reliable.

- **Shell:** yellow crayon (`#ffd23f`) scribble with an Ink spiral; in a
  workspace the shell may take that workspace's accent crayon.
- **Body:** paper-white with a pale pink (`#ff9fb6`) scribble on the belly line.
- **Trail:** a short wavy Ink line or check mark. It doubles as the underline motif.
- **Why a snail:** slow and reluctant on the outside, never loses anything
  that goes in the shell. That is the product.

#### Poses (for illustrations)

| Pose | Use |
|---|---|
| Sigh: eyes half-closed, sigh puff | logo mark, favicon |
| Writing: pencil on a notebook | saved / created |
| Reading: tiny glasses, open notebook | search, onboarding |
| Asleep: curled in shell, "z" squiggles | search off, idle |
| Shrug: eye-stalks drooping | empty state, no results |
| Oops: shell tipped over, crayons spilled | error |
| Wave: one eye-stalk waving | welcome, empty workspace list |

### Lockups

| Lockup | Use |
|---|---|
| **Mark** (Okie, sigh pose) | favicon, app icon, avatar, loading |
| **Horizontal**: mark + hand-lettered wordmark | app header, README, docs |
| **Stacked**: mark above wordmark + tagline | splash, social card, about page |
| **Wordmark only** | inline text-heavy places |

- The wordmark is **hand-lettered** in the spirit of Mali Bold, slightly tilted (−2°),
  with a **coral crayon underline** (`#ff7b6b`) under “OK, Fine Memory”.
- **Clear space:** at least the height of Okie's eye-stalks on every side
  (about ¼ of the mark height).
- **Minimum size:** mark 20 px; horizontal lockup 120 px wide.
- **Colour versions:** full colour on Paper; one-colour Ink; one-colour Paper (reversed on Ink).

### Don't

Don't stretch, re-colour the shell outside the palette, add gradients or drop
shadows, set the wordmark in a different font, straighten the tilt, make Okie
angry, crying, or winking, or turn them into a slug (the shell is the point).

---

## 4. Colour

Everything sits on **notebook paper**. Ink does the talking; crayons decorate.

### Core

| Token | Hex | Role |
|---|---|---|
| `ink` | `#2b3a67` | all text, outlines, icons |
| `paper` | `#fffef9` | page and card background |
| `rule` | `#c9dcf5` | notebook lines (every 32 px) |
| `margin` | `#ff9fb6` | the double margin line |
| `link` | `#d1345b` | links (wavy underline); hover `#a3123a` |
| `note` | `#fff6b8` | sticky-note blocks, concept bodies |

### Crayons

Workspace colours, fills, highlights, underlines, washi tape.

| Token | Hex | Default use |
|---|---|---|
| `yellow` | `#ffd23f` | primary button, title underline, highlight |
| `pink` | `#ff9fb6` | secondary button, folders, tags |
| `green` | `#9be564` | create / confirm, pages |
| `blue` | `#6aa8ff` | notebook cover, cancel |
| `red` | `#ff7b6b` | delete, the logo underline (`coral`) |
| `orange` | `#ffb703` | sun, stars, bullets |
| `purple` | `#b79cff` | flowers, accents |

### Rules

- **Text is always Ink** (`#2b3a67` on Paper ≈ 11:1 contrast). Never set text in a crayon colour; crayons are too light for text.
- Crayons are **scribbled fills** (zigzag hatching with paper showing through), not flat blocks. Flat fills only for tiny details (swatches, eyes).
- A workspace's **accent** is one crayon. It recolours that workspace's notebook cover, highlights, title underline, and tape. Everything else stays core.
- **Dark mode is a chalkboard**: `#2f4a3d` board, `#f1ede0` chalk text, faint chalk rules, yellow `#ffd98a` links. Crayon fills inside buttons and highlights are muted so they read as pastel chalk. Okie and the generated art keep their ink outlines, like stickers on the board. Theme tokens live in `src/app.css` (`:root` / `.dark`); the ☀/☾ toggle stores `okf-theme` in localStorage and follows the OS until the user picks one.
- **Intro**: on the first visit per tab, Okie crawls along a pencil trail, the name writes itself, the tagline types out with a "~ sigh ~", then the page lifts (about 3.3 s). Click or any key skips it. It is skipped under reduced motion; add `?intro` to the URL to replay it.

---

## 5. Typography

| Role | Font | Settings |
|---|---|---|
| Headings, buttons, labels | **Mali** 600/700 | tilt −1° to −2° on page titles |
| Body, inputs, lists | **Patrick Hand** 400 | 18 px / 32 px line height, so text sits on the notebook rules |
| IDs, paths, code | system `ui-monospace` | 0.85 em, on a light blue chip |

Both fonts support Vietnamese and ship self-hosted via `@fontsource`. Fallback:
`"Comic Sans MS", "Chalkboard SE", cursive`.

Scale: page title 36 px · section 24 px · body 18 px · small 14 px.

---

## 6. Illustration & icons

- Everything looks **drawn by a 7-year-old with a marker and a crayon box**:
  wobbly Ink outlines (2–3 px, round caps), lines sometimes drawn twice, crayon
  zigzag fills that spill past the line.
- **Okie the snail** appears in states and empty screens (see the poses in §3).
- Other subjects come from a school desk and a kid's world: notebooks, pencils,
  erasers, crayons, washi tape, stickers, sun, clouds, houses, flowers, stick figures.
- Icons: drawn on a 128 × 128 canvas and shown at 20–32 px; bold silhouette, Ink outline + one crayon.
- No gradients, no shadows, no 3D, no text inside images, nothing copied from
  existing characters or icon sets.
- In code, outlines and fills come from **rough.js** and marker annotations
  from **rough-notation**; static art (icons, Okie, decorations) comes from
  `src/assets/doodles/` as **transparent PNGs at about 4× display size**, generated
  with an image model from one Okie reference sheet so the character stays
  consistent. Only tiling pieces and the favicon are hand-written SVG.

---

## 7. UI motifs

| Motif | Where |
|---|---|
| Lined paper + pink double margin | page background |
| Spiral notebook with a name label | the explorer; each index is a notebook |
| Wobbly double outline | cards, header, dialogs |
| Crayon-filled buttons that wiggle on hover | all actions |
| Marker highlight / double underline | current item, page titles |
| Washi tape on corners | the main page sheet |
| Sticky note | concept body, messages |
| Highlighter swipe (pink, green, yellow in turn) | tags and types, with counts in small pencil |
| Margin doodles (sun, cloud, house, flower, stars) | large screens only |
| Inked arrow cursor; crayon pencil over anything clickable (text fields keep the I-beam) | everywhere (`src/app.css`) |
| Writing sits on the rules: lead copy snaps to the 32 px lines | landing hero, Get started |

### Motion

Small and physical: buttons **wiggle** (±4°, 0.4 s); pages **turn** on
navigation (slide + 1° rotate, 0.2 s); loading **opens a notebook**; skeletons
are **grey pencil scribbles** that breathe. All motion is off under
`prefers-reduced-motion`.

---

## 8. Voice & microcopy

Short. A little sigh, then help. The user is never the butt of the joke. Errors
always say what happened in plain words; the joke is optional, the information isn't.

| Moment | Copy |
|---|---|
| Tagline | OK, fine, I’ll remember it for you. |
| Loading | Opening the notebook… / Coming, coming… |
| Saved | Fine. Remembered. |
| Created | Fine, I’ll keep this one too. |
| Deleted | Erased. I’ll pretend I never knew. |
| Delete confirm | Erase *{id}*? I won't be able to un-know it. |
| Delete blocked | Other pages still point here: … Erase anyway and unlink them? |
| Moved | Moved it. Links are fixed, you're welcome. |
| Reindexed | Tidied up {n} listings. |
| Empty notebook | Nothing here yet. Tell me something and I’ll remember it. |
| About | I'm slow, but I don't forget. |
| Empty workspace list | No notebooks yet. Fine, let's start one. |
| No search results | I looked. Nothing. Try other words? |
| Search off | Search is napping. Set `OKF_EMBEDDING_URL` and `OKF_EMBEDDING_MODEL` to wake it up. |
| Read-only | Look, don't touch (read-only). |
| Error (generic) | Oops, I dropped my crayons: {message} |
| 404 | This page fell out of the notebook. |

Write UI copy in **English**, sentence case, curly quotes and apostrophes,
the ellipsis character (…), and no exclamation marks except “Oops!”.

---

## 9. Files

| Path | What |
|---|---|
| `brand/BRAND.md` | this guide |
| `brand/brand-board.html` | one-page visual board (open from disk) |
| `ASSETS_PROMPT.md` | brief for generating the icon and illustration set |
| `src/assets/doodles/` | generated assets: icons, Okie poses, decor, notebook pieces (PNG) |
| `brand/logo/` | mark, wordmark, lockups, app icon |
| `src/doodle/Sketch.tsx` | palette constants used in code (`ink`, `crayon`) |
