"""
dashboard.py — Numbeo City Rankings Dashboard
================================================
Interactive Streamlit dashboard visualizing Numbeo city ranking data.

Tabs:
  1. Top Cities Bar Chart   — Horizontal bar chart, top N by selected index
  2. Cost vs Crime Quadrants  — Quadrant chart colored by Affordable/Expensive × Safe/Dangerous
  3. City Comparison        — Radar chart comparing QoL sub-indices across cities

Usage:
    streamlit run dashboard.py

Deployment:
    - Commit numbeo.db to GitHub (add data/ to .gitignore)
    - Deploy via Streamlit Community Cloud, set main file to dashboard.py
"""

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Numbeo City Rankings",
    # you can get emojis from https://emojipedia.org/
    page_icon="🌍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DB_PATH = "numbeo.db"


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    """Load a full table from numbeo.db into a DataFrame (cached)."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {name}", conn)  # noqa: S608 — table name is internal
    conn.close()
    return df


@st.cache_data
def load_all() -> dict[str, pd.DataFrame]:
    tables = ["cost_of_living", "quality_of_life", "crime", "property_prices"]
    return {t: load_table(t) for t in tables}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

st.title("🌍 Numbeo City Rankings Explorer")
st.caption(
    "Data sourced from [Numbeo.com](https://www.numbeo.com) — "
    "scraped for years 2023–current."
)

# Load data (show spinner on first load)
with st.spinner("Loading data from numbeo.db …"):
    data = load_all()

col = data["cost_of_living"]
qol = data["quality_of_life"]
crime = data["crime"]
prop = data["property_prices"]

# Gather common year options
all_years = sorted(
    set(col["year"].unique()) |
    set(qol["year"].unique()) |
    set(crime["year"].unique()) |
    set(prop["year"].unique())
)

all_countries = sorted(
    set(col["country"].dropna().unique()) |
    set(qol["country"].dropna().unique())
)
all_countries = [c for c in all_countries if c]  # drop empty strings

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Controls")

    # Year
    year = st.selectbox(
        "Year",
        options=all_years,
        index=all_years.index("current") if "current" in all_years else 0,
    )

    # Country filter
    selected_countries = st.multiselect(
        "Filter by Country",
        options=all_countries,
        default=[],
        placeholder="All countries",
    )

    # Top-N slider
    top_n = st.slider("Top N cities", min_value=5, max_value=50, value=20, step=5)

    # Index selector (Tab 1)
    st.subheader("Tab 1 — Index")
    index_options = {
        "Cost of Living":    ("cost_of_living",  "cost_of_living_index"),
        "Quality of Life":   ("quality_of_life", "quality_of_life_index"),
        "Crime":             ("crime",            "crime_index"),
        "Rent Index":        ("cost_of_living",   "rent_index"),
        "Safety":            ("crime",            "safety_index"),
    }
    selected_index_label = st.selectbox("Ranking index", list(index_options.keys()))
    idx_table, idx_col = index_options[selected_index_label]

    # Cities for radar (Tab 3)
    st.subheader("Tab 3 — Radar Chart")
    qol_year = qol[qol["year"] == year]
    if selected_countries:
        qol_year = qol_year[qol_year["country"].isin(selected_countries)]
    radar_city_options = sorted(qol_year["city"].dropna().unique().tolist())
    radar_cities = st.multiselect(
        "Cities to compare",
        options=radar_city_options,
        default=radar_city_options[:5] if len(radar_city_options) >= 5 else radar_city_options,
        max_selections=10,
    )

    # Label toggle (Tab 2)
    st.subheader("Tab 2 — Quadrant")
    show_labels = st.checkbox("Label outlier cities", value=True)


# ---------------------------------------------------------------------------
# Helper: filter by year and optional country list
# ---------------------------------------------------------------------------

def filter_df(df: pd.DataFrame, yr: str, countries: list[str]) -> pd.DataFrame:
    out = df[df["year"] == yr].copy()
    if countries:
        out = out[out["country"].isin(countries)]
    return out


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    # you can get emojis from https://emojipedia.org/
    "📊 Top Cities Bar Chart",
    "🔵 Cost vs Crime Quadrants",
    "🕸️ City Comparison Radar",
])

# ── Tab 1: Top N horizontal bar chart ────────────────────────────────────────

with tab1:
    st.subheader(f"Top {top_n} Cities — {selected_index_label} Index ({year})")

    df_idx = filter_df(data[idx_table], year, selected_countries)

    if df_idx.empty or idx_col not in df_idx.columns:
        st.warning(f"No data available for {selected_index_label} in {year}.")
    else:
        df_idx = df_idx.dropna(subset=[idx_col])
        df_top = df_idx.nlargest(top_n, idx_col).sort_values(idx_col)

        fig = px.bar(
            df_top,
            x=idx_col,
            y="city",
            color="country",
            orientation="h",
            title=f"Top {top_n} Cities by {selected_index_label} Index ({year})",
            labels={idx_col: selected_index_label, "city": "City"},
            hover_data=["country", "year"],
            height=max(400, top_n * 28),
            color_discrete_sequence=px.colors.qualitative.Plotly,
        )
        fig.update_layout(
            yaxis_title="",
            xaxis_title=selected_index_label,
            legend_title="Country",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("View data table"):
            st.dataframe(
                df_top[["city", "country", idx_col, "year"]],
                use_container_width=True,
            )

# ── Tab 2: Cost of Living vs Crime — Quadrant Chart ──────────────────────────

with tab2:
    st.subheader(f"Cost of Living vs Crime — Quadrant View ({year})")

    df_col2 = filter_df(col, year, selected_countries)[["city", "country", "cost_of_living_index", "year"]]
    df_crime2 = filter_df(crime, year, selected_countries)[["city", "country", "crime_index", "safety_index"]]

    merged = pd.merge(
        df_col2, df_crime2,
        on=["city", "country"],
        how="inner",
    ).dropna(subset=["cost_of_living_index", "crime_index"])

    if merged.empty:
        st.warning(
            "No overlapping city data for Cost of Living and Crime in the selected filters. "
            "Try removing country filters or selecting a different year."
        )
    else:
        med_col = merged["cost_of_living_index"].median()
        med_crime = merged["crime_index"].median()

        def _quadrant(row):
            hi_cost = row["cost_of_living_index"] >= med_col
            hi_crime = row["crime_index"] >= med_crime
            if hi_cost and hi_crime:
                return "Expensive & Dangerous"
            elif hi_cost:
                return "Expensive but Safe"
            elif hi_crime:
                return "Affordable but Dangerous"
            return "Affordable & Safe"

        merged["quadrant"] = merged.apply(_quadrant, axis=1)

        color_map = {
            "Expensive & Dangerous":    "#e74c3c",
            "Expensive but Safe":       "#3498db",
            "Affordable but Dangerous": "#e67e22",
            "Affordable & Safe":        "#2ecc71",
        }

        fig2 = px.scatter(
            merged,
            x="cost_of_living_index",
            y="crime_index",
            color="quadrant",
            color_discrete_map=color_map,
            hover_name="city",
            hover_data={"country": True, "safety_index": True, "quadrant": False},
            title=f"Cost of Living vs Crime Index ({year})",
            labels={
                "cost_of_living_index": "Cost of Living Index",
                "crime_index": "Crime Index",
                "quadrant": "",
            },
            height=550,
        )

        fig2.add_vline(
            x=med_col, line_dash="dash", line_color="gray", opacity=0.5,
            annotation_text=f"Median CoL {med_col:.0f}",
            annotation_position="top left",
            annotation_font_size=11,
        )
        fig2.add_hline(
            y=med_crime, line_dash="dash", line_color="gray", opacity=0.5,
            annotation_text=f"Median Crime {med_crime:.0f}",
            annotation_position="bottom right",
            annotation_font_size=11,
        )

        if show_labels:
            merged["_dist"] = (
                (merged["cost_of_living_index"] - med_col) ** 2
                + (merged["crime_index"] - med_crime) ** 2
            ) ** 0.5
            top_outliers = (
                merged.sort_values("_dist", ascending=False)
                .groupby("quadrant")
                .head(3)
            )
            for _, row in top_outliers.iterrows():
                fig2.add_annotation(
                    x=row["cost_of_living_index"],
                    y=row["crime_index"],
                    text=row["city"],
                    showarrow=True,
                    arrowhead=1,
                    arrowwidth=1,
                    arrowsize=0.7,
                    ax=18,
                    ay=-18,
                    font=dict(size=9),
                    bgcolor="rgba(255,255,255,0.7)",
                )

        fig2.update_traces(marker=dict(size=8, opacity=0.75))
        fig2.update_layout(
            legend_title="",
            margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)

        st.caption(
            f"{len(merged)} cities plotted. "
            "Dashed lines show median values — quadrants highlight cities that are "
            "above/below median cost of living and crime."
        )

        with st.expander("View data table"):
            st.dataframe(
                merged[["city", "country", "cost_of_living_index", "crime_index", "safety_index", "quadrant"]],
                use_container_width=True,
            )

# ── Tab 3: Radar chart — compare cities across QoL sub-indices ───────────────

with tab3:
    st.subheader(f"Quality of Life Sub-Index Comparison ({year})")

    QOL_SUBCOLS = [
        "purchasing_power_index",
        "safety_index",
        "health_care_index",
        "cost_of_living_index",
        "pollution_index",
        "climate_index",
        "traffic_commute_time_index",
    ]

    df_qol_yr = filter_df(qol, year, selected_countries)

    # Keep only sub-columns that actually exist in this year's data
    available_subcols = [c for c in QOL_SUBCOLS if c in df_qol_yr.columns]

    if not radar_cities:
        st.info("Select at least one city in the sidebar to display the radar chart.")
    elif not available_subcols:
        st.warning("Quality of Life sub-index columns not found in the data for this year.")
    else:
        df_radar = df_qol_yr[df_qol_yr["city"].isin(radar_cities)][["city"] + available_subcols].copy()
        df_radar = df_radar.dropna(subset=available_subcols, how="all")

        if df_radar.empty:
            st.warning("No data for the selected cities.")
        else:
            # Normalize to 0–100 range per column for visual comparability
            df_norm = df_radar.copy()
            for sc in available_subcols:
                col_min = df_qol_yr[sc].min()
                col_max = df_qol_yr[sc].max()
                rng = col_max - col_min
                if rng > 0:
                    df_norm[sc] = (df_norm[sc] - col_min) / rng * 100
                else:
                    df_norm[sc] = 50.0

            # Build Plotly radar figure
            fig3 = go.Figure()
            colors = px.colors.qualitative.Plotly

            # Friendly axis labels
            axis_labels = [c.replace("_index", "").replace("_", " ").title() for c in available_subcols]
            # Close the radar loop
            theta = axis_labels + [axis_labels[0]]

            for i, (_, row) in enumerate(df_norm.iterrows()):
                values = [row[sc] for sc in available_subcols]
                values_closed = values + [values[0]]
                fig3.add_trace(
                    go.Scatterpolar(
                        r=values_closed,
                        theta=theta,
                        fill="toself",
                        name=row["city"],
                        line_color=colors[i % len(colors)],
                        opacity=0.7,
                    )
                )

            fig3.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9))
                ),
                showlegend=True,
                legend_title="City",
                title=f"QoL Sub-Index Radar — Normalized 0–100 ({year})",
                height=600,
                margin=dict(l=50, r=50, t=60, b=50),
            )
            st.plotly_chart(fig3, use_container_width=True)
            st.caption(
                "Values normalized to 0–100 relative to the full dataset for the selected year. "
                "Higher = better for most indices (except Cost of Living, Pollution, Traffic)."
            )

            with st.expander("View raw sub-index values"):
                display_df = df_radar.set_index("city")
                display_df.columns = axis_labels
                st.dataframe(display_df.style.format("{:.1f}"), use_container_width=True)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Built with Streamlit · Data from Numbeo.com · "
    "Python Scraping Capstone Demo"
)
