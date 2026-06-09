#!/usr/bin/env python3
"""
Command-line interface for the legislative scraping pipeline.

Usage:
    python run_pipeline.py --config path_to_config.json, run pipeline
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from sqlite_setup import sqlite_setup
from dbconnection import create_connection
from html_storer import store_html
from export_utils import export_all_tables, compute_domain_metrics
from error_codes import ErrorCode
from constants import Timeouts
from txt_storer import is_pdf_url, retrieve_txt
from driver_utils import ensure_firefox_driver

# Load environment variables
load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")
dbtype = os.getenv("db_type")
incremental_run = os.getenv("incremental_run")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results" / "bills"

def add_timestamp_results_directory():
    """
    Ensure the results directory exists with timestamp, adds timestamp if needed to avoid overwrite
    
    Returns:
        str: Path to the timestamped results directory (results/bills/{timestamp})
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = RESULTS_DIR / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)
    return str(results_dir)


def parse_args():
     # parse command line args
    parser = argparse.ArgumentParser(
        description="Runs the pipeline with search terms (SERP API)"
    )
    # provides path to json config file
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the JSON configuration file"
    )
    return parser.parse_args()


def validate_config(config_path):
    """
    Load and validate the JSON configuration file.

    Args:
        config_path: Path to the JSON config file

    Returns:
        dict: Validated configuration dictionary with defaults applied

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

    if "settings" not in config:
        config["settings"] = {}

    if "URLs" in config:
        raise ValueError("Search-only mode: config must not include 'URLs'. Provide 'searches' instead.")

    if "searches" not in config:
        raise ValueError("Config must contain 'searches' field")

    if not isinstance(config["searches"], list) or len(config["searches"]) == 0:
        raise ValueError("'searches' must be a non-empty list")

    for i, entry in enumerate(config["searches"]):
        if not isinstance(entry, dict):
            raise ValueError(f"Search entry {i} must be an object")
        if "term" not in entry or "domain" not in entry:
            raise ValueError(f"Search entry {i} must have 'term' and 'domain' keys")

    return config


def load_config(config_path):
    """
    Validate config, run search discovery, and return config with URLs populated.

    Args:
        config_path: Path to the JSON config file

    Returns:
        dict: Configuration dictionary with URLs resolved via SERP API
    """
    config = validate_config(config_path)

    from search_layer import discover_urls
    connection = create_connection(host, user, pw, database, dbtype)
    if connection is None:
        raise RuntimeError("Failed to connect to database for search discovery")
    try:
        print(f"\n{'#'*70}")
        print(f"  SEARCH DISCOVERY STAGE")
        print(f"{'#'*70}\n")
        settings = config.get("settings", {})
        discovery = discover_urls(config["searches"], connection, settings=settings)
    finally:
        if connection and connection.is_connected():
            connection.close()

    config["URLs"] = discovery["urls"]
    config["_search_discovery"] = discovery

    print(f"{'='*70}")
    print(f"  SEARCH DISCOVERY SUMMARY")
    print(f"{'='*70}")
    print(f"  Total searches:      {discovery['total_searches']}")
    print(f"  Successful searches: {discovery['successful_searches']}")
    print(f"  Failed searches:     {discovery['failed_searches']}")
    print(f"  URLs discovered:     {discovery['total_urls_discovered']}")
    print(f"  Total time:          {discovery['timing']['total_duration_seconds']}s")
    if discovery["errors"]:
        print(f"  Errors:")
        for err in discovery["errors"]:
            print(f"    - {err}")
    if discovery["warnings"]:
        print(f"  Warnings:")
        for warn in discovery["warnings"]:
            print(f"    - {warn}")
    print(f"{'='*70}\n")

    if not config["URLs"]:
        raise ValueError("Search returned no URLs after filtering")

    return config


def process_url(url, driver=None, search_link_id=None):
    """
    Process a single URL through the pipeline (HTML fetch + text extraction).
    
    Args:
        url: URL to process
        driver: Optional existing WebDriver instance to reuse
        search_link_id: Optional search_links.id that discovered this URL
    
    Returns:
        dict: Result dictionary with success status, details, and warnings
    """
    try:
        html_result = store_html(url, driver=driver, search_link_id=search_link_id)
        
        if html_result.get("error"):
            return {
                "url": url,
                "success": False,
                "html_id": html_result.get("html_id"),
                "warning": html_result.get("warning"),
                "error": html_result["error"],
                "error_code": html_result.get("error_code", ErrorCode.UNKNOWN_ERROR.value),
                "stage": html_result.get("stage", "html_fetch"),
                "extraction_method": None
            }
        
        html_id = html_result.get("html_id")
        if html_id is None:
            return {
                "url": url,
                "success": False,
                "html_id": None,
                "warning": html_result.get("warning"),
                "error": html_result.get("error") or "Failed to store HTML",
                "error_code": html_result.get("error_code", ErrorCode.UNKNOWN_ERROR.value),
                "stage": html_result.get("stage", "html_fetch"),
                "extraction_method": None
            }
        
        txt_result = retrieve_txt(
            html_id=html_id,
            driver=driver,
            search_link_id=search_link_id
        )
        
        warning = html_result.get("warning")
        error = None
        error_code = None
        extraction_method = None
        stage = "complete"
        success = True
        
        if txt_result:
            if txt_result.get("warning"):
                warning = txt_result["warning"]
            extraction_method = txt_result.get("extraction_method")
            if txt_result.get("error"):
                error = txt_result["error"]
                error_code = txt_result.get("error_code")
                stage = "text_extraction"
                success = False
            elif not txt_result.get("success"):
                warning = txt_result.get("warning") or "Text extraction failed"
                error_code = txt_result.get("error_code")
                stage = "text_extraction"
                success = False
        
        return {
            "url": url,
            "success": success,
            "html_id": html_id,
            "warning": warning,
            "error": error,
            "error_code": error_code,
            "stage": stage,
            "extraction_method": extraction_method
        }
    
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "html_id": None,
            "warning": None,
            "error": str(e),
            "error_code": ErrorCode.UNKNOWN_ERROR.value,
            "stage": "html_fetch",
            "extraction_method": None
        }


def run_pipeline(config, results_dir):
    """
    Run the pipeline for all URLs in config
    
    Args:
        config: Configuration dictionary
        results_dir: Directory to save results
    
    Returns:
        dict: Pipeline execution summary
    """
    URLs = config["URLs"]
    url_to_search_link_id = config.get("_search_discovery", {}).get("url_to_search_link_id", {})
    
    results = []
    successful_URLs = 0
    failed_URLs = 0
    errors = []
    warnings = []
    url_timings = []  # Track per-URL processing times

    #setting up file for sqlite config
    if not (dbtype == "MySQL"):
        sqlite_setup()
    
    print(f"# running pipeline, writing to results directory: {results_dir}")
    print(f"{'#'*70}\n")
    
    # Track pipeline start time
    pipeline_start_time = time.time()

    # Create a single shared browser instance for all URLs
    driver = None
    driver_warning = None
    try:
        try:
            driver = ensure_firefox_driver(None)
        except Exception as e:
           
            driver = None
            driver_warning = f"Shared Firefox driver unavailable: {e}"
            print(f"WARNING: {driver_warning}")

        for idx, url in enumerate(URLs, 1):
            if driver is not None:
                try:
                    driver = ensure_firefox_driver(driver)
                except Exception as e:
                    driver = None
                    if not driver_warning:
                        driver_warning = f"Shared Firefox driver dropped during run: {e}"
                    print(f"WARNING: Shared Firefox driver unavailable for {url}: {e}")

            # Track per-URL timing
            url_start_time = time.time()
            url_timeout = Timeouts.PDF_URL_TIMEOUT if is_pdf_url(url) else Timeouts.PER_URL_TIMEOUT

            # Run process_url in a daemon thread with a timeout so one
            # stuck URL can never block the rest of the pipeline.
            result_holder = [None]

            def _run(u=url, d=driver, slid=url_to_search_link_id.get(url)):
                result_holder[0] = process_url(u, driver=d, search_link_id=slid)

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout=url_timeout)

            if thread.is_alive():
                result = {
                    "url": url,
                    "success": False,
                    "html_id": None,
                    "warning": None,
                    "error": f"Timed out after {url_timeout}s",
                    "error_code": ErrorCode.PIPELINE_TIMEOUT.value,
                    "stage": "timeout",
                    "extraction_method": None
                }
               
                # kill stuck browser
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = ensure_firefox_driver(None)
            else:
                result = result_holder[0]
                if result is None:
                    result = {
                        "url": url,
                        "success": False,
                        "html_id": None,
                        "warning": None,
                        "error": "Unknown pipeline error (no result returned)",
                        "error_code": ErrorCode.UNKNOWN_ERROR.value,
                        "stage": "pipeline",
                        "extraction_method": None
                    }

            # Calculate and store URL processing time
            url_duration = time.time() - url_start_time
            result["duration_seconds"] = round(url_duration, 2)
            url_timings.append(url_duration)

            results.append(result)
            
            if result["success"]:
                successful_URLs += 1
                # Capture warnings from successful runs
                if result.get("warning"):
                    warnings.append(f"{url}: {result['warning']}")
            else:
                failed_URLs += 1
                error_msg = f"Failed to process {url}: {result['error']}"
                errors.append(error_msg)
        if driver_warning:
            warnings.append(driver_warning)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
    
    # Calculate total pipeline duration
    pipeline_duration = time.time() - pipeline_start_time
    
    # collect html_ids from successful runs for csv export filtering
    html_ids = [r["html_id"] for r in results if r["html_id"] is not None]

    # compute per-domain success metrics
    domain_metrics = compute_domain_metrics(results)
    
    # Compute timing statistics
    timing_stats = {
        "total_duration_seconds": round(pipeline_duration, 2),
        "avg_per_url_seconds": round(sum(url_timings) / len(url_timings), 2) if url_timings else 0,
        "min_url_seconds": round(min(url_timings), 2) if url_timings else 0,
        "max_url_seconds": round(max(url_timings), 2) if url_timings else 0
    }
    
    # summary of pipleine execution
    summary = {
        "total_URLs": len(URLs),
        "successful_URLs": successful_URLs,
        "failed_URLs": failed_URLs,
        "results": results,
        "errors": errors,
        "warnings": warnings,
        "html_ids": html_ids,
        "domain_metrics": domain_metrics,
        "timing": timing_stats,
        "search_discovery": config.get("_search_discovery"),
    }
    # Per-stage counts
    total = len(URLs)
    success_pct = round(successful_URLs / total * 100, 1) if total > 0 else 0.0

    html_fetch_fails = [r for r in results if not r["success"] and r.get("stage") == "html_fetch"]
    text_extract_fails = [r for r in results if not r["success"] and r.get("stage") == "text_extraction"]
    timeout_fails = [r for r in results if not r["success"] and r.get("stage") == "timeout"]

    print(f"\n{'='*70}")
    print(f"  PIPELINE EXECUTION SUMMARY")
    print(f"{'='*70}")
    print(f"  Total processed:  {total}")
    print(f"  Succeeded:        {successful_URLs}  ({success_pct}%)")
    print(f"  Failed:           {failed_URLs}")
    print(f"{'='*70}")
    print(f"  Stage 1 - HTML Fetch:       {total - len(html_fetch_fails) - len(timeout_fails)}/{total} succeeded")
    if html_fetch_fails:
        print(f"    {len(html_fetch_fails)} failed:")
        for r in html_fetch_fails:
            print(f"      - {r['url']}: {r['error']}")
    print(f"  Stage 2 - Text Extraction:  {total - len(html_fetch_fails) - len(timeout_fails) - len(text_extract_fails)}/{total - len(html_fetch_fails) - len(timeout_fails)} succeeded")
    if text_extract_fails:
        print(f"    {len(text_extract_fails)} failed:")
        for r in text_extract_fails:
            print(f"      - {r['url']}: {r['error']}")
    if timeout_fails:
        print(f"  Timed out:        {len(timeout_fails)}")
        for r in timeout_fails:
            print(f"      - {r['url']}: {r['error']}")
    print(f"{'='*70}\n")

    return summary


def export_results_to_csv(results_dir, html_ids=None, search_link_ids=None):
    """
    Exports db tables to csv, filtered by html_ids from this run
    
    Args:
        results_dir: Directory to save CSV files
        html_ids: List of html IDs to export (only bills from this run - can change if want all)
        search_link_ids: Optional list of search_links.id values to export (only SERP accepted links from this run)
    
    Returns:
        dict: Export summary with row counts
    """
    
    try:
        connection = create_connection(host, user, pw, database, dbtype)
        # checks conneciton to db
        if connection is None:
            print("Failed to connect to database for export")
            return None
        
        exports = export_all_tables(
            connection,
            results_dir,
            html_ids=html_ids,
            search_link_ids=search_link_ids,
        )
        
        if connection.is_connected():
            connection.close()
        return exports
    
    except Exception as e:
        print(f"Error during CSV export: {e}")
        return None


def write_status_json(results_dir, pipeline_summary, export_summary, export_error=None):
    """
    Write status.json with execution results.
    
    Args:
        results_dir: Directory to save status.json
        pipeline_summary: summary from run_pipeline()
        export_summary: summary from export_results_to_csv()
        export_error: error message if CSV export failed
    """
    all_errors = pipeline_summary["errors"].copy()
    if export_error:
        all_errors.append(f"CSV export error: {export_error}")
    
    # Compute error code distribution (only for actual errors, not successes)
    error_code_counts = {}
    for r in pipeline_summary.get("results", []):
        code = r.get("error_code")
        if code is not None:
            error_code_counts[code] = error_code_counts.get(code, 0) + 1
    
    # Compute extraction method distribution (only for successful extractions)
    extraction_method_counts = {}
    for r in pipeline_summary.get("results", []):
        method = r.get("extraction_method")
        if method is not None:
            extraction_method_counts[method] = extraction_method_counts.get(method, 0) + 1
    
    # Compute stage-by-stage breakdown
    results = pipeline_summary.get("results", [])
    total_urls = len(results)
    
    html_fetch_failures = len([r for r in results if not r["success"] and r.get("stage") == "html_fetch"])
    text_extraction_failures = len([r for r in results if not r["success"] and r.get("stage") == "text_extraction"])
    timeout_failures = len([r for r in results if not r["success"] and r.get("stage") == "timeout"])
    
    html_fetch_attempted = total_urls
    html_fetch_succeeded = total_urls - html_fetch_failures - timeout_failures
    
    text_extraction_attempted = html_fetch_succeeded
    text_extraction_succeeded = text_extraction_attempted - text_extraction_failures
    
    stage_breakdown = {
        "html_fetch": {
            "attempted": html_fetch_attempted,
            "succeeded": html_fetch_succeeded,
            "failed": html_fetch_failures
        },
        "text_extraction": {
            "attempted": text_extraction_attempted,
            "succeeded": text_extraction_succeeded,
            "failed": text_extraction_failures
        },
        "timeout": timeout_failures,
        "complete": pipeline_summary["successful_URLs"]
    }

    # search discovery section for status file 
    discovery = pipeline_summary.get("search_discovery")
    search_discovery_section = None
    if discovery:
        search_error_code_counts = {}
        for sr in discovery.get("search_results", []):
            code = sr.get("error_code")
            if code is not None:
                search_error_code_counts[code] = search_error_code_counts.get(code, 0) + 1

        search_discovery_section = {
            "total_searches": discovery["total_searches"],
            "successful_searches": discovery["successful_searches"],
            "failed_searches": discovery["failed_searches"],
            "total_urls_discovered": discovery["total_urls_discovered"],
            "timing": discovery["timing"],
            "per_search_results": discovery["search_results"],
            "error_code_distribution": search_error_code_counts,
            "errors": discovery["errors"],
            "warnings": discovery["warnings"],
        }
    
    # Build list of processed URLs with their status.
    # If search_discovery is present, only include URLs discovered in *this* run
    # so scheduled retry carryover from older runs does not leak into the UI.
    discovered_url_set = set(discovery.get("urls", [])) if discovery else None
    processed_urls = []
    for r in results:
        url = r.get("url")
        if not url:
            continue
        if discovered_url_set is not None and url not in discovered_url_set:
            continue
        processed_urls.append({
            "url": url,
            "success": r.get("success", False),
            "error": r.get("error") if not r.get("success") else None,
        })
    
    status_data = {
        "timestamp": datetime.now().isoformat(),
        "success": pipeline_summary["failed_URLs"] == 0 and export_error is None,
        "search_discovery": search_discovery_section,
        "total_URLs": pipeline_summary["total_URLs"],
        "successful_URLs": pipeline_summary["successful_URLs"],
        "failed_URLs": pipeline_summary["failed_URLs"],
        "processed_urls": processed_urls,
        "processing_timing": pipeline_summary.get("timing", {}),
        "extraction_method_distribution": extraction_method_counts,
        "stage_breakdown": stage_breakdown,
        "error_code_distribution": error_code_counts,
        "domain_metrics": pipeline_summary.get("domain_metrics", {}),
        "csv_files": [],
        "errors": all_errors,
        "warnings": pipeline_summary.get("warnings", [])
    }
    if pipeline_summary.get("scheduled"):
        status_data["scheduled"] = pipeline_summary["scheduled"]

    if export_summary:
        for table_name, row_count in export_summary.items():
            if row_count is not None:
                status_data["csv_files"].append({
                    "filename": f"{table_name}.csv",
                    "rows": row_count
                })
    
    status_path = os.path.join(results_dir, "status.json")
    try:
        with open(status_path, 'w') as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        raise Exception(f"Failed to write status.json: {e}")
        


def main():
    # for main execution
    try:
        args = parse_args()

        config = load_config(args.config)
        # creates results directory with timestamp
        results_dir = add_timestamp_results_directory()
        # run the pipeline
        pipeline_summary = run_pipeline(config, results_dir)
        
        # Export results to CSV, taking only records from this run
        html_ids = pipeline_summary.get("html_ids", [])
        search_discovery = pipeline_summary.get("search_discovery") or {}
        url_to_search_link_id = search_discovery.get("url_to_search_link_id") or {}
        search_link_ids = list(url_to_search_link_id.values())
        export_error = None
        try:
            export_summary = export_results_to_csv(
                results_dir,
                html_ids=html_ids,
                search_link_ids=search_link_ids,
            )
            if export_summary is None:
                export_error = "Export returned no results"
        except Exception as e:
            export_summary = None
            export_error = str(e)
        
        # Write status.json
        write_status_json(results_dir, pipeline_summary, export_summary, export_error=export_error)
        
        # Exit with appropriate code
        if pipeline_summary["failed_URLs"] > 0 or export_error:
            sys.exit(1)
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()