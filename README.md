# Wuolah Scraper

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![PyPI - Version](https://img.shields.io/pypi/v/wuolah-scraper)](https://pypi.org/project/wuolah-scraper/)

A Python toolkit for browsing, searching, and downloading documents from [Wuolah](https://wuolah.com) using your own authenticated session.

---

## Important — Read Before Using

**This tool requires a Wuolah Premium (ad-free) account.** The official download endpoint (`/v2/download`) uses a `noAdsToken` that is only available to premium users. If you have a free account, Wuolah inserts an advertisement flow before each download and the API will return an empty `fileUrl`.

This project **does not**:
- Bypass paywalls or advertisement gates
- Share, distribute, or store your credentials
- Redistribute copyrighted documents from Wuolah
- Perform unauthorized mass scraping

It simply automates what you can already do manually through your browser session. You are responsible for complying with Wuolah's terms of service.

---

## Features

- **Metadata indexing** — universities, centers, degree programs, subjects, documents
- **Rich search** — filter by university, community, subject, keyword, category, course, creator
- **Authenticated downloads** — official `/v2/download` flow with your session cookies/tokens
- **PDF cleaner** — remove tracking and ad links from downloaded PDFs
- **SQLite storage** — all metadata persisted locally for fast queries
- **Desktop GUI** — Tkinter interface for cookie setup, search, and download
- **CLI** — full argparse-based command-line interface

---

## Installation

```bash
git clone https://github.com/Fernando-Cuenca/wuolah-scraper.git
cd wuolah-scraper
pip install -e .

# Optional: PDF cleaning support
pip install -e ".[pdf]"

# Optional: everything
pip install -e ".[all]"
```

Requires Python 3.10 or later. The only hard dependency is `requests`. Tkinter is included with Python on most platforms. PDF cleaning requires `PyMuPDF`.

---

## Configuration

Copy the example config and edit it:

```bash
cp config.example.json config.json
```

Choose one authentication method:

### Option A — cookie header (recommended)

Paste your full session cookie string from the browser (DevTools → Application → Cookies):

```json
"auth": {
  "cookie_header": "token=eyJhbG...; refreshToken=eyJhbG..."
}
```

### Option B — cookie file

Export cookies from your browser in Netscape format (extensions like "cookies.txt" can do this):

```json
"auth": {
  "cookie_file": "/path/to/cookies.txt"
}
```

### Option C — direct tokens

```json
"auth": {
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG..."
}
```

The scraper auto-detects `token` and `refreshToken` keys from cookies and will refresh expired access tokens via `/login/refresh`.

---

## CLI Usage

```bash
# Test authentication
wuolah-scraper auth-check --config config.json

# List all universities
wuolah-scraper universities --config config.json

# Crawl an entire university
wuolah-scraper crawl --config config.json \
  --university-slug universidad-carlos-iii-de-madrid

# Crawl with filters (community + subject + category)
wuolah-scraper crawl --config config.json \
  --community-slug uc-3-m-escuela-politecnica-superior-campus-leganes/grado-ingenieria-tecnologias-industriales \
  --subject-slug physics-ii \
  --category examenes \
  --max-pages 3

# Download a specific document by ID
wuolah-scraper official-download --config config.json --document-id 12345

# Clean ad/tracking links from a PDF
wuolah-scraper clean-pdf --aggressive file.pdf

# Show database table counts
wuolah-scraper db-counts --config config.json
```

### Available filters

| Flag | Description |
|------|-------------|
| `--university-slug` | Filter by university |
| `--community-slug` | Filter by degree/community |
| `--subject-slug` | Filter by subject |
| `--study-type-slug` | Filter by study type |
| `--center-slug` | Filter by center/faculty |
| `--course` | Filter by course year (1, 2, 3, 4...) |
| `--category` | One of: apuntes, examenes, ejercicios, practicas, trabajos, test, pec, otros |
| `--creator-user-id` | Filter by uploader |
| `--keyword` | Full-text search in document name/slug/teacher/comments |
| `--sort` | Sort order (default: `-numDownloads`) |
| `--max-pages` | Limit API pagination (0 = unlimited) |
| `--all-universities` | Crawl every known university |

---

## Desktop GUI

```bash
wuolah-gui
```

A Tkinter interface for those who prefer not to use the terminal:

1. Paste your cookie at the top
2. Set university, community, subject, and filters
3. Click **Search**
4. Double-click a result to copy its URL
5. Select rows and click **Download** to save files locally

The GUI uses only Python's standard library — no extra dependencies needed beyond `requests`.

---

## Output Structure

```
outputs/
├── wuolah.sqlite          # Main database
├── last_run_summary.json  # Summary of the last crawl
└── raw_pages/             # Raw __NEXT_DATA__ dumps (if enabled)
```

SQLite tables: `universities`, `centers`, `communities`, `subjects`, `documents`, `community_artifacts`, `runs`.

---

## Project Structure

```
wuolah-scraper/
├── pyproject.toml
├── config.example.json
├── README.md
├── LICENSE
└── src/wuolah_scraper/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py            # CLI (argparse)
    ├── gui.py            # Desktop GUI (Tkinter)
    ├── client.py         # HTTP client with auth
    ├── auth.py           # Cookie/token management, JWT decoding
    ├── crawler.py        # Crawl orchestration
    ├── next_data.py      # Next.js __NEXT_DATA__ parser
    ├── storage.py        # SQLite persistence
    └── pdf_cleaner.py    # PDF ad-link redaction
```

## Architecture

The scraper uses a hybrid strategy:

1. **Structural discovery** — parses `__NEXT_DATA__` from Next.js server-rendered HTML (no browser required)
2. **Document enumeration** — paginates through the REST API at `https://api.wuolah.com/v2/documents`
3. **Document details** — fetches full metadata from `/v2/documents/{id}`
4. **Subject resolution** — resolves community-subject relationships via `/v2/communities/{id}/subjects/{slug}`
5. **Token refresh** — automatically refreshes access tokens through `/login/refresh`

This avoids depending on headless browsers or DOM scraping for the bulk of the work.

---

## Known Limitations

- The API's `filter[category]` parameter is sometimes ignored server-side; the scraper applies a client-side filter as a safety net
- Official downloads require a premium account; free accounts get empty `fileUrl` responses
- Email/password login is not implemented (cookie/token-based auth only)
- Non-document artifacts (social posts, giveaways, streams) are only partially indexed from community preview pages

---

## Security

- `config.json` and `*.cookies.txt` are in `.gitignore`
- Never commit your credentials or session tokens
- If you accidentally expose tokens, rotate them immediately in your Wuolah account settings
- The scraper stores credentials only in your local `config.json`

---

## License

MIT — see [LICENSE](LICENSE).

This project is not affiliated with, endorsed by, or connected to Wuolah. Use at your own risk and in accordance with their terms of service.
