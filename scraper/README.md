

## Installation and Setup

### Requirements

- Python 3.8+
- MySQL database
- Firefox browser + geckodriver (for Selenium-based extraction)

### Dependencies

Install required packages:

```bash
pip install mysql-connector-python python-dotenv requests beautifulsoup4 selenium pymupdf pymupdf4llm serpapi lxml python-dateutil pdfservices-sdk
```

### Environment Variables

Create a `.env` file in the project root with database credentials and API keys:

```
host_name=localhost
user_name=your_username
password=your_password
database_name=your_database
serp_api_key=your_serpapi_key
# if using congress api:
congress_api_key=your_congress_api_key
app_port=port_on_your_machine_to_run_app
incremental_run = disallow_duplicate_links_T/F
```

If a port is not defined in .env, program will deafult to 5001

### Database Setup

Initialize the database tables:

```bash
python dbsetup.py
```

This creates four tables:
- `search_links` - URLs discovered via SERP API search queries
- `leg_html` - Raw HTML storage
- `leg_processed` - Extracted plain text
- `definitions` - Extracted term definitions

---

## Usage

### Standard Run (Search + Scrape)

```bash
python run_pipeline.py --config path/to/config.json
```

This runs the full pipeline: search discovery → HTML fetch → text extraction → CSV export.

### Scheduled / Resumable Run

```bash
python run_scheduled.py --config path/to/config.json
```

Use this for recurring runs. It:
- Re-runs all searches with deduplication (skips already-recorded URLs)
- Retries all previously failed HTML fetches
- Retries all previously failed text extractions
- Exports results and writes `status.json`

### Configuration File Format

Config files use a `searches` list instead of a raw `URLs` list. The pipeline resolves URLs automatically via SERP API.

```json
{
  "searches": [
    {
      "term": "Housing bills",
      "domain": "congress.gov",
      "inurl": "bill/",
      "max_results": 10
    },
    {
      "term": "algorithm",
      "domain": "leginfo.legislature.ca.gov",
      "inurl": "bill/",
      "max_results": 10
    }
  ],
  "settings": {
    "min_bill_text_length": 500
  }
}
```

**Search Entry Fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `term` | Yes | Keyword or phrase to search for |
| `domain` | Yes | Site to restrict search to (e.g. `congress.gov`) |
| `inurl` | No | Additional `inurl:` filter for the query |
| `max_results` | No | Max SERP results to retrieve (default: `10`) |

**Settings:**
- `min_bill_text_length` - Minimum character threshold for valid extracted text (default: `500`)

### Output

Results are saved to `results/bills/{timestamp}/` containing:
- `status.json` - Full pipeline execution summary and metrics
- `leg_html.csv` - Exported raw HTML records from this run
- `leg_processed.csv` - Exported extracted text records from this run
- `search_links.csv` - SERP-discovered links from this run

---

## Architecture

```
flowchart TD
    Config[Config JSON] --> RunPipeline[run_pipeline.py]
    RunPipeline --> SearchLayer[search_layer.py]
    SearchLayer --> |SERP API queries| SERP[(SerpAPI)]
    SERP --> |Discovered URLs| SearchLinks[(search_links table)]
    SearchLinks --> HtmlStorer[html_storer.py]
    HtmlStorer --> |Raw HTML| LegHtml[(leg_html table)]
    LegHtml --> TxtStorer[txt_storer.py]
    TxtStorer --> |Clean Text| LegProcessed[(leg_processed table)]
    RunPipeline --> ExportUtils[export_utils.py]
    ExportUtils --> CSV[CSV Files]
    RunPipeline --> StatusJSON[status.json]

    RunScheduled[run_scheduled.py] --> ResumeUtils[resume_utils.py]
    ResumeUtils --> |Retry failures| RunPipeline
    RunScheduled --> SearchLayer
```

### Module Descriptions

