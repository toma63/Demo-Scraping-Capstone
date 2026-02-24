# -*- coding: utf-8 -*-
"""
query_db.py - Numbeo Database Query Tool
==========================================
Interactive CLI menu for querying the numbeo.db SQLite database.

Menu options:
  1. Top N cities by Cost of Living Index
  2. Top N cities by Quality of Life Index
  3. Cities ranked by Crime Index with Quality of Life score  (JOIN)
  4. Cost of Living vs Property Prices for a country          (JOIN)
  5. Year-over-year trend for a specific city
  6. Countries with most cities in top 20 for any index
  7. Custom SQL query
  0. Exit

Usage:
    python query_db.py
"""

import sqlite3
import sys

# Force UTF-8 output on Windows (default console encoding is cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from tabulate import tabulate
except ImportError:
    print("[ERROR] tabulate is not installed.  Run: pip install tabulate")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = "numbeo.db"
TABLE_FMT = "rounded_outline"
FLOAT_FMT = ".2f"

MENU = """
+------------------------------------------------------+
|        Numbeo City Rankings Query Tool               |
+------------------------------------------------------+
|  1. Top N cities by Cost of Living Index             |
|  2. Top N cities by Quality of Life Index            |
|  3. Crime vs Quality of Life (JOIN)                  |
|  4. Cost of Living vs Property Prices by country     |
|     (JOIN)                                           |
|  5. Year-over-year trend for a city                  |
|  6. Countries with most cities in top 20             |
|  7. Custom SQL query                                 |
|  0. Exit                                             |
+------------------------------------------------------+
"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def run_query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Execute a SELECT query and return all rows."""
    try:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()
    except sqlite3.OperationalError as exc:
        print(f"\n[DB ERROR] {exc}")
        return []


def print_rows(rows: list[sqlite3.Row], title: str = "") -> None:
    """Pretty-print query results using tabulate."""
    if not rows:
        print("\n  (no results)\n")
        return
    headers = list(rows[0].keys())
    data = [list(row) for row in rows]
    if title:
        print(f"\n{title}")
    print(tabulate(data, headers=headers, tablefmt=TABLE_FMT, floatfmt=FLOAT_FMT))
    print(f"  {len(rows)} row(s) returned.\n")


def ask_int(prompt: str, default: int) -> int:
    """Prompt for an integer with a fallback default."""
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"  Invalid number — using {default}")
        return default


def ask_str(prompt: str) -> str:
    return input(f"{prompt}: ").strip()


