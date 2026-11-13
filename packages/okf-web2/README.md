# okf-web2: OK, Fine Memory

> OK, fine, I’ll remember it for you.

The kid's-notebook web UI for OKF workspaces. It talks to the HTTP API of
[`okf-web`](../okf-web/) (Python), so run that as the backend. Brand, voice and
style live in [`brand/BRAND.md`](brand/BRAND.md).

## Run

```bash
# backend (from the repo root): serves the API on 127.0.0.1:8765
uv run okf-web

# frontend dev server with HMR, proxies /api to the backend
cd packages/okf-web2 && bun install && bun run dev      # http://localhost:5173

# or build once and let okf-web serve it
bun run build && uv run okf-web --static packages/okf-web2/dist
```

`OKF_API=http://127.0.0.1:8766 bun run dev` points the dev proxy at another
backend (e.g. a slow proxy for checking loading states).

There are two pages: the app (`index.html`) and the landing page
(`landing.html`, code in `src/landing/`). In dev open
`http://localhost:5173/landing.html`; once built, `okf-web --static` serves it
at `/landing.html`. Add `?intro` to the app URL to replay the opening animation.

## Stack

| Concern | Library |
|---|---|
| Build | Vite + React 19 + TypeScript |
| Routing | wouter, hash-based (`#/w/<ws>/<index>/c/<id>`) |
| Server state | TanStack Query (writes invalidate the whole index) |
| Forms / dialogs | react-hook-form + Radix Dialog (`useDialogs().form/prompt/confirm`) |
| Toasts | sonner (unstyled, drawn as sticky notes) |
| Doodle look | Tailwind v4, rough.js (`<Sketch>`, `<Btn>`), rough-notation (`<Mark>`) |
| Markdown | react-markdown + remark-gfm (tables, strikethrough, task lists) |
| Fonts | `@fontsource` Mali + Patrick Hand (Vietnamese included) |
| Tests | Vitest + Testing Library + MSW (`src/test/fakeBackend.ts`) |

## Layout

```
src/
  App.tsx              routes: #/ · #/w/:ws · #/w/:ws/:index/…
  pages/               WorkspacesPage, WorkspacePage, IndexLayout, DirPage, ConceptPage, ConceptForm, SearchPage
  components/          Tree (notebook explorer), Dialogs, ColorPicker, Logo, Title, Intro, ThemeToggle
  doodle/              Sketch, Btn, Mark, Skeleton, Loading, Okie, DoodleIcon, Doodles
  lib/                 api client, query hooks, scope + paths, workspace accent
  landing/             the landing page (second Vite entry)
  assets/doodles/      generated art (see ASSETS_PROMPT.md); picked up automatically
  assets/landing/      landing-page art and screenshots
brand/                 BRAND.md, brand-board.html, logo/
```

Generated art is optional: `Okie`, `DoodleIcon` and the logo use the PNGs from
`src/assets/doodles/` and `brand/logo/` when they exist (via
`import.meta.glob`) and fall back to inline sketches otherwise.

## Test

```bash
bun run test        # Vitest
bun run typecheck   # tsc
```
