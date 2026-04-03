"""
Scheduled / resumable pipeline entry point.

Re-runs all searches from config (deduplicating discovered URLs),
retries all previously failed work, processes new URLs, and exports results.

Usage:
    python run_scheduled.py --config path_to_config.json
"""
import argparse
import os
import sys
from dotenv import load_dotenv

from dbconnection import create_connection
from txt_storer import retrieve_txt
from resume_utils import (
    get_failed_html_urls,
    get_failed_text_html_ids,
    cleanup_failed_html,
    cleanup_failed_text,
)
from run_pipeline import (
    validate_config,
    run_pipeline,
    export_results_to_csv,
    write_status_json,
    add_timestamp_results_directory,
)
load_dotenv()
pw = os.getenv("password")
host = os.getenv("host_name")
user = os.getenv("user_name")
database = os.getenv("database_name")


def parse_args():
    ### parses the command line arguments
    parser = argparse.ArgumentParser(
        description="Scheduled/resumable pipeline: incremental search + retry failures"
    )
    parser.add_argument(
        "--config", type=str, required=True,
        help="Path to the JSON configuration file",
    )
    return parser.parse_args()


def retry_text_extractions(failed_text_rows):
    """Re-run text extraction for HTML records whose text extraction previously failed.

    Returns list of result dicts
    """
    if not failed_text_rows:
        return []

    results = []
    for html_id, source_url, search_link_id in failed_text_rows:
        raw = retrieve_txt(html_id=html_id, search_link_id=search_link_id) or {}
        result = {
            "url": source_url,
            "html_id": html_id,
            "search_link_id": search_link_id,
            "success": raw.get("success", False),
            "error": raw.get("error"),
            "warning": raw.get("warning"),
            "is_text_retry": True,
        }
        results.append(result)

    return results


def with_connection(callback):
    """Open a DB connection, run callback(conn), and always close it."""
    conn = create_connection(host, user, pw, database)
    if conn is None:
        raise RuntimeError("Failed to connect to database")
    try:
        return callback(conn)
    finally:
        conn.close()


def empty_pipeline_summary():
    """Return an empty summary shaped like run_pipeline()."""
    return {
        "total_URLs": 0,
        "successful_URLs": 0,
        "failed_URLs": 0,
        "results": [],
        "errors": [],
        "warnings": [],
        "html_ids": [],
        "domain_metrics": {},
        "timing": {},
    }


def prepare_retries(url_to_search_link_id):
    """Find retry work, clean up failed rows, and return retry inputs."""
    def _run(conn):
        failed_html_rows = get_failed_html_urls(conn)
        failed_text_rows = get_failed_text_html_ids(conn)
        retry_html_urls = [url for _, url in failed_html_rows]
        url_to_search_link_id.update({url: sl_id for sl_id, url in failed_html_rows})
        cleanup_failed_html(conn, retry_html_urls)
        cleanup_failed_text(conn, [hid for hid, _, _ in failed_text_rows])
        return retry_html_urls, failed_text_rows

    return with_connection(_run)


def run_incremental_search(config):
    """Run search discovery and return its discovery payload."""
    from search_layer import discover_urls
    return with_connection(lambda conn: discover_urls(config["searches"], conn, incremental=True))


def run_retry_pipeline(config, results_dir, discovery, retry_html_urls, url_to_search_link_id):
    """Run the normal pipeline over new URLs plus HTML retries."""
    all_urls = list(dict.fromkeys(discovery["urls"] + retry_html_urls))
    if not all_urls:
        return empty_pipeline_summary()

    return run_pipeline({
        "URLs": all_urls,
        "settings": config["settings"],
        "_search_discovery": {"url_to_search_link_id": url_to_search_link_id},
    }, results_dir)


def merge_text_retry_results(pipeline_summary, discovery, failed_text_rows):
    """Apply text-only retry results onto the pipeline summary."""
    text_results = retry_text_extractions(failed_text_rows)

    for r in text_results:
        pipeline_summary["results"].append(r)
        if r["success"]:
            pipeline_summary["successful_URLs"] += 1
            if r.get("html_id"):
                pipeline_summary["html_ids"].append(r["html_id"])
        else:
            pipeline_summary["failed_URLs"] += 1
            err = r.get("error") or r.get("warning") or "Text extraction failed"
            pipeline_summary["errors"].append(
                f"Text retry failed for html_id={r.get('html_id')} ({r['url']}): {err}"
            )

    pipeline_summary["total_URLs"] += len(text_results)
    pipeline_summary["search_discovery"] = discovery
    return pipeline_summary


def attach_scheduled_stats(pipeline_summary, discovery, retry_html_urls):
    """Counts for status.json: new URLs from search, retries that succeeded."""
    retry_set = set(retry_html_urls)
    html_fixed = sum(
        1
        for r in pipeline_summary["results"]
        if r.get("url") in retry_set and r["success"] and not r.get("is_text_retry")
    )
    text_fixed = sum(
        1 for r in pipeline_summary["results"] if r.get("is_text_retry") and r["success"]
    )
    pipeline_summary["scheduled"] = {
        "new_urls_found": len(discovery.get("urls", [])),
        "urls_fixed": html_fixed + text_fixed,
    }
    return pipeline_summary


def write_status(results_dir, pipeline_summary, url_to_search_link_id):
    """Reuse the existing export/status flow from run_pipeline.py."""
    export_error = None
    try:
        export_summary = export_results_to_csv(
            results_dir,
            html_ids=pipeline_summary["html_ids"],
            search_link_ids=list(url_to_search_link_id.values()),
        )
        if export_summary is None:
            export_error = "Export returned no results"
    except Exception as e:
        export_summary = None
        export_error = str(e)

    write_status_json(results_dir, pipeline_summary, export_summary, export_error=export_error)
    return export_error


def main():
    try:
        config = validate_config(parse_args().config)
        results_dir = add_timestamp_results_directory()
        discovery = run_incremental_search(config)
        url_to_search_link_id = discovery.get("url_to_search_link_id", {})
        retry_html_urls, failed_text_rows = prepare_retries(url_to_search_link_id)
        pipeline_summary = run_retry_pipeline(
            config, results_dir, discovery, retry_html_urls, url_to_search_link_id
        )
        pipeline_summary = (
            merge_text_retry_results(pipeline_summary, discovery, failed_text_rows)
        )
        attach_scheduled_stats(pipeline_summary, discovery, retry_html_urls)
        export_error = write_status(
            results_dir, pipeline_summary, url_to_search_link_id
        )
        sys.exit(1 if pipeline_summary["failed_URLs"] > 0 or export_error else 0)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
