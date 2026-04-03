This directory includes information for setting up scheduled runs of the pipeline 

### set up for choronological scraping 


 -> TODO!

### Master pipeline script 

The master script run_scheduled.py runs the full scraping pipeline. 

This does the following: 

## Utilizes SERPAPI to search all terms in the given juridstiction 

## Discads the URLS that already exist in the searched_links database to avoid duplication 

## Passes all unique links to main pipeline which 

1) Extracts html from a given link 

2) If HTML processing is succesful, or if API workaround exists, processes text 

## Imports HTML and text to database, along with related metrics 

## In both HTML and text stages, processes over previously unsuccesful sites, and updates database if rety makes them succesful. 


## Logging 

Pipeline creates comprehensive logging through status file and exported CSVs in a timestamped folder in a results directory 

## Logging includes 

- Time of execution 
- The number of URLs processed
- Success/failure status
- Error messages
- Execution duration
- Detailed output from each script
- Success statistics per domain 
- Metrics on execution method, time of processing per search/method 
- Search params 
- Path to output files 


## Error Handling

The master script includes comprehensive error handling:

- Missing/invalid config input: missing config file, invalid JSON, missing required fields

- Database failures: MySQL connector errors during discovery (mysql.connector.Error in search_layer.py) and connection failures (raised as RuntimeError / checked None in run_pipeline.py and run_scheduled.py)

- SERP API problems: missing SERP API key, SERP API returning None, and exceptions during SERP API.

- No search results: treated as a warning/error condition when SERP returns no organic links for a query (SEARCH_NO_RESULTS).

 - Per-URL scraping failures: any exception during HTML fetch / text extraction 

-  Timeouts: URL processing that exceeds the per-URL timeout is caught via thread.join and marked as a timeout failure (PIPELINE_TIMEOUT).

- Browser shutdown issues: exceptions during driver.quit() are swallowed to keep the pipeline moving.

- CSV export failures: any exception during export is caught and recorded 

- Status file write failures: exceptions writing status.json raise (and are treated as fatal)

- Scraping-based erors are reported via set rules in error-taxonomy files.

### The results file also reports warnings.

### DEPENDENCIES 

-> TO DO! 

