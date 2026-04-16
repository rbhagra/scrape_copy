"""Selenium WebDriver helpers (health check, Firefox lifecycle)."""
from selenium import webdriver
from selenium.common.exceptions import WebDriverException


def ensure_firefox_driver(driver):
    """
    Return a Firefox WebDriver that responds to commands.

    Pings with ``current_url``. If the session is dead, quits the old handle
    (best-effort) and starts a new Firefox instance.
    """
    if driver is not None:
        try:
            driver.current_url
            return driver
        except WebDriverException:
            try:
                driver.quit()
            except Exception:
                pass
    return webdriver.Firefox()
