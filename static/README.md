# static/

The web UI: a single-page app in plain JavaScript (no build step, no CDN). Served by FastAPI with a strict CSP (`'self'` only), and all text is rendered with `textContent`.

| File | Purpose |
|---|---|
| `index.html` | Page shell: header (customer picker, LLM badge, analyst name, theme toggle), sidebar, main area. |
| `theme.js` | Applies the saved or system light/dark theme before the page paints. |
| `app.js` | All UI logic: investigations (new, summary, KQL, follow-up, findings & notes with LLM ticket drafts, ticket, raw log, history), ticket template editor (placeholders, live preview, starters), customer config (details & files, schema selection with categories), schema catalog (pull from Microsoft, browse, custom schemas). |
| `style.css` | Dark and light themes and layout. |
