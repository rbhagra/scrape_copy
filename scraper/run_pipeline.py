#!/usr/bin/env python3
"""
Command-line interface for the legislative scraping pipeline.

Usage:
    python run_pipeline.py --config path_to_config.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from dbconnection import create_connection
from html_storer import store_html
from export_utils import export_all_tables

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


def process_url(url, allow_duplicates):
    """
    Process a single URL through the pipeline.
    
    Args:
        url: URL to process
        allow_duplicates: Whether to allow duplicate processing
    
    Returns:
        dict: Result dictionary with success status and details
    """
    try:
        
        
        result_id = store_html(url, allow_duplicates=allow_duplicates)
        
        if result_id is not None:
            return {
                "url": url,
                "success": True,
                "html_id": result_id,
                "error": None
            }
        else:
            return {
                "url": url,
                "success": False,
                "html_id": None,
                "error": "Failed to store HTML (errors logged)"
            }
    
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "html_id": None,
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
    
   
    print(f"# running pipeline, writing to results directory: {results_dir}")
    print(f"{'#'*70}\n")
    
    for idx, url in enumerate(URLs, 1):
        
        result = process_url(url, allow_duplicates)
        results.append(result)
        
        if result["success"]:
            successful_URLs += 1
        else:
            failed_URLs += 1
            error_msg = f"Failed to process {url}: {result['error']}"
            errors.append(error_msg)
    
    # collect html_ids from successful runs for csv export filtering
    html_ids = [r["html_id"] for r in results if r["success"] and r["html_id"] is not None]
    
    # summary of pipleine execution
    summary = {
        "total_URLs": len(URLs),
        "successful_URLs": successful_URLs,
        "failed_URLs": failed_URLs,
        "results": results,
        "errors": errors,
        "html_ids": html_ids
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


def write_status_json(results_dir, pipeline_summary, export_summary):
    """
    Write status.json with execution results.
    
    Args:
        results_dir: Directory to save status.json
        pipeline_summary: summary from run_pipeline()
        export_summary: summary from export_results_to_csv()
    """
    status_data = {
        "timestamp": datetime.now().isoformat(),
        "success": pipeline_summary["failed_URLs"] == 0,
        "total_URLs": pipeline_summary["total_URLs"],
        "successful_URLs": pipeline_summary["successful_URLs"],
        "failed_URLs": pipeline_summary["failed_URLs"],
        "csv_files": [],
        "pipeline errors": pipeline_summary["errors"]
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
        
        # Export results to CSV, taking only bills fro that run
        html_ids = pipeline_summary.get("html_ids", [])
        export_summary = export_results_to_csv(results_dir, html_ids=html_ids)
        
        # Write status.json
        write_status_json(results_dir, pipeline_summary, export_summary)
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {e}")
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
