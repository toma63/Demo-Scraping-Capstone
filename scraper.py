"""
scraper.py - Numbeo City Rankings Scraper
============================================
Scrapes 4 datasets × 4 years from Numbeo.com and saves each to a CSV file
in the data/ directory.

Datasets  : cost_of_living, quality_of_life, crime, property_prices
Years     : current, 2023, 2024, 2025
Output    : data/<dataset>_<year>.csv  (16 files total)

Usage:
    python scraper.py
"""

import os
import re
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.numbeo.com"

# Maps dataset key -> Numbeo URL title slug
DATASETS = {
    "cost_of_living": "cost-of-living",
    "quality_of_life": "quality-of-life",
    "crime": "crime",
    "property_prices": "property-investment",
}

YEARS = ["current", "2023", "2024", "2025"]

DATA_DIR = "data"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    """Convert a column header to snake_case."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def split_city_country(val: str) -> tuple[str, str]:
    """
    Split a Numbeo 'City' cell like 'New York, NY, United States'
    into (city, country) by splitting on the *last* comma.
    """
    s = str(val).strip()
    if "," not in s:
        return s, ""
    idx = s.rfind(",")
    return s[:idx].strip(), s[idx + 1:].strip()


def build_url(dataset_slug: str, year: str) -> str:
    """Return the full Numbeo rankings URL for a given dataset and year."""
    if year == "current":
        return f"{BASE_URL}/{dataset_slug}/rankings_current.jsp"
    return f"{BASE_URL}/{dataset_slug}/rankings.jsp?title={year}"


def make_driver() -> webdriver.Chrome:
    """Create a headless Chrome WebDriver with anti-detection options."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ) # new options for Chrome which help avoid detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # Mask WebDriver navigator property
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def scrape_table(driver: webdriver.Chrome, url: str) -> list[list[str]]:
    """
    Navigate to url and extract all rows from the Numbeo DataTable (#t2).
    Handles defensive pagination in case 'Next' button exists and is enabled.
    """
    driver.get(url)
    wait = WebDriverWait(driver, 20)

    all_rows: list[list[str]] = []

    while True:
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table#t2 tbody tr"))
            )
        except TimeoutException:
            print(f"    [WARN] Timed out waiting for table on {url}")
            break

        time.sleep(1.5)  # Allow JS to finish rendering

        for tr in driver.find_elements(By.CSS_SELECTOR, "table#t2 tbody tr"):
            cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
            if cells:
                all_rows.append(cells)

        # Defensive pagination: click Next if enabled
        try:
            next_btn = driver.find_element(By.ID, "t2_next")
            if "disabled" in (next_btn.get_attribute("class") or ""):
                break
            next_btn.click()
            time.sleep(1.0)
        except NoSuchElementException:
            break  # No pagination present - single-page table

    return all_rows


def scrape_headers(driver: webdriver.Chrome) -> list[str]:
    """Extract and normalize column headers from the visible DataTable."""
    headers = []
    for th in driver.find_elements(By.CSS_SELECTOR, "table#t2 thead tr th"):
        text = th.text.strip()
        headers.append(normalize(text) if text else normalize(th.get_attribute("aria-label") or "col"))
    return headers


def scrape_dataset(driver: webdriver.Chrome, dataset_key: str, year: str) -> pd.DataFrame | None:
    """
    Scrape a single dataset/year combination and return a cleaned DataFrame,
    or None if the page returned no data.
    """
    slug = DATASETS[dataset_key]
    url = build_url(slug, year)
    print(f"  Scraping {dataset_key} / {year} -> {url}")

    driver.get(url)
    wait = WebDriverWait(driver, 20)

    # Wait for the table header to load before extracting headers
    try:
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table#t2 thead tr th"))
        )
    except TimeoutException:
        print(f"    [WARN] Table header not found for {dataset_key}/{year}")
        return None

    headers = scrape_headers(driver)
    rows = scrape_table(driver, url)

    if not rows:
        print(f"    [WARN] No rows found for {dataset_key}/{year}")
        return None

    # Build DataFrame - pad/trim rows to match header length
    n_cols = len(headers)
    clean_rows = []
    for row in rows:
        if len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))
        clean_rows.append(row[:n_cols])

    df = pd.DataFrame(clean_rows, columns=headers)

    # --- City / Country split ---
    city_col = next((c for c in df.columns if "city" in c), None)
    if city_col:
        df[["city", "country"]] = df[city_col].apply(
            lambda v: pd.Series(split_city_country(v))
        )
        if city_col not in ("city", "country"):
            df.drop(columns=[city_col], inplace=True)

    # --- Year column ---
    df["year"] = year

    # --- Clean sentinel missing values ---
    df.replace({"N/A": "", "-": "", "n/a": ""}, inplace=True)

    print(f"    [OK]  {len(df)} rows, columns: {list(df.columns)}")
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    driver = make_driver()
    results: dict[str, int] = {}

    try:
        for dataset_key in DATASETS:
            print(f"\n=== Dataset: {dataset_key} ===")
            for year in YEARS:
                df = scrape_dataset(driver, dataset_key, year)

                label = "current" if year == "current" else year
                filename = f"{DATA_DIR}/{dataset_key}_{label}.csv"

                if df is not None and not df.empty:
                    df.to_csv(filename, index=False)
                    results[filename] = len(df)
                    print(f"    Saved -> {filename}")
                else:
                    print(f"    [SKIP] No data - file not written for {dataset_key}/{year}")

                time.sleep(2.0)  # Polite delay between requests
    finally:
        driver.quit()

    print("\n" + "=" * 60)
    print("Scraping complete. Files written:")
    for path, count in results.items():
        print(f"  {path:55s}  {count:>5} rows")
    print(f"\nTotal files: {len(results)}")


if __name__ == "__main__":
    main()
