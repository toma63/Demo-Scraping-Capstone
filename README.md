# Numbeo Web Scraping Capstone

A 4-program Python demo project showing end-to-end web scraping, database import,
querying, and dashboard visualization using data from [Numbeo.com](https://www.numbeo.com).

## Datasets

| Dataset | Table |
|---|---|
| Cost of Living | `cost_of_living` |
| Quality of Life | `quality_of_life` |
| Crime | `crime` |
| Property Prices | `property_prices` |

Years covered: **current, 2023, 2024, 2025**

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Programs

### 1. Scraper — `scraper.py`
Scrapes Numbeo city rankings using Selenium (headless Chrome) and saves CSV files
to the `data/` directory.

```bash
python scraper.py
```

**Output:** `data/<dataset>_<year>.csv` — up to 16 CSV files.

---

### 2. Database Importer — `import_db.py`
Loads all CSVs from `data/` into a SQLite database (`numbeo.db`).

```bash
python import_db.py
```

**Output:** `numbeo.db` with 4 tables.

---

### 3. Query Tool — `query_db.py`
Interactive CLI menu for querying `numbeo.db`.

```bash
python query_db.py
```

**Menu options:**
1. Top N cities by Cost of Living Index
2. Top N cities by Quality of Life Index
3. Crime vs Quality of Life *(JOIN)*
4. Cost of Living vs Property Prices by country *(JOIN)*
5. Year-over-year trend for a city
6. Countries with most cities in top 20
7. Custom SQL query
0. Exit

---

### 4. Dashboard — `4_dashboard.py`
Streamlit dashboard with interactive Plotly charts.

```bash
streamlit run 4_dashboard.py
```

**Tabs:**
- **Top Cities Bar Chart** — Horizontal bar chart, Top N cities by chosen index
- **Cost of Living vs Crime** — Scatter plot with optional OLS trendline
- **City Comparison Radar** — Radar chart comparing QoL sub-indices across cities

---

## Streamlit Community Cloud Deployment

1. Commit `numbeo.db` to your GitHub repository (the `data/` folder is gitignored).
2. Push the repository to GitHub.
3. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo.
4. Set the main file path to `4_dashboard.py`.
5. Deploy — no secrets are required.

---

## Project Structure

```
scraping_capstone/
├── scraper.py          # Selenium scraper → CSV files
├── import_db.py        # CSV files → SQLite database
├── query_db.py         # CLI menu query tool
├── dashboard.py        # Streamlit dashboard
├── numbeo.db             # SQLite database (committed to repo)
├── requirements.txt
├── .gitignore            # Excludes data/ CSVs
└── README.md
```
