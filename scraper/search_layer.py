"""
Search discovery layer: resolves search terms into URLs via SERP API
and records each discovered link in the search_links table.
"""
import os
import time
import importlib
from mysql.connector import Error
from dotenv import load_dotenv
from error_codes import ErrorCode

load_dotenv()
serp_api_key = os.getenv("serp_api_key")


def _build_query(term, domain, inurl=None):
    """Build a Google query string from a search term, domain, and optional inurl filter."""
    query = f'"{term}" site:{domain}'
    if inurl:
        query += f" inurl:{inurl}"
    return query




def _search_serp_api(query, max_results, max_retries=2):
    """
    Call SERP API with retry logic and return a structured result dict.

    Returns:
        dict with keys: results, num_tries, num_failures, error, error_code, duration
    """
    if not serp_api_key:
        return {
            "results": {},
            "num_tries": 0,
            "num_failures": 0,
            "error": "SERP API key not configured (serp_api_key in .env)",
            "error_code": ErrorCode.SERP_API_KEY_MISSING.value,
            "duration": 0.0,
        }

    start = time.time()
    num_tries = 0
    num_failures = 0
    last_error = None

    for attempt in range(1 + max_retries):
        num_tries += 1
        try:
            serpapi = importlib.import_module("serpapi")
            client = serpapi.Client(api_key=serp_api_key)
            raw = client.search({
                "engine": "google",
                "q": query,
                "num": max_results,
                "location": "United States",
                "google_domain": "google.com",
                "hl": "en",
                "gl": "us",
            })

            if raw is None:
                num_failures += 1
                last_error = "SERP API returned None"
                continue

            if isinstance(raw, dict):
                result_dict = raw
            elif hasattr(raw, "as_dict"):
                try:
                    result_dict = raw.as_dict() or {}
                except Exception:
                    result_dict = {}
            else:
                try:
                    result_dict = dict(raw)
                except Exception:
                    result_dict = {"_raw_result_str": str(raw)}

            duration = round(time.time() - start, 3)
            return {
                "results": result_dict,
                "num_tries": num_tries,
                "num_failures": num_failures,
                "error": None,
                "error_code": None,
                "duration": duration,
            }

        except Exception as e:
            num_failures += 1
            last_error = str(e)
            print(f"  SERP API attempt {attempt + 1} failed for '{query}': {e}")

    duration = round(time.time() - start, 3)
    return {
        "results": {},
        "num_tries": num_tries,
        "num_failures": num_failures,
        "error": f"SERP API failed after {num_tries} attempts: {last_error}",
        "error_code": ErrorCode.SERP_API_FAILED.value,
        "duration": duration,
    }


