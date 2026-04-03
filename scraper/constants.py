## shared constraints for the pipeline 


# Congress API bill version priority order (most preferred first)
VERSION_PRIORITY = [
    "Enrolled Bill",
    "Public Law",
    "Engrossed in House",
    "Engrossed in Senate",
    "Reported to House",
    "Reported to Senate",
    "Placed on Calendar Senate",
    "Placed on Calendar House",
    "Introduced in House",
    "Introduced in Senate",
]

# Timeout configurations (in seconds)
class Timeouts:
    # Pipeline-level timeouts
    PER_URL_TIMEOUT = 20
    PDF_URL_TIMEOUT = 120
    
    # HTTP request timeouts
    DEFAULT_REQUEST = 15
    PDF_DOWNLOAD = 60
    PDF_HTML_FETCH = 100
    EMBEDDED_DOC = 30
    
    # Selenium timeouts
    PAGE_LOAD = 10
    ELEMENT_WAIT = 10
    WEBDRIVER_WAIT = 2

# Text extraction thresholds
MIN_BILL_TEXT_LENGTH = 500
PDF_UNKNOWN_CHAR_THRESHOLD = 0.3
