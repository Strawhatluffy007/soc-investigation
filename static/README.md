# static/

The web UI: a single-page app in plain JavaScript (no build step, no CDN). Served by FastAPI with a strict CSP (`'self'` only), and all text is rendered with `textContent`.

| File | Purpose |
|---|---|
| `index.html` | Page shell: header (customer picker, LLM badge, analyst name), sidebar, main area. |
| `app.js` | All UI logic: investigations (new, summary, KQL, findings, ticket, history), customer config (details & files, schema selection with categories), schema catalog (pull from Microsoft, browse, custom schemas). |
| `style.css` | Dark theme and layout. |