def _record_link(cursor, search_method, keyword_search, other_filters, link,
                 processing_time=None, num_api_tries=0, num_api_failures=0,
                 failure_type=None, is_successful=1):
    """Insert a single discovered link into search_links with tracking columns.

    Returns:
        int: The auto-generated id of the inserted row.
    """
    insert_query = """INSERT INTO search_links
        (search_method, keyword_search, other_filters, link,
         processing_time, num_api_tries, num_api_failures, failure_type, is_successful)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    cursor.execute(insert_query, (
        search_method, keyword_search, other_filters, link,
        processing_time, num_api_tries, num_api_failures, failure_type, is_successful,
    ))
    return cursor.lastrowid


def discover_urls(searches, connection, incremental=False):
    """
    For each search entry, query SERP API, record results in search_links,
    and return a structured discovery report.

    Args:
        searches: list of search entry dicts, each with keys:
            term, domain, inurl (optional), max_results (optional)
        incremental: if True, skip URLs already present in search_links
            (used by scheduled runs to avoid re-recording known URLs)

    Returns:
        dict with keys:
            urls                   - deduplicated list of discovered URLs
            url_to_search_link_id  - dict mapping each URL to its search_links.id
            search_results         - per-entry metrics list
            timing                 - aggregate timing stats
            total_searches / successful_searches / failed_searches
            total_urls_discovered
            errors                 - list of error strings
            warnings               - list of warning strings
    """
    overall_start = time.time()
    all_urls = set()
    url_to_search_link_id = {}
    search_results = []
    all_errors = []
    all_warnings = []
    search_durations = []

    cursor = None
    try:
        cursor = connection.cursor()

        for entry in searches:
            term = entry["term"]
            domain = entry["domain"]
            inurl = entry.get("inurl")
            max_results = entry.get("max_results", 10)

            query = _build_query(term, domain, inurl)

            entry_start = time.time()
            print(f"  Searching: {query}  (max {max_results} results)")

            serp = _search_serp_api(query, max_results)
            api_duration = serp["duration"]

            entry_error = serp["error"]
            entry_error_code = serp["error_code"]

            if entry_error:
                print(f"    ERROR: {entry_error}")
                all_errors.append(f"{query}: {entry_error}")
                search_results.append({
                    "query": query,
                    "domain": domain,
                    "duration_seconds": round(time.time() - entry_start, 3),
                    "num_tries": serp["num_tries"],
                    "num_failures": serp["num_failures"],
                    "results_count": 0,
                    "error": entry_error,
                    "error_code": entry_error_code,
                })
                search_durations.append(time.time() - entry_start)
                continue

            results_dict = serp["results"]
            organic = results_dict.get("organic_results", []) if isinstance(results_dict, dict) else []
            raw_links = [r.get("link") for r in organic if r.get("link")]

            if not raw_links:
                entry_error = f"No organic results for query: {query}"
                entry_error_code = ErrorCode.SEARCH_NO_RESULTS.value
                print(f"    WARNING: {entry_error}")
                all_warnings.append(entry_error)
                search_results.append({
                    "query": query,
                    "domain": domain,
                    "duration_seconds": round(time.time() - entry_start, 3),
                    "num_tries": serp["num_tries"],
                    "num_failures": serp["num_failures"],
                    "results_count": 0,
                    "error": entry_error,
                    "error_code": entry_error_code,
                })
                search_durations.append(time.time() - entry_start)
                continue

            entry_new = 0
            for link in raw_links:
                if incremental:
                    cursor.execute(
                        "SELECT id FROM search_links WHERE link = %s LIMIT 1",
                        (link,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        continue

                link_id = _record_link(
                    cursor, "SERPAPI", query, None, link,
                    processing_time=api_duration,
                    num_api_tries=serp["num_tries"],
                    num_api_failures=serp["num_failures"],
                    is_successful=1,
                )
                if link not in all_urls:
                    url_to_search_link_id[link] = link_id
                all_urls.add(link)
                entry_new += 1

            if incremental:
                print(f"    {entry_new} new results")
            else:
                print(f"    {len(raw_links)} results found")

            entry_duration = round(time.time() - entry_start, 3)
            search_durations.append(entry_duration)

            search_results.append({
                "query": query,
                "domain": domain,
                "duration_seconds": entry_duration,
                "num_tries": serp["num_tries"],
                "num_failures": serp["num_failures"],
                "results_count": entry_new if incremental else len(raw_links),
                "error": None,
                "error_code": None,
            })

        connection.commit()

    except Error as e:
        err_msg = f"Database error during search discovery: {e}"
        print(f"  {err_msg}")
        all_errors.append(err_msg)
    finally:
        if cursor:
            try:
                cursor.fetchall() if cursor.with_rows else None
                cursor.close()
            except Exception:
                pass

    url_list = list(all_urls)
    overall_duration = round(time.time() - overall_start, 3)

    successful_searches = sum(1 for r in search_results if r["error"] is None)
    failed_searches = len(search_results) - successful_searches

    timing = {
        "total_duration_seconds": overall_duration,
        "avg_per_search_seconds": round(sum(search_durations) / len(search_durations), 3) if search_durations else 0,
        "min_search_seconds": round(min(search_durations), 3) if search_durations else 0,
        "max_search_seconds": round(max(search_durations), 3) if search_durations else 0,
    }

    print(f"\n  Total unique URLs discovered: {len(url_list)}")
    print(f"  Search timing: {overall_duration}s total, "
          f"{timing['avg_per_search_seconds']}s avg per query\n")

    return {
        "urls": url_list,
        "url_to_search_link_id": url_to_search_link_id,
        "search_results": search_results,
        "timing": timing,
        "total_searches": len(search_results),
        "successful_searches": successful_searches,
        "failed_searches": failed_searches,
        "total_urls_discovered": len(url_list),
        "errors": all_errors,
        "warnings": all_warnings,
    }
