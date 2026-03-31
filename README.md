# vcode — Verbatim Coding Tool

Internal market research tool for coding open-end survey responses using AI.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Python + Streamlit |
| Desktop wrapper | Electron + Node.js (MIT, free) |
| AI providers | Google Gemini, OpenAI GPT |
| Auth & key management | Cloudflare Workers + KV |
| Email OTP | Brevo API |

---

## Features

- **OTP login** — Email verification via `@asia-plus.net` only, 7-day session
- **Excel upload** — Multi-sheet support, auto-detect duplicate ResID+Question
- **Codeframe editor** — Table view with Net 1 / Net 2 / Net 3 hierarchy columns
- **Paste from Excel** — Up to 5 columns: `code_id | label | net1 | net2 | net3`
- **AI coding** — Gemini (batch 100) or GPT (batch 50), multi-code per verbatim
- **Deduplication** — Groups identical verbatims before API call to save costs
- **Review tab** — Low-confidence records, manual re-code, add new codes inline
- **Export** — Session JSON + CSV with Net 1/2/3 columns
- **Admin tab** — Block/unblock emails, GPT API usage stats (7/14/30 days)

---

## Project Structure

```
vcode/
├── app.py                  ← Streamlit UI (main)
├── worker.js               ← Cloudflare Worker (auth + OTP + key server)
├── build.bat               ← Windows build script
├── requirements.txt
├── .env                    ← Local dev only (never commit)
├── electron/
│   ├── main.js             ← Electron main process
│   ├── splash.html         ← Loading screen
│   └── package.json
└── src/
    ├── auth.py             ← OTP, session, block, usage, admin
    ├── base_coder.py       ← Abstract coder + dedup logic
    ├── gemini_coder.py     ← Gemini implementation
    ├── gpt_coder.py        ← GPT implementation
    ├── i18n.py             ← English UI strings via t() helper
    ├── models.py           ← CodeEntry (with net1/2/3), Codeframe, VerbatimRecord
    ├── excel_reader.py     ← Excel parser
    ├── session_manager.py  ← Save/load JSON sessions
    └── vcode.py            ← VCode orchestrator
```

---

## Security Architecture

```
App (user machine)
    │
    ├── HMAC-SHA256 signed request (APP_TOKEN + timestamp, ±30s window)
    ↓
Cloudflare Worker  ←  OPENAI_API_KEY (never leaves Cloudflare)
    │
    ├── /send-otp        → Brevo API → email
    ├── /verify-otp      → KV: create session token
    ├── /check-session   → KV: validate token
    ├── /get-key         → returns OPENAI_API_KEY (valid session required)
    ├── /check-admin     → KV: admin:email → 1
    ├── /block-email     → KV: blocked:email → 1
    ├── /unblock-email   → KV: delete blocked:email
    ├── /list-blocked    → KV: list blocked: prefix
    └── /get-usage       → KV: usage:YYYY-MM-DD:email
```

**Key security points:**
- `OPENAI_API_KEY` stored only in Cloudflare Worker secrets — never in code or `.env`
- Every request signed with HMAC-SHA256 + timestamp (30-second replay protection)
- Session tokens stored locally at `%LOCALAPPDATA%\vcode\session.json`
- Admin status stored in KV: `admin:email@asia-plus.net → 1`

---

## Cloudflare Worker Setup

### Variables (Settings → Variables and Secrets)

| Variable | Type | Value |
|----------|------|-------|
| `OPENAI_API_KEY` | Secret | `sk-...` |
| `APP_TOKEN` | Secret | *(set in Cloudflare)* |
| `HMAC_SECRET` | Secret | *(set in Cloudflare)* |
| `BREVO_API_KEY` | Secret | *(set in Cloudflare)* |
| `BREVO_SENDER` | Plain | sender Gmail address |

### KV Binding

| Variable name | Namespace | ID |
|--------------|-----------|-----|
| `KV` | `vcode-auth` | *(your KV namespace ID)* |

### KV Key Schema

| Key pattern | Value | TTL |
|-------------|-------|-----|
| `otp:email` | 6-digit OTP | 10 min |
| `ratelimit:email` | `1` | 60 sec |
| `session:token` | `{email, expiresAt}` | 7 days |
| `blocked:email` | `1` | permanent |
| `admin:email` | `1` | permanent |
| `usage:YYYY-MM-DD:email` | call count | 90 days |

### Set Admin Email

In Cloudflare KV dashboard → `vcode-auth` → Add entry:
```
Key:   admin:your.email@asia-plus.net
Value: 1
```

---

## Local Development

### Prerequisites
- Python 3.10+
- Node.js 18+
- Cloudflare Worker deployed

### Setup

```powershell
# Create and activate venv
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
WORKER_URL=<your_worker_url>
APP_TOKEN=<your_app_token>

# Run Streamlit directly
streamlit run app.py

# Run via Electron (dev mode)
cd electron
npm install
npm start
```

---

## Build Desktop App

```powershell
# From project root
.\build.bat
```

**What build.bat does:**
1. Copies `src/`, `app.py`, `data/` into `python/` bundle
2. Creates `python/run.py` (Streamlit entry point)
3. Installs Electron dependencies (`npm install`)
4. Runs `electron-builder` → `dist\win-unpacked\vcode.exe`
5. Copies `venv/` next to `vcode.exe` (no Python needed on user machine)

**Distribute:** Zip `dist\win-unpacked\` → send to users → unzip → run `vcode.exe`

---

## AI Coding

### Batch sizes (auto-selected by provider)

| Provider | Batch size | Notes |
|----------|-----------|-------|
| Gemini 2.5 Flash | 100 | 1M context, handles large batches |
| Gemini 2.5 Pro | 100 | |
| GPT-4o | 50 | 128K context |
| GPT-4o-mini | 50 | |

### Deduplication
Before each API call, identical verbatims are grouped — only unique verbatims are sent to AI. Results are copied back to all duplicates. Saves API cost proportional to duplicate rate.

### Confidence & Review
- Records with `confidence < threshold` (default 0.9) → flagged for review
- In Review tab: approve, re-code, or add new codes to codeframe inline

---

## Codeframe Net Hierarchy

```
Net 1 (top level)
  └── Net 2 (sub-group)
        └── Net 3 (sub-sub-group)
              └── Code ID / Label
```

**Paste from Excel** — up to 5 columns (tab-separated):
```
101   Gấu trúc       Nhận dạng ký tự
201   Dễ thương       Hấp dẫn trực quan
```

**Validation on save:**
- Net 2 set → Net 1 must be set
- Net 3 set → Net 2 must be set

**CSV export columns:** `ResID, Question, Verbatim, CodeID, CodeLabel, Net 1, Net 2, Net 3, Confidence, NeedsReview`

---

## Session State Keys (reference)

```
auth_token, auth_email, auth_step, auth_otp_email
_cached_openai_key, _is_admin, _blocked_list
ai_provider, model, api_key, _gemini_api_key
_prev_provider, _prev_model
threshold, rules, codeframes, records, step
_coding_qs, _coding_recoding, _coding_batch
_loading_otp, _loading_verify, _loading_gen_all, _loading_coding
```

---

## Dependencies

```
streamlit>=1.55
pandas
openpyxl
google-generativeai
openai
requests
python-dotenv
```

---

## License

Internal use only — Asia Plus Research.