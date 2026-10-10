# AppsFlyer Intelligence — Starter Project

A runnable starter for an AppsFlyer-style marketing analytics platform. It includes account registration/login, private user-owned CSV/Excel uploads, column normalization, KPI calculations, charts, campaign/source/event tables, a data-quality summary, and a sample dataset.

> This is a functional starter, not yet a fully production-hardened analytics product. The implementation intentionally does not guess payable-event status, deduplicate records across reports, or claim that a source column exists when it does not. See limitations below.

## 1. Requirements

- Python 3.11 or newer
- Internet connection for the Chart.js and Google Fonts CDN used by the frontend
- Windows, macOS, or Linux

## 2. Run locally (Windows)

1. Extract the ZIP file.
2. Open Command Prompt or PowerShell in the `appsflyer_intelligence` folder.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

5. Set a secret key for this terminal session:

   ```powershell
   $env:SECRET_KEY="replace-this-with-a-long-random-secret"
   ```

6. Start the server:

   ```powershell
   uvicorn app.main:app --reload
   ```

7. Open **http://127.0.0.1:8000** in your browser. Create an account, then upload an AppsFlyer CSV/XLSX report. API documentation is at **http://127.0.0.1:8000/docs**.

## 3. Try demo data

- In the app, use the `Download sample CSV` link or open `http://127.0.0.1:8000/api/demo.csv`.
- Upload `sample_data/demo_appsflyer.csv` from your computer.
- The sample numbers are synthetic and for demonstration only.

## 4. What works

- Registration and login with hashed passwords and signed bearer tokens.
- User-specific dataset listing and deletion.
- CSV, XLSX, and XLS file upload with a 20 MB default limit.
- Normalization of common AppsFlyer-style column names.
- KPI totals and ratios: CPI, CPC, CPA, CTR, install rate, and ROAS when the required columns are available.
- Daily trend chart, media-source chart, campaign/source/event tables, and basic exact duplicate/missing-cell counts.
- Responsive desktop/mobile layout.
- API docs at `/docs`.

## 5. Important metric and data notes

- Currency is currently displayed as USD. If your reports use another currency, change the UI formatting and add explicit currency metadata before relying on financial totals.
- If a column is absent, its metric is `Unavailable` rather than a fabricated zero.
- `conversions` means the report column mapped to conversions/purchases; confirm your AppsFlyer export semantics before using CPA.
- Exact duplicate counts are diagnostic only. The app does not automatically delete duplicates.
- When multiple datasets are selected, the starter concatenates them. It does not perform cross-report deduplication because safely identifying duplicate records requires report-specific keys and attribution semantics.
- Event names are shown if present. Payable status is not inferred.
- The current Excel upload reads the first worksheet. Worksheet selection and manual column mapping are future enhancements.
- The AI analyst, PDF export, saved filters, background jobs, detailed geospatial map, password reset, email verification, organization roles, and advanced optimization rules are not implemented in this starter yet.

## 6. Deploy online

You need to deploy the Python API and frontend together or deploy them as separate services, and use persistent storage.

For a simple first deployment:
1. Push this project to a private GitHub repository.
2. Choose a Python web host that supports FastAPI and persistent disks, or deploy to a VPS/container platform.
3. Configure the start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Set `SECRET_KEY` to a unique long random value.
5. Configure a managed PostgreSQL database and set `DATABASE_URL` to its connection string. Add the matching PostgreSQL driver (for example, `psycopg[binary]`) to `requirements.txt` if using PostgreSQL.
6. Use persistent private file storage for uploaded reports. The local `uploads/` directory is suitable for development only unless the host guarantees persistent disk.
7. Enable HTTPS, backups, request limits, logging, and monitoring before inviting real users.

Do not commit `.env`, API keys, database passwords, real marketing exports, or uploaded customer data to GitHub.

## 7. Suggested next stages

1. Add worksheet selection and a column-mapping/validation preview.
2. Add global date/source/campaign/geo/event filters and server-side pagination.
3. Implement business-configured payable events and transparent optimization rules.
4. Add secure AI chat grounded in backend-calculated metrics.
5. Add report exports, automated integration tests, and deployment automation.
6. Complete production security review (rate limiting, token revocation/refresh, CSRF strategy if switching to cookies, audit logging, malware scanning, tenant isolation tests).
