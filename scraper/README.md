

## Installation and Setup

### Requirements

- Python 3.8+
- MySQL database
- Firefox browser + geckodriver (for Selenium-based extraction)

### Dependencies

Install required packages:

```bash
pip install mysql-connector-python python-dotenv requests beautifulsoup4 selenium pymupdf pymupdf4llm
```

### Environment Variables

Create a `.env` file in the project root with  database credentials:

```
host_name=localhost
user_name=your_username
password=your_password
database_name=your_database
```

### Database Setup

Initialize the database tables:

```bash
python dbsetup.py
```

This creates three tables:
- `leg_html` - Raw HTML storage
- `leg_processed` - Extracted plain text
- `definitions` - Extracted term definitions

## Usage

### Basic Command

```bash
python run_pipeline.py --config path/to/config.json
```

### Configuration File Format

Create a JSON config file with URLs to scrape:

```json
{
  "URLs": [
    "https://www.congress.gov/bill/118th-congress/house-bill/1",
    "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240AB1",
    "https://capitol.texas.gov/tlodocs/89R/billtext/pdf/HB00149I.pdf"
  ],
  "settings": {
    "allow_duplicates": true,
    "min_bill_text_length": 500
  }
}
```

**Settings:**
- `allow_duplicates` - If `false`, skip URLs already in the database (default: `true`)
- `min_bill_text_length` - Minimum character threshold for valid extracted text (default: `500`)

### Output

Results are saved to `results/bills/{timestamp}/` containing:
- `status.json` - Pipeline execution summary and metrics
- `html_records.csv` - Exported raw HTML records
- `processed_text.csv` - Exported extracted text

## Architecture

```
flowchart TD
    Config[Config JSON] --> RunPipeline[run_pipeline.py]
    RunPipeline --> HtmlStorer[html_storer.py]
    HtmlStorer --> |Raw HTML| Database[(MySQL DB)]
    HtmlStorer --> TxtStorer[txt_storer.py]
    TxtStorer --> |Clean Text| Database
    RunPipeline --> ExportUtils[export_utils.py]
    ExportUtils --> CSV[CSV Files]
    RunPipeline --> StatusJSON[status.json]
```

### Module Descriptions

| Module | Purpose |
|--------|---------|
| `run_pipeline.py` | Entry point, orchestrates URL processing, generates status.json |
| `html_storer.py` | Fetches raw HTML, detects Cloudflare/block pages, stores to `leg_html` table |
| `txt_storer.py` | Extracts clean text via BeautifulSoup, Selenium, or PDF parsing; stores to `leg_processed` table |
| `error_codes.py` | Centralized error taxonomy for consistent classification |
| `export_utils.py` | CSV export and per-domain metrics computation |
| `dbsetup.py` | Database schema creation |
| `dbconnection.py` | MySQL connection management |

### Database Schema

**leg_html** (raw document storage)
- `id` - Primary key
- `source_url` - URL where document was fetched
- `raw_content` - Full HTML content
- `created_at` - Scrape timestamp

**leg_processed** (extracted text)
- `id` - Primary key
- `raw_doc_id` - Foreign key to `leg_html`
- `clean_text` - Extracted plain text
- `processed_at` - Processing timestamp

**definitions** (extracted terms)
- `id` - Primary key
- `processed_doc_id` - Foreign key to `leg_processed`
- `term` - Defined term
- `definition_text` - Definition content

## Error Code Reference

The pipeline uses standardized error codes for consistent classification and reporting.

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
| `DATABASE_ERROR` | any | Database operation failed (connection, query, or write error) |
| `PIPELINE_TIMEOUT` | timeout | URL processing exceeded maximum allowed time |
| `UNKNOWN_ERROR` | any | An unexpected error occurred |

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

### Timing Statistics

The `timing` object contains processing duration metrics:

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

### Additional Fields

| Field | Description |
|-------|-------------|
| `error_code_distribution` | Count of each error code encountered |
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