| Module | Purpose |
|--------|---------|
| `run_pipeline.py` | Primary entry point — runs search discovery, orchestrates per-URL processing, exports CSVs, generates `status.json` |
| `run_scheduled.py` | Scheduled/resumable entry point — incremental search dedup, retries failed HTML and text jobs, then calls `run_pipeline` internals |
| `search_layer.py` | Resolves search entries to URLs via SERP API; records each discovered link in `search_links` |
| `resume_utils.py` | Queries DB for failed/incomplete work; cleans up failed records before retry |
| `html_storer.py` | Fetches raw HTML, detects Cloudflare/block pages, stores to `leg_html` |
| `txt_storer.py` | Extracts clean text via BeautifulSoup, Selenium, or PDF parsing; stores to `leg_processed` |
| `def_storer.py` | Extracts term definitions from clean text or XML via regex/XML parsing; stores to `definitions` |
| `export_utils.py` | CSV export filtered by run's HTML/search_link IDs; per-domain metrics computation |
| `error_codes.py` | Centralized error taxonomy for consistent classification across all stages |
| `constants.py` | Shared configuration: timeout values, text length thresholds, Congress bill version priority |
| `detail_extract.py` | Parses `congress.gov` bill URLs to extract congress number, bill type, and bill number |
| `alg.py` | XML-based definitions classifier for Congress.gov bill XML format |
| `dbsetup.py` | Database schema creation and migration |
| `dbconnection.py` | MySQL connection management |
| `main.py` | Local testing utility — not used for pipeline execution |

---

## Database Schema

**search_links** (SERP discovery tracking)
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | Auto-increment primary key |
| `search_method` | VARCHAR | How the link was found (e.g. `"SERPAPI"`) |
| `keyword_search` | VARCHAR | Full query string sent to the search engine |
| `other_filters` | VARCHAR | Serialized URL filters applied after search |
| `link` | VARCHAR | The discovered URL |
| `processing_time` | DECIMAL | Seconds taken by the SERP API call |
| `num_api_tries` | INT | Number of SERP API attempts made |
| `num_api_failures` | INT | Number of failed SERP API attempts |
| `failure_type` | VARCHAR | Error code if the search failed |
| `is_successful` | TINYINT | `1` if link was accepted, `0` otherwise |
| `discovered_at` | TIMESTAMP | Timestamp of discovery |

**leg_html** (raw document storage)
| Column | Type | Description |
|--------|------|-------------|
| `search_id` | INT PK | Auto-increment primary key |
| `source_url` | VARCHAR | URL where the document was fetched |
| `HTML` | LONGTEXT | Full raw HTML content |
| `domain` | VARCHAR | Extracted domain of the source URL |
| `num_tries` | INT | Number of fetch attempts made |
| `num_failures` | INT | Number of failed fetch attempts |
| `failure_type` | VARCHAR | Error code if fetch failed |
| `warnings` | VARCHAR | Non-fatal warning messages |
| `is_successful` | TINYINT | `1` if fetch succeeded, `0` otherwise |
| `processing_time` | DECIMAL | Seconds taken to fetch |
| `created_at` | TIMESTAMP | Scrape timestamp |

**leg_processed** (extracted text)
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | Auto-increment primary key |
| `raw_doc_id` | INT FK | Foreign key to `leg_html.search_id` |
| `source_url` | VARCHAR | Source URL (denormalized for convenience) |
| `clean_text` | LONGTEXT | Extracted plain text |
| `processed_at` | TIMESTAMP | Processing timestamp |
| `num_tries_text_processing` | INT | Number of extraction attempts |
| `num_failures_text_processing` | INT | Number of failed extraction attempts |
| `failure_type` | VARCHAR | Error code if extraction failed |
| `text_processing_method` | VARCHAR | Method used (e.g. `beautifulsoup`, `selenium`, `pdf`) |
| `domain` | VARCHAR | Source domain |
| `warnings` | VARCHAR | Non-fatal warning messages |
| `is_successful` | TINYINT | `1` if extraction succeeded, `0` otherwise |
| `processing_time` | DECIMAL | Seconds taken to extract |
| `search_link_id` | INT FK | Foreign key to `search_links.id` |
| `search_term` | VARCHAR | Search term that led to this document |

**definitions** (extracted terms)
| Column | Type | Description |
|--------|------|-------------|
| `id` | INT PK | Auto-increment primary key |
| `processed_doc_id` | INT FK | Foreign key to `leg_processed.id` |
| `term` | VARCHAR | Defined term |
| `definition_text` | TEXT | Definition content |

---

## Error Code Reference

| Code | Stage | Description |
|------|-------|-------------|
| `DUPLICATE_SKIPPED` | html_fetch | URL already exists in database, skipped |
| `NETWORK_TIMEOUT` | html_fetch | HTTP request timed out while fetching the page |
| `NETWORK_REQUEST_FAILED` | html_fetch | HTTP request failed (connection error, DNS failure, etc.) |
| `CLOUDFLARE_ATTENTION_REQUIRED` | html_fetch | Cloudflare protection detected (block page, challenge, or cookie requirement) |
| `ACCESS_DENIED` | html_fetch | Server returned access denied (non-Cloudflare) |
| `SCRAPER_BLOCKED` | html_fetch | Website security blocked the scraper |
| `PDF_EXTRACTION_FAILED` | text_extraction | Failed to download or extract text from PDF document |
| `EMBEDDED_DOC_FAILED` | text_extraction | Failed to extract content from embedded document (iframe/embed/object) |
| `INSUFFICIENT_TEXT` | text_extraction | Extracted text was below minimum length threshold |
| `SELENIUM_FAILED` | text_extraction | Selenium browser automation failed to extract content |
| `SERP_API_KEY_MISSING` | search | `serp_api_key` not set in `.env` |
| `SERP_API_FAILED` | search | SERP API call failed after all retries |
| `SEARCH_NO_RESULTS` | search | Search query returned zero organic results |
| `URL_FILTER_REJECTED_ALL` | search | URL filters rejected every result for a search entry |
| `DATABASE_ERROR` | any | Database operation failed (connection, query, or write error) |
| `PIPELINE_TIMEOUT` | timeout | URL processing exceeded maximum allowed time |
| `UNKNOWN_ERROR` | any | An unexpected error occurred |

---

## Timeout Reference

