"""
Standardized error codes for scraping pipeline.

provides a centralized taxonomy of errors for consistent  reporting across  pipeline.
"""
from enum import Enum


class ErrorCode(Enum):
    # Non-fatal states
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"

    # Network/fetch errors (html_fetch stage)
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_REQUEST_FAILED = "NETWORK_REQUEST_FAILED"

    # Block/security errors (html_fetch stage)
    CLOUDFLARE_ATTENTION_REQUIRED = "CLOUDFLARE_ATTENTION_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    SCRAPER_BLOCKED = "SCRAPER_BLOCKED"

    # Text extraction errors (text_extraction stage)
    PDF_EXTRACTION_FAILED = "PDF_EXTRACTION_FAILED"
    EMBEDDED_DOC_FAILED = "EMBEDDED_DOC_FAILED"
    INSUFFICIENT_TEXT = "INSUFFICIENT_TEXT"
    SELENIUM_FAILED = "SELENIUM_FAILED"

    # Search discovery errors (search stage)
    SERP_API_KEY_MISSING = "SERP_API_KEY_MISSING"
    SERP_API_FAILED = "SERP_API_FAILED"
    SEARCH_NO_RESULTS = "SEARCH_NO_RESULTS"
    URL_FILTER_REJECTED_ALL = "URL_FILTER_REJECTED_ALL"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"

    # Pipeline-level errors
    PIPELINE_TIMEOUT = "PIPELINE_TIMEOUT"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


ERROR_DESCRIPTIONS = {
    ErrorCode.DUPLICATE_SKIPPED: "URL already exists in database, skipped",

    ErrorCode.NETWORK_TIMEOUT: "HTTP request timed out while fetching the page",
    ErrorCode.NETWORK_REQUEST_FAILED: "HTTP request failed (connection error, DNS failure, etc.)",

    ErrorCode.CLOUDFLARE_ATTENTION_REQUIRED: "Cloudflare protection detected (block page, challenge, or cookie requirement)",
    ErrorCode.ACCESS_DENIED: "Server returned access denied (non-Cloudflare)",
    ErrorCode.SCRAPER_BLOCKED: "Website security blocked the scraper",

    ErrorCode.PDF_EXTRACTION_FAILED: "Failed to download or extract text from PDF document",
    ErrorCode.EMBEDDED_DOC_FAILED: "Failed to extract content from embedded document (iframe/embed/object)",
    ErrorCode.INSUFFICIENT_TEXT: "Extracted text was below minimum length threshold",
    ErrorCode.SELENIUM_FAILED: "Selenium browser automation failed to extract content",

    ErrorCode.SERP_API_KEY_MISSING: "SERP API key not configured in .env",
    ErrorCode.SERP_API_FAILED: "SERP API call failed (exception or empty response)",
    ErrorCode.SEARCH_NO_RESULTS: "Search query returned zero organic results",
    ErrorCode.URL_FILTER_REJECTED_ALL: "URL filters rejected every result for a search entry",

    ErrorCode.DATABASE_ERROR: "Database operation failed (connection, query, or write error)",

    ErrorCode.PIPELINE_TIMEOUT: "URL processing exceeded maximum allowed time",
    ErrorCode.UNKNOWN_ERROR: "An unexpected error occurred",
}


def get_error_description(code):
    """Get the human-readable description for an error code."""
    return ERROR_DESCRIPTIONS.get(code, "Unknown error code")
