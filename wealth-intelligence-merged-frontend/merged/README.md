# Wealth Intelligence — Merged Frontend

This is the two uploaded frontends merged into a single, working Vite + React app.

## What happened in the merge

- **Base app:** `block3`'s Vite/React Router app was used as the foundation — it
  had the most complete set of screens (Radar, Client Intelligence, Recommendations,
  Scenario Lab, Meeting Copilot) and none of its existing logic was changed.
- **Ported in:** the Next.js app's standout feature — a **live AI Agent panel**
  (generate / regenerate an explanation, scenario or recommendation write-up,
  rendered as Markdown) — was ported over as a new **"Agent Lab"** page and added
  to the sidebar. It's implemented in its own files (`src/api/agentClient.ts`,
  `src/components/AgentPanel.tsx`, `src/components/AgentMarkdown.tsx`,
  `src/pages/AgentLab.tsx`) so it never touches any of the pre-existing
  components or API calls.
- **UI:** every existing page/component's JSX and logic is untouched — only
  `src/index.css` was rewritten for a more polished look (gradients, shadows,
  motion, refined color system), and it also fills in several classes
  (`ai-section`, `nav-item`, `sidebar-nav`, `rm-profile`, etc.) that components
  already referenced but had no styling for in the original CSS.

## Running it

```bash
npm install
npm run dev
```

By default the app expects a backend at `http://localhost:8000` (see `.env`,
`VITE_API_URL`). The existing pages call `/api/rm/...` endpoints; the new
Agent Lab page calls `/api/clients/:id/agent-runs/...` endpoints (as the
Next.js app did) — point `VITE_API_URL` at whichever backend implements the
routes you need, or update the base URL per-environment.

## Build

```bash
npm run build
```

This has been verified to type-check and build cleanly.
