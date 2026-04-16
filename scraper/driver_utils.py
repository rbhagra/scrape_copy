"""Selenium WebDriver helpers"""
from selenium import webdriver
from selenium.common.exceptions import WebDriverException


def ensure_firefox_driver(driver):
    """
    Return a Firefox WebDriver that responds to commands.
    if sessions is dead, quits old handle and starts new firefox instance
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
