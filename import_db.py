"""
import_db.py — CSV to SQLite Importer
=======================================
Reads all CSV files from the data/ directory and imports them into
a single SQLite database (numbeo.db) with 4 tables.

Tables created:
  cost_of_living    — data/cost_of_living_*.csv
  quality_of_life   — data/quality_of_life_*.csv
  crime             — data/crime_*.csv
  property_prices   — data/property_prices_*.csv

Usage:
    python import_db.py
"""

import glob
import sqlite3
import sys
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = "numbeo.db"
DATA_DIR = "data"

# Maps table name using glob pattern matching for CSV files
# glob is the same kind of pattern matching the command line uses
TABLES = {
    "cost_of_living":  "cost_of_living",
    "quality_of_life": "quality_of_life",
    "crime":           "crime",
    "property_prices": "property_prices",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_csvs(dataset_key: str) -> pd.DataFrame | None:
    """
    Glob all CSV files for a dataset, load and concatenate them.
    Returns None if no matching files are found.
    """
    pattern = f"{DATA_DIR}/{dataset_key}_*.csv"
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"  [WARN] No CSV files found matching: {pattern}")
        return None

    frames = []
    for path in files:
        try:
            df = pd.read_csv(path, dtype=str)  # Load as strings first
            df["_source_file"] = path          # Track provenance temporarily
            frames.append(df)
            print(f"    Loaded {path:55s}  {len(df):>5} rows")
        except Exception as exc:
            print(f"    [ERROR] Could not load {path}: {exc}")

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined.drop(columns=["_source_file"], inplace=True)
    return combined


def coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """Convert every non-text column to numeric, coercing failures to NaN."""
    non_numeric = {"city", "country", "year"}
    for col in df.columns:
        if col in non_numeric:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def import_table(conn: sqlite3.Connection, table_name: str, dataset_key: str) -> bool:
    """Load, clean, and import a single table. Returns True on success."""
    print(f"\n--- {table_name} ---")

    df = load_csvs(dataset_key)
    if df is None or df.empty:
        print(f"  [SKIP] No data to import for {table_name}")
        return False

    df = coerce_numerics(df)

    # Ensure required text columns exist
    for col in ("city", "country", "year"):
        if col not in df.columns:
            df[col] = ""

    # Strip extra whitespace from text columns
    for col in ("city", "country", "year"):
        df[col] = df[col].astype(str).str.strip()

    # Write to SQLite
    df.to_sql(table_name, conn, if_exists="replace", index=False)

    # Verify
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cursor.fetchone()[0]
    print(f"  [OK]  {row_count} rows imported into '{table_name}'")
    print(f"        Columns: {list(df.columns)}")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Importing CSVs into {DB_PATH}...\n")

    conn = sqlite3.connect(DB_PATH)
    success_count = 0

    try:
        for table_name, dataset_key in TABLES.items():
            ok = import_table(conn, table_name, dataset_key)
            if ok:
                success_count += 1

        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"\n[FATAL] Unexpected error: {exc}")
        sys.exit(1)
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print(f"Import complete: {success_count}/{len(TABLES)} tables written to {DB_PATH}")

    if success_count == 0:
        print("\nNo data was imported. Did you run 1_scraper.py first?")
        sys.exit(1)

    # Summary query
    conn2 = sqlite3.connect(DB_PATH)
    print("\nRow counts per table:")
    for table_name in TABLES:
        try:
            (count,) = conn2.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            print(f"  {table_name:<25}  {count:>6} rows")
        except sqlite3.OperationalError:
            print(f"  {table_name:<25}  (not found)")
    conn2.close()


if __name__ == "__main__":
    main()
