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
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from dbconnection import create_connection
from html_storer import store_html
from export_utils import export_all_tables, compute_domain_metrics
from selenium import webdriver

# Load environment variables
load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")

PROJECT_ROOT = Path(__file__).parent
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
        description="Runs the legislative scraping pipeline with config file containing URLs and basic settings and a results diirectory"
    )
    # provides path to json config file
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the JSON configuration file"
    )
    return parser.parse_args()


def load_config(config_path):
    """
    Load and validate the configuration file.
    
    Args:
        config_path: Path to the JSON config file
    
    Returns:
        dict: Validated configuration dictionary
    errors raies:
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
    
    # Validate required fields
    if "URLs" not in config:
        raise ValueError("Config must contain 'URLs' field")
    
    if not isinstance(config["URLs"], list):
        raise ValueError("'URLs' must be a list")
    
    if len(config["URLs"]) == 0:
        raise ValueError("URLs list cannot be empty")
    
    # Set defaults for optional fields
    if "settings" not in config:
        config["settings"] = {}
    # defaults to true for duplicates
    if "allow_duplicates" not in config["settings"]:
        config["settings"]["allow_duplicates"] = True
    
    return config


def process_url(url, allow_duplicates, driver=None):
    """
    Process a single URL through the pipeline.
    
    Args:
        url: URL to process
        allow_duplicates: Whether to allow duplicate processing
        driver: Optional existing WebDriver instance to reuse
    
    Returns:
        dict: Result dictionary with success status, details, and warnings
    """
    try:
        result = store_html(url, allow_duplicates=allow_duplicates, driver=driver)
        
        # Check for errors first (e.g. Cloudflare block, embedded-doc failure)
        if result.get("error"):
            return {
                "url": url,
                "success": False,
                "html_id": result.get("html_id"),
                "warning": result.get("warning"),
                "error": result["error"]
            }
        elif result.get("html_id") is not None:
            return {
                "url": url,
                "success": True,
                "html_id": result["html_id"],
                "warning": result.get("warning"),
                "error": None
            }
        else:
            return {
                "url": url,
                "success": False,
                "html_id": None,
                "warning": result.get("warning"),
                "error": result.get("error") or "Failed to store HTML"
            }
    
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "html_id": None,
            "warning": None,
            "error": str(e)
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
    allow_duplicates = config["settings"]["allow_duplicates"]
    
    results = []
    successful_URLs = 0
    failed_URLs = 0
    errors = []
    warnings = []
    
    print(f"# running pipeline, writing to results directory: {results_dir}")
    print(f"{'#'*70}\n")
    
    # Max seconds to spend on a single URL before skipping it
    PER_URL_TIMEOUT = 20

    # Create a single shared browser instance for all URLs
    driver = None
    try:
        
        driver = webdriver.Firefox()
        
        for idx, url in enumerate(URLs, 1):
            

            # Run process_url in a daemon thread with a timeout so one
            # stuck URL can never block the rest of the pipeline.
            result_holder = [None]

            def _run(u=url, dup=allow_duplicates, d=driver):
                result_holder[0] = process_url(u, dup, driver=d)

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout=PER_URL_TIMEOUT)

            if thread.is_alive():
                # Thread is still running — URL timed out
                result = {
                    "url": url,
                    "success": False,
                    "html_id": None,
                    "warning": None,
                    "error": f"Timed out after {PER_URL_TIMEOUT}s"
                }
               
                # kill stuck browser 
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = webdriver.Firefox()
            else:
                result = result_holder[0]

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
    finally:
        # Close the shared browser when done with all URLs
        if driver:
            driver.quit()
    
    # collect html_ids from successful runs for csv export filtering
    html_ids = [r["html_id"] for r in results if r["success"] and r["html_id"] is not None]

    # compute per-domain success metrics
    domain_metrics = compute_domain_metrics(results)
    
    # summary of pipleine execution
    summary = {
        "total_URLs": len(URLs),
        "successful_URLs": successful_URLs,
        "failed_URLs": failed_URLs,
        "results": results,
        "errors": errors,
        "warnings": warnings,
        "html_ids": html_ids,
        "domain_metrics": domain_metrics
    }
    print(f"# pipeline execution complete")
    print(f"#Total: {len(URLs)} | Success: {successful_URLs} | Failed: {failed_URLs}")
    return summary


def export_results_to_csv(results_dir, html_ids=None):
    """
    Exports db tables to csv, filtered by html_ids from this run
    
    Args:
        results_dir: Directory to save CSV files
        html_ids: List of html IDs to export (only bills from this run - can change if want all)
    
    Returns:
        dict: Export summary with row counts
    """
    
    try:
        connection = create_connection(host, user, pw, database)
        # checks conneciton to db
        if connection is None:
            print("Failed to connect to database for export")
            return None
        
        exports = export_all_tables(connection, results_dir, html_ids=html_ids)
        
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
    
    status_data = {
        "timestamp": datetime.now().isoformat(),
        "success": pipeline_summary["failed_URLs"] == 0 and export_error is None,
        "total_URLs": pipeline_summary["total_URLs"],
        "successful_URLs": pipeline_summary["successful_URLs"],
        "failed_URLs": pipeline_summary["failed_URLs"],
        "domain_metrics": pipeline_summary.get("domain_metrics", {}),
        "csv_files": [],
        "errors": all_errors,
        "warnings": pipeline_summary.get("warnings", [])
    }
    
    # if export was successful adds csv file info
    if export_summary:
        for table_name, row_count in export_summary.items():
            if row_count is not None:
                status_data["csv_files"].append({
                    "filename": f"{table_name}.csv",
                    "rows": row_count
                })
    
    # write status.json
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
        
        # Export results to CSV, taking only bills from that run
        html_ids = pipeline_summary.get("html_ids", [])
        export_error = None
        try:
            export_summary = export_results_to_csv(results_dir, html_ids=html_ids)
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