Defined in `constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `PER_URL_TIMEOUT` | 20s | Max time per non-PDF URL in the pipeline |
| `PDF_URL_TIMEOUT` | 120s | Max time per PDF URL in the pipeline |
| `DEFAULT_REQUEST` | 15s | Default HTTP request timeout |
| `PDF_DOWNLOAD` | 60s | PDF download timeout |
| `PDF_HTML_FETCH` | 100s | HTML fetch timeout when PDF is embedded |
| `EMBEDDED_DOC` | 30s | Embedded document extraction timeout |
| `PAGE_LOAD` | 10s | Selenium page load timeout |
| `ELEMENT_WAIT` | 10s | Selenium element wait timeout |
| `WEBDRIVER_WAIT` | 2s | Selenium WebDriver initialization wait |

---

## Output Metrics (status.json)

The `status.json` file provides detailed execution metrics for research and debugging.

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO timestamp of pipeline completion |
| `success` | boolean | `true` if all URLs succeeded and export completed |
| `total_URLs` | integer | Total number of URLs processed |
| `successful_URLs` | integer | Number of URLs successfully scraped |
| `failed_URLs` | integer | Number of URLs that failed |

### Search Discovery Section

The `search_discovery` object summarizes the SERP API stage:

| Field | Description |
|-------|-------------|
| `total_searches` | Number of search queries run |
| `successful_searches` | Queries that returned at least one result |
| `failed_searches` | Queries that failed or returned no results |
| `total_urls_discovered` | Unique URLs found across all queries |
| `timing` | Timing breakdown for the search stage |
| `per_search_results` | Per-query metrics list |
| `error_code_distribution` | Count of each search error code encountered |
| `errors` / `warnings` | Errors and warnings from the search stage |

### Timing Statistics

The `processing_timing` object contains URL processing duration metrics:

| Field | Description |
|-------|-------------|
| `total_duration_seconds` | Total pipeline execution time |
| `avg_per_url_seconds` | Average processing time per URL |
| `min_url_seconds` | Fastest URL processing time |
| `max_url_seconds` | Slowest URL processing time |

### Extraction Method Distribution

The `extraction_method_distribution` object counts how text was extracted:

| Method | Description |
|--------|-------------|
| `beautifulsoup` | Standard HTML parsing |
| `selenium` | Browser automation for dynamic content |
| `congress_selenium` | Specialized handling for congress.gov |
| `pdf` | Direct PDF URL extraction |
| `embedded_pdf` | PDF embedded in HTML page |
| `embedded_doc` | Other embedded documents (iframe/embed/object) |

### Stage Breakdown

The `stage_breakdown` object shows success/failure at each pipeline stage:

```json
{
  "html_fetch": {
    "attempted": 100,
    "succeeded": 95,
    "failed": 5
  },
  "text_extraction": {
    "attempted": 95,
    "succeeded": 90,
    "failed": 5
  },
  "timeout": 0,
  "complete": 90
}
```

### Scheduled Run Fields

When using `run_scheduled.py`, the `scheduled` object is added:

| Field | Description |
|-------|-------------|
| `new_urls_found` | New URLs discovered in this scheduled run |
| `urls_fixed` | Previously failed URLs that succeeded on retry |

### Additional Fields

| Field | Description |
|-------|-------------|
| `error_code_distribution` | Count of each error code encountered during scraping |
| `domain_metrics` | Per-domain success rates, failure counts, and error messages |
| `csv_files` | List of exported CSV files with row counts |
| `errors` | Detailed error messages for failed URLs |
| `warnings` | Non-fatal warnings (e.g., fallback extraction methods used) |

### Example domain_metrics

```json
{
  "www.congress.gov": {
    "total": 14,
    "success": 12,
    "failed": 2,
    "blocked": 0,
    "success_rate": 85.7,
    "errors": ["Timed out after 20s", "Timed out after 20s"]
  }
}
```

## Database Metric Files

Through the usage of dbmetrics.py, you can scan a database for information about what are the most prevelant terms and links by different terms and links, as well as the largest term-link groups in your database.
Database scanning is done through the information in the .env file. 
The 'dbmetrics' program is also run after each successful run of the pipeline algorithm

### Database Metrics Files

All metrics are stored in subfolder "results\metrics", which is a subfolder for the results folder. This folder is created upon running running dbmetrics if it does not already exist. 
These files follow the nomenclature: 

    type-phrase-databaseName-metrics-timestamp

These different words have the following meanings:
- 'type' - term, general, or link, represents the type of following phrase and subsequent search
- 'phrase' - the string by which the database is filtered to only show terms/links correpsonding to that phrase
                * This is an empty string for general metrics
- 'databaseName' - the name of the database the dbmetrics is run on
- 'timestamp' - timestamp in form: YEARMONTHDAY_HOURMINUTESECOND
                * Note that this means that metrics analysis with the same type, parameter and database must occur at least 1 second apart

Most of the files, are organized as such:

| Phrase(s) | Frequency |
|-------|-------------|
| `term` or `link` | Count of each in the database for the search term |

For general metrics files, however, each link and term group is a unique combination, thus this file is structed as so:

| Term | Link | Frequency |
|-------|-------------|
| `term` | `link` | Count of each in the database |



### Running Database Metrics

dbmetrics can be run without a config file or with one, wherin the first case a general metrics analysis is done on the database. This is done as so:

```bash
python dbmetrics.py
```

To run dbmetrics with config file (which is necessary to search for term/link frequency by phrase), you must append the existing config.json file as so:

Example:
```json
{
  "other settings": {
      ...
  },
  "metrics" : {
    "type": "link",
    "phrase": "congress.gov"
  }
}
```
Following this formatting, the dbmetrics is simply run through th following command:

```bash
python dbmetrics.py --config path/to/config.json
```

---

## Bill Viewer Web Application

A web interface for browsing scraped bills and configuring new scrape jobs.

NOTE: Make sure to define an avaiable port in your env file. The app will run on that port

NOTE: Make sure to define mock status is frontend .env file (more below in mock section)

NOTE 2: 

### Quick Start

**Terminal 1 - Backend (Flask API):**
```bash
cd /path/to/scraper
source .venv/bin/activate
pip install -r web/requirements.txt
.venv/bin/python -m web.api.app
```

**Terminal 2 - Frontend (React):**
```bash
cd /path/to/scraper/web/frontend
npm install
npm run dev
```

**Browser:**
Open page shown in second terminal 

### Web Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's Browser                          │
│                     http://127.0.0.1:5173                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│                         Port 5173                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Browse    │  │  New Scrape │  │ Job Status  │              │
│  │    Bills    │  │    Form     │  │   Tracker   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                                │
                          /api/* proxy
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (Flask API)                           │
│                         Port 5000                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │/api/bills   │  │/api/        │  │/api/scrapes │              │
│  │             │  │jurisdictions│  │             │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐    ┌──────────────────────────────┐
│         MySQL DB          │    │     run_scheduled.py         │
│  (leg_html, leg_processed)│    │    (spawned as subprocess)   │
└───────────────────────────┘    └──────────────────────────────┘
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/jurisdictions` | GET | List unique domains from `leg_html` |
| `/api/bills` | GET | List bills with optional `?jurisdiction=` filter |
| `/api/bills/<id>` | GET | Get single bill with full text |
| `/api/scrapes` | GET | List all scrape jobs |
| `/api/scrapes` | POST | Create and start a new scrape job |
| `/api/scrapes/<job_id>` | GET | Get job status and results |

