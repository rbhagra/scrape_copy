"""
Search discovery layer: resolves search terms into URLs via SERP API
and records each discovered link in the search_links table.
"""
import os
import time
import importlib
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from mysql.connector import Error
from dotenv import load_dotenv
from error_codes import ErrorCode

load_dotenv()
serp_api_key = os.getenv("serp_api_key")


def split_date_range_monthly(start_date_str, end_date_str):
    """
    Split a date range into monthly increments.
    
    Args:
        start_date_str: Start date in YYYY-MM-DD format
        end_date_str: End date in YYYY-MM-DD format
    
    Returns:
        List of tuples (month_start, month_end) as datetime objects
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    date_ranges = []
    current_start = start_date
    
    while current_start <= end_date:
        # Calculate the end of the current month
        next_month_start = current_start + relativedelta(months=1)
        # get last day of current month 
        month_end = min(next_month_start - timedelta(days=1), end_date)
        
        date_ranges.append((current_start, month_end))
        current_start = next_month_start
    
    return date_ranges


def _build_query(term, domain, inurl=None, start_date=None, end_date=None):
    """
    Build a Google query string from a search term, domain, optional inurl filter,
    and optional date range using after:/before: operators.
    
    Args:
        term: Search term
        domain: Domain to restrict search to
        inurl: Optional URL path filter
        start_date: Optional start date (datetime object)
        end_date: Optional end date (datetime object)
    
    Returns:
        Query string like: "term" site:domain after:2025-01-01 before:2025-01-31
    """
    query = f'"{term}" site:{domain}'
    if inurl:
        query += f" inurl:{inurl}"
    if start_date and end_date:
        query += f" after:{start_date.strftime('%Y-%m-%d')} before:{end_date.strftime('%Y-%m-%d')}"
    return query




def _search_serp_api(query, max_results, max_retries=2):
    """
    Call SERP API with retry logic and return a structured result dict.

    Args:
        query: Search query string (may include after:/before: date operators)
        max_results: Maximum number of results to return
        max_retries: Number of retry attempts on failure

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

    search_params = {
        "engine": "google",
        "q": query,
        "num": max_results,
        "location": "United States",
        "google_domain": "google.com",
        "hl": "en",
        "gl": "us",
    }

    for attempt in range(1 + max_retries):
        num_tries += 1
        try:
            serpapi = importlib.import_module("serpapi")
            client = serpapi.Client(api_key=serp_api_key)
            raw = client.search(search_params)

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


