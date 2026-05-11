

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
```

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