def available_years(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = run_query(conn, f"SELECT DISTINCT year FROM {table} ORDER BY year")
    return [r["year"] for r in rows]


def pick_year(conn: sqlite3.Connection, table: str) -> str:
    years = available_years(conn, table)
    if not years:
        return "current"
    print(f"  Available years: {', '.join(years)}")
    year = ask_str("  Enter year (or press Enter for 'current')")
    return year if year in years else "current"


# ---------------------------------------------------------------------------
# Menu handlers
# ---------------------------------------------------------------------------

def q1_top_cost_of_living(conn: sqlite3.Connection) -> None:
    """Top N cities by Cost of Living Index."""
    n = ask_int("  How many cities to show", 10)
    year = pick_year(conn, "cost_of_living")

    sql = """
        SELECT rank, city, country, cost_of_living_index, year
        FROM cost_of_living
        WHERE year = ?
        ORDER BY cost_of_living_index DESC
        LIMIT ?
    """
    rows = run_query(conn, sql, (year, n))
    print_rows(rows, f"Top {n} Cities by Cost of Living Index ({year})")


def q2_top_quality_of_life(conn: sqlite3.Connection) -> None:
    """Top N cities by Quality of Life Index."""
    n = ask_int("  How many cities to show", 10)
    year = pick_year(conn, "quality_of_life")

    sql = """
        SELECT rank, city, country, quality_of_life_index, year
        FROM quality_of_life
        WHERE year = ?
        ORDER BY quality_of_life_index DESC
        LIMIT ?
    """
    rows = run_query(conn, sql, (year, n))
    print_rows(rows, f"Top {n} Cities by Quality of Life Index ({year})")


def q3_crime_vs_qol(conn: sqlite3.Connection) -> None:
    """Cities ranked by Crime Index with their Quality of Life score (JOIN)."""
    n = ask_int("  How many cities to show", 15)

    # Use year that is common to both tables; default to 'current'
    crime_years = available_years(conn, "crime")
    qol_years   = available_years(conn, "quality_of_life")
    common = sorted(set(crime_years) & set(qol_years))
    if common:
        print(f"  Years with data in both tables: {', '.join(common)}")
    year = ask_str("  Enter year (or press Enter for 'current')") or "current"

    sql = """
        SELECT
            c.rank           AS crime_rank,
            c.city,
            c.country,
            c.crime_index,
            c.safety_index   AS crime_safety_index,
            q.quality_of_life_index,
            q.safety_index   AS qol_safety_index,
            c.year
        FROM crime c
        JOIN quality_of_life q
          ON TRIM(LOWER(c.city))    = TRIM(LOWER(q.city))
         AND TRIM(LOWER(c.country)) = TRIM(LOWER(q.country))
         AND c.year = q.year
        WHERE c.year = ?
        ORDER BY c.crime_index DESC
        LIMIT ?
    """
    rows = run_query(conn, sql, (year, n))
    print_rows(rows, f"Top {n} Cities by Crime Index with QoL Score ({year})")


def q4_col_vs_property(conn: sqlite3.Connection) -> None:
    """Cost of Living vs Property Prices for a chosen country (JOIN)."""
    country = ask_str("  Enter country name (e.g. United States)")
    year = pick_year(conn, "cost_of_living")

    sql = """
        SELECT
            col.city,
            col.country,
            col.cost_of_living_index,
            col.rent_index,
            pp.price_to_income_ratio,
            pp.mortgage_as_a_percentage_of_income,
            pp.affordability_index,
            col.year
        FROM cost_of_living col
        JOIN property_prices pp
          ON TRIM(LOWER(col.city))    = TRIM(LOWER(pp.city))
         AND TRIM(LOWER(col.country)) = TRIM(LOWER(pp.country))
         AND col.year = pp.year
        WHERE TRIM(LOWER(col.country)) = TRIM(LOWER(?))
          AND col.year = ?
        ORDER BY col.cost_of_living_index DESC
    """
    rows = run_query(conn, sql, (country, year))
    print_rows(rows, f"Cost of Living vs Property Prices — {country} ({year})")


def q5_city_trend(conn: sqlite3.Connection) -> None:
    """Year-over-year trend for a specific city."""
    city = ask_str("  Enter city name (e.g. New York, NY)")

    # Check across the index-rich table: quality_of_life
    sql = """
        SELECT year, city, country,
               quality_of_life_index,
               cost_of_living_index,
               safety_index,
               pollution_index
        FROM quality_of_life
        WHERE TRIM(LOWER(city)) LIKE TRIM(LOWER(?))
        ORDER BY year
    """
    rows = run_query(conn, sql, (f"%{city}%",))
    if rows:
        print_rows(rows, f"Quality of Life Trend for '{city}'")
    else:
        print(f"\n  No quality_of_life data found for '{city}'.\n")

    # Also show cost of living trend
    sql2 = """
        SELECT year, city, country,
               cost_of_living_index,
               rent_index,
               local_purchasing_power_index
        FROM cost_of_living
        WHERE TRIM(LOWER(city)) LIKE TRIM(LOWER(?))
        ORDER BY year
    """
    rows2 = run_query(conn, sql2, (f"%{city}%",))
    if rows2:
        print_rows(rows2, f"Cost of Living Trend for '{city}'")


def q6_countries_top20(conn: sqlite3.Connection) -> None:
    """Countries with the most cities in the top 20 for any index."""
    index_choices = {
        "1": ("cost_of_living",  "cost_of_living_index",  "Cost of Living"),
        "2": ("quality_of_life", "quality_of_life_index",  "Quality of Life"),
        "3": ("crime",           "crime_index",             "Crime"),
        "4": ("property_prices", "price_to_income_ratio",   "Price-to-Income Ratio"),
    }
    print("  Which index?")
    for k, (_, _, label) in index_choices.items():
        print(f"    {k}. {label}")
    choice = ask_str("  Enter number").strip()
    if choice not in index_choices:
        print("  Invalid choice.")
        return

    table, col, label = index_choices[choice]
    year = pick_year(conn, table)

    sql = f"""
        SELECT country, COUNT(*) AS cities_in_top20
        FROM (
            SELECT city, country
            FROM {table}
            WHERE year = ?
            ORDER BY {col} DESC
            LIMIT 20
        ) sub
        GROUP BY country
        ORDER BY cities_in_top20 DESC
    """
    rows = run_query(conn, sql, (year,))
    print_rows(rows, f"Countries with Most Cities in Top 20 — {label} Index ({year})")


def q7_custom_sql(conn: sqlite3.Connection) -> None:
    """Run a custom SQL query entered by the user."""
    print("  Available tables: cost_of_living, quality_of_life, crime, property_prices")
    print("  Type your SQL query below (end with a blank line or semicolon):\n")

    lines = []
    while True:
        line = input("  SQL> ")
        lines.append(line)
        if line.strip().endswith(";") or line.strip() == "":
            break

    sql = " ".join(lines).rstrip(";").strip()
    if not sql:
        print("  (empty query — skipping)")
        return

    rows = run_query(conn, sql)
    print_rows(rows, "Custom Query Results")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

HANDLERS = {
    "1": q1_top_cost_of_living,
    "2": q2_top_quality_of_life,
    "3": q3_crime_vs_qol,
    "4": q4_col_vs_property,
    "5": q5_city_trend,
    "6": q6_countries_top20,
    "7": q7_custom_sql,
}


def main():
    try:
        conn = get_connection()
    except sqlite3.OperationalError as exc:
        print(f"[ERROR] Could not open {DB_PATH}: {exc}")
        print("Did you run 2_import_db.py first?")
        sys.exit(1)

    print(MENU)

    while True:
        choice = input("Select option (0–7): ").strip()

        if choice == "0":
            print("Goodbye!")
            break
        elif choice in HANDLERS:
            try:
                HANDLERS[choice](conn)
            except KeyboardInterrupt:
                print("\n  (query cancelled)")
        else:
            print("  Invalid option — please enter 0–7.\n")

    conn.close()


if __name__ == "__main__":
    main()