def _record_links_batch(cursor, links_data):
    """Insert discovered links in one batch and return link -> inserted id."""
    if not links_data:
        return {}

    insert_query = """INSERT INTO search_links
        (search_method, keyword_search, other_filters, link,
         processing_time, num_api_tries, num_api_failures, failure_type, is_successful)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
    rows = [
        (
            data["search_method"],
            data["keyword_search"],
            data["other_filters"],
            data["link"],
            data["processing_time"],
            data["num_api_tries"],
            data["num_api_failures"],
            data["failure_type"],
            data["is_successful"],
        )
        for data in links_data
    ]
    
    cursor.executemany(insert_query, rows)

    link_to_id = {}
    for link in [data["link"] for data in links_data]:
        cursor.execute(
            """SELECT id FROM search_links
               WHERE link = %s AND is_successful = 1
               ORDER BY id DESC LIMIT 1""",
            (link,),
        )
        row = cursor.fetchone()
        if row: # guard none
            link_to_id[link] = int(row[0])

    return link_to_id


def _fetch_serp_worker(query_info):
    """Worker function for ThreadPoolExecutor - executes a single SERP API call."""
    serp_result = _search_serp_api(query_info["query"], query_info["max_results"])
    return {"query_info": query_info, "serp": serp_result}


def discover_urls(searches, connection, incremental=False, settings=None):
    """
    For each search entry, query SERP API in parallel, record results in search_links,
    and return a structured discovery report.

    Args:
        searches: list of search entry dicts, each with keys:
            term, domain, inurl (optional), max_results (optional)
        incremental: if True, skip URLs already present in search_links
            (used by scheduled runs to avoid re-recording known URLs)
        settings: optional dict with date range settings:
            "Start Date" and "End Date" in YYYY-MM-DD format

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
    
    # Base dates in case no dates are given or dates are invalid
    start_date_str_base = "2010-01-01"
    end_date_str_base = datetime.now().strftime("%Y-%m-%d")
    
    # Extract date range from settings if provided
    start_date_str = None
    end_date_str = None
    if settings:
        start_date_str = settings.get("Start Date")
        end_date_str = settings.get("End Date")
    
    # Split date range into monthly increments
    date_ranges = []
    if start_date_str and end_date_str:
        try:
            date_ranges = split_date_range_monthly(start_date_str, end_date_str)
        except ValueError as e:
            all_warnings.append(f"Invalid date format in settings: {e}. Searching with base dates.")
            date_ranges = split_date_range_monthly(start_date_str_base, end_date_str_base)
    else:
        # Default to base dates if dates not provided or incomplete
        date_ranges = split_date_range_monthly(start_date_str_base, end_date_str_base)

    # Phase 1: Build all queries upfront
    from constants import MAXIMUM_RESULTS
    all_queries = []
    
    for entry in searches:
        term = entry["term"]
        domain = entry["domain"]
        inurl = entry.get("inurl")  # May be None if no signal for this domain
        max_results = entry.get("max_results", MAXIMUM_RESULTS)
        
        for month_start, month_end in date_ranges:
            query = _build_query(term, domain, inurl, start_date=month_start, end_date=month_end)
            all_queries.append({
                "query": query,
                "domain": domain,
                "inurl": inurl,
                "max_results": max_results,
                "term": term,
                "month_start": month_start,
                "month_end": month_end,
            })
    
    # Execute SERP API calls in parallel
    serp_results = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_query = {executor.submit(_fetch_serp_worker, q): q for q in all_queries}
        
        for future in as_completed(future_to_query):
            query_info = future_to_query[future]
            try:
                serp_results.append(future.result())
            except Exception as e:
                all_errors.append(f"{query_info['query']}: {e}")
                serp_results.append({
                    "query_info": query_info,
                    "serp": {
                        "results": {},
                        "num_tries": 0,
                        "num_failures": 1,
                        "error": str(e),
                        "error_code": ErrorCode.SERP_API_FAILED.value,
                        "duration": 0.0,
                    },
                })
    #writing to db sequentially
        cursor = None
    try:
        cursor = connection.cursor()
        
        for result in serp_results:
            query_info = result["query_info"]
            serp = result["serp"]
            query = query_info["query"]
            domain = query_info["domain"]
            duration = serp["duration"]
            entry_error = serp["error"]
            entry_error_code = serp["error_code"]
            
            if entry_error:
                all_errors.append(f"{query}: {entry_error}")
                search_results.append({
                    "query": query,
                    "domain": domain,
                    "duration_seconds": duration,
                    "num_tries": serp["num_tries"],
                    "num_failures": serp["num_failures"],
                    "results_count": 0,
                    "error": entry_error,
                    "error_code": entry_error_code,
                })
                search_durations.append(duration)
                continue
            
            results_dict = serp["results"]
            organic = results_dict.get("organic_results", []) if isinstance(results_dict, dict) else []
            raw_links = [r.get("link") for r in organic if r.get("link")]
            
            if not raw_links:
                entry_error = f"No organic results for query: {query}"
                entry_error_code = ErrorCode.SEARCH_NO_RESULTS.value
                all_warnings.append(entry_error)
                search_results.append({
                    "query": query,
                    "domain": domain,
                    "duration_seconds": duration,
                    "num_tries": serp["num_tries"],
                    "num_failures": serp["num_failures"],
                    "results_count": 0,
                    "error": entry_error,
                    "error_code": entry_error_code,
                })
                search_durations.append(duration)
                continue
            
            links_to_insert = []
            links_seen_in_query = set()
            entry_new = 0
            
            for link in raw_links:
                try:
                    if incremental:
                        cursor.execute(
                            "SELECT id FROM search_links WHERE link = %s LIMIT 1",
                            (link,),
                        )
                        existing = cursor.fetchone()
                        if existing:
                            continue
                    
                    links_to_insert.append({
                        "search_method": "SERPAPI",
                        "keyword_search": query,
                        "other_filters": None,
                        "link": link,
                        "processing_time": duration,
                        "num_api_tries": serp["num_tries"],
                        "num_api_failures": serp["num_failures"],
                        "failure_type": None,
                        "is_successful": 1,
                    })
                    links_seen_in_query.add(link)
                    entry_new += 1
                    
                except Error as e:
                    link_str = link if isinstance(link, str) else str(link)
                    snippet = (link_str[:200] + "…") if len(link_str) > 200 else link_str
                    all_warnings.append(f"Skipping discovered URL (database): {e} link={snippet!r}")
                    continue
            
            if links_to_insert:
                try:
                    link_ids = _record_links_batch(cursor, links_to_insert)
                    connection.commit()
                    url_to_search_link_id.update(link_ids)
                    all_urls.update(data["link"] for data in links_to_insert)
                except Error as e:
                    try:
                        connection.rollback()
                    except Exception:
                        pass
                    all_warnings.append(f"Batch insert failed for query {query}: {e}")
            
            search_durations.append(duration)
            search_results.append({
                "query": query,
                "domain": domain,
                "duration_seconds": duration,
                "num_tries": serp["num_tries"],
                "num_failures": serp["num_failures"],
                "results_count": entry_new if incremental else len(raw_links),
                "error": None,
                "error_code": None,
            })
    
    except Error as e:
        err_msg = f"Database error during search discovery: {e}"
        print(f"  {err_msg}")
        all_errors.append(err_msg)
        try:
            connection.rollback()
        except Exception:
            pass
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
        
    }
    
    print(f"\n  Total unique URLs discovered: {len(url_list)}")

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
