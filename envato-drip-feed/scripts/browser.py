from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def driver(selenium_url: str):
    options = Options()
    options.add_argument("--user-data-dir=/home/seluser/profile")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--window-size=1440,1100")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": "/home/seluser/Downloads",
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Remote(command_executor=selenium_url, options=options)

