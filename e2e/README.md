# E2E / API tests (Playwright) — planned

Scaffold only, not yet implemented. When added:

```powershell
npm init playwright@latest          # in this directory
npm i -D allure-playwright          # Allure reporter
```

Point the reporter at the shared results dir so backend + frontend reports
combine under one `allure serve`:

```js
// playwright.config.ts
reporter: [
  ["line"],
  ["allure-playwright", { resultsDir: "../allure-results" }],
],
```

Run against the full dev stack (db + osrm + backend on :8000 + frontend on
:5173). Keep to 2–3 smoke flows: search → variant → steps table; OSRM-down →
graceful error. API tests via Playwright's `request` fixture overlap with the
backend pytest integration suite — prefer pytest unless you specifically want
browser-context coverage (CORS, cookies, auth headers).
