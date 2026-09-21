# Customer Intelligence Platform — Frontend

Next.js 16 (App Router) + Tailwind v4 dashboard for the FastAPI backend in `../src/api`. Guide section 20 (dashboard design) implemented as: Dashboard, Customers (search/filter), Customer 360, Segments, Cohorts, Model Center, Retention Simulator, Monitoring.

## Running it

The backend must be running first (see `../docs/api_reference.md`):

```powershell
# from the project root
docker compose up -d postgres
python scripts/build_backend_data.py
uvicorn api.main:app --app-dir src --reload   # default port 8000
```

Then, from this directory:

```powershell
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL if the API isn't on :8000
npm install
npm run dev
```

## Architecture notes

- **Server Components by default.** Every page except the interactive bits (`components/RetentionSimulator.tsx`, the recharts wrappers) fetches directly from the FastAPI backend server-side with `cache: "no-store"` (see `lib/api.ts`) — no client-side loading spinners needed for read-only pages.
- **Charts use fixed dimensions, not `ResponsiveContainer`.** Recharts' `ResponsiveContainer` depends on a `ResizeObserver` firing after mount, which was unreliable in this dev environment (see `components/charts/*.tsx` comments) — a fixed size is a worthwhile trade for a dashboard whose layout doesn't need to flex to arbitrary widths.
- **`SegmentBarChart` and `ChurnByDimensionChart` are loaded with `next/dynamic(..., { ssr: false })`,** via thin wrapper files around `*Impl.tsx`. Found via a real hydration-mismatch error (not just a lint warning) surfaced by Next's dev overlay: Recharts measures Y-axis tick-label wrapping with a canvas that doesn't exist during SSR, so a label like "Steady Regulars" rendered unwrapped on the server and wrapped on the client — different text, so React discarded and re-rendered the whole subtree. Skipping SSR for just these two chart components (a placeholder matching their fixed dimensions avoids layout shift) was simpler and more robust than fighting Recharts' text measurement.
- **The Customer 360 risk number uses a CSS animation, not a JS `requestAnimationFrame` loop.** An earlier rAF-based count-up never fired due to a Next 16 dev-mode quirk (`allowedDevOrigins` blocking dev resources when the app was opened via `127.0.0.1` instead of `localhost` — fixed in `next.config.ts`, but the CSS approach in `components/AnimatedRiskNumber.tsx` is also just more robust regardless of that fix, since the correct number is in the server-rendered HTML from the start).
- **`next/font/google`** loads Space Grotesk (UI/headings) and IBM Plex Mono (all numeric values, via the `.tabular` utility class) — see `docs/architecture.md` for why these were chosen over the create-next-app defaults.
- **The Monitoring page's drift tables read `GET /monitoring/drift/{model}`** (Phase 11 — see `docs/monitoring.md`) and explicitly render the "no baseline yet" case rather than a fabricated zero: prediction drift only exists once `scripts/build_backend_data.py` has run at least twice, and the API says so via `has_prediction_baseline`.
