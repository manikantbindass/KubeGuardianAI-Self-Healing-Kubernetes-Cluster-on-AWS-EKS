# Dashboard

Next.js App Router, strict TypeScript, Tailwind CSS, source-owned shadcn/ui conventions (Radix Slot, CVA, `cn`, semantic tokens, `components.json`), and TanStack Query. Reusable Button/Card components live under `src/components/ui`; the UI is dark-first and responsive, with keyboard focus, labels, a skip link, live status regions, and reduced-motion support. These basics do not establish full WCAG compliance.

Requests go through a route-allowlisted same-origin Next.js proxy; `API_BASE_URL` stays server-side. Health, readiness, version and jobs use typed clients with runtime response checks. Readiness 503 is a dependency state; unexpected HTTP failures include correlation IDs. Queries use bounded timeout/retry; jobs poll every two seconds and health every ten seconds.

Run from root using `npm run dev`, `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`. See the [development guide](../../docs/development-guide.md). Component tests use mocked API clients; container/native smoke separately checks actual connectivity. Future authentication and incident flows are not implemented.

The Button adapts the [shadcn/ui new-york source](https://ui.shadcn.com/r/styles/new-york/button.json) to this design's variants and focus treatment; its MIT notice is retained alongside the component. Source is maintained here rather than depending on a runtime shadcn package. The repository's original Apache 2.0 LICENSE is unchanged.