### Features

**Browse Bills**
- Filter bills by jurisdiction (domain)
- Paginated list view with excerpts
- Full text detail view with metadata

**New Scrape**
- Enter search terms (one per line)
- Select jurisdictions from predefined list
- Set optional date range (Start Date / End Date)
- Jobs run asynchronously in background

**Job Status**
- Real-time status updates (polls every 3 seconds)
- View results when complete
- See error logs on failure

### Mock Mode (Frontend Development)

Run the frontend without a backend using Mock Service Worker (MSW):

```bash
cd web/frontend
echo "VITE_USE_MOCKS=true" > .env
npm run dev
```

This intercepts all `/api/*` requests and returns dummy data, useful for UI development or demos. Mock data lives in `web/frontend/src/mocks/`.

To return to normal mode, set `VITE_USE_MOCKS=false` or remove the line.

### Web Application File Structure

```
web/
├── api/
│   ├── __init__.py
│   ├── app.py           # Flask app entry point
│   ├── db.py            # Database connection helper
│   ├── bills.py         # /api/bills endpoints
│   ├── jurisdictions.py # /api/jurisdictions endpoint
│   ├── scrapes.py       # /api/scrapes endpoints
│   └── job_runner.py    # Background job management
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main app with routing
│   │   ├── components/
│   │   │   ├── BillsBrowser.tsx
│   │   │   ├── BillsList.tsx
│   │   │   ├── BillDetail.tsx
│   │   │   ├── JurisdictionSelector.tsx
│   │   │   ├── ScrapeForm.tsx
│   │   │   └── JobStatus.tsx
│   │   ├── api/client.ts        # API fetch functions
│   │   └── types.ts             # TypeScript types
│   ├── vite.config.ts           # Dev server + proxy config
│   └── package.json
├── requirements.txt     # Python dependencies (flask, flask-cors, psutil)
└── README.md
```

### Web Dependencies

**Backend (Python):**
- `flask` - Web framework
- `flask-cors` - Cross-origin resource sharing
- `psutil` - Process monitoring for job status

**Frontend (Node.js):**
- React 18+ with TypeScript
- Vite (build tool)
- TailwindCSS (styling)
- React Router (navigation)
- TanStack Query (data fetching)
