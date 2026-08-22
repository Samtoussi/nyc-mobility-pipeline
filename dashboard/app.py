import time

import altair as alt
import boto3
import pandas as pd
import streamlit as st


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

AWS_REGION = "eu-north-1"
DATABASE = "nyc_mobility_gold"
ATHENA_OUTPUT = "s3://nyc-mobility-pipeline-samtoussi/athena-results/"


st.set_page_config(
    page_title="NYC Mobility Analytics",
    page_icon="🚕",
    layout="wide",
)


# -------------------------------------------------------------------
# Athena
# -------------------------------------------------------------------

@st.cache_data(ttl=3600)
def run_athena_query(query: str) -> pd.DataFrame:
    athena = boto3.client(
        "athena",
        region_name=AWS_REGION,
    )

    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            "Database": DATABASE,
        },
        ResultConfiguration={
            "OutputLocation": ATHENA_OUTPUT,
        },
    )

    query_execution_id = response["QueryExecutionId"]

    while True:
        execution = athena.get_query_execution(
            QueryExecutionId=query_execution_id
        )

        status = execution["QueryExecution"]["Status"]
        state = status["State"]

        if state == "SUCCEEDED":
            break

        if state in {"FAILED", "CANCELLED"}:
            reason = status.get(
                "StateChangeReason",
                "Unknown Athena error",
            )
            raise RuntimeError(reason)

        time.sleep(0.5)

    paginator = athena.get_paginator("get_query_results")

    pages = paginator.paginate(
        QueryExecutionId=query_execution_id
    )

    columns = None
    rows = []
    first_page = True

    for page in pages:
        if columns is None:
            columns = [
                column["Label"]
                for column in page[
                    "ResultSet"
                ]["ResultSetMetadata"]["ColumnInfo"]
            ]

        page_rows = page["ResultSet"]["Rows"]

        if first_page:
            page_rows = page_rows[1:]
            first_page = False

        for row in page_rows:
            values = [
                value.get("VarCharValue")
                for value in row["Data"]
            ]

            rows.append(values)

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# -------------------------------------------------------------------
# Load Gold data
# -------------------------------------------------------------------

try:
    yearly = run_athena_query(
        """
        SELECT
            year,
            total_trips,
            total_revenue,
            avg_revenue_per_trip,
            avg_trip_distance,
            avg_duration_min
        FROM yearly_mobility_summary
        ORDER BY year
        """
    )

    monthly = run_athena_query(
        """
        SELECT
            month_start,
            year,
            month,
            total_trips,
            total_revenue
        FROM monthly_mobility_trends
        ORDER BY month_start
        """
    )

    hourly = run_athena_query(
        """
        SELECT
            weekday,
            pickup_hour,
            total_trips
        FROM hourly_mobility_patterns
        ORDER BY weekday, pickup_hour
        """
    )

    pickup_zones = run_athena_query(
        """
        SELECT
            borough,
            zone,
            total_trips,
            total_revenue
        FROM pickup_location_performance
        ORDER BY total_trips DESC
        """
    )

    last_updated = run_athena_query(
        """
        SELECT
            MAX(trip_date) AS latest_trip_date
        FROM daily_mobility_metrics
        """
    )

except Exception as exc:
    st.error("Unable to load analytics data from Athena.")
    st.exception(exc)
    st.stop()


# -------------------------------------------------------------------
# Data types
# -------------------------------------------------------------------

yearly_numeric = [
    "year",
    "total_trips",
    "total_revenue",
    "avg_revenue_per_trip",
    "avg_trip_distance",
    "avg_duration_min",
]

for column in yearly_numeric:
    yearly[column] = pd.to_numeric(yearly[column])


monthly["month_start"] = pd.to_datetime(
    monthly["month_start"]
)

monthly["year"] = pd.to_numeric(
    monthly["year"]
)

monthly["month"] = pd.to_numeric(
    monthly["month"]
)

monthly["total_trips"] = pd.to_numeric(
    monthly["total_trips"]
)

monthly["total_revenue"] = pd.to_numeric(
    monthly["total_revenue"]
)


hourly["weekday"] = pd.to_numeric(
    hourly["weekday"]
)

hourly["pickup_hour"] = pd.to_numeric(
    hourly["pickup_hour"]
)

hourly["total_trips"] = pd.to_numeric(
    hourly["total_trips"]
)


pickup_zones["total_trips"] = pd.to_numeric(
    pickup_zones["total_trips"]
)

pickup_zones["total_revenue"] = pd.to_numeric(
    pickup_zones["total_revenue"]
)


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------

st.title("🚕 NYC Mobility Analytics")

st.caption(
    "Interactive NYC Yellow Taxi analytics powered by "
    "AWS S3, Glue, Athena, dbt and ECS Fargate."
)


# -------------------------------------------------------------------
# Year selection
# -------------------------------------------------------------------

years = sorted(
    yearly["year"].astype(int).tolist(),
    reverse=True,
)

selected_year = st.selectbox(
    "Year",
    years,
    index=0,
)

year_data = yearly[
    yearly["year"] == selected_year
].iloc[0]

year_monthly = monthly[
    monthly["year"] == selected_year
].copy()


# -------------------------------------------------------------------
# KPI row
# -------------------------------------------------------------------

st.subheader(f"{selected_year} Overview")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.metric(
        "Total Trips",
        f"{year_data['total_trips'] / 1_000_000:.1f}M",
    )

with kpi2:
    st.metric(
        "Total Revenue",
        f"${year_data['total_revenue'] / 1_000_000:.1f}M",
    )

with kpi3:
    st.metric(
        "Avg Revenue / Trip",
        f"${year_data['avg_revenue_per_trip']:.2f}",
    )

with kpi4:
    st.metric(
        "Avg Trip Distance",
        f"{year_data['avg_trip_distance']:.2f} mi",
    )

with kpi5:
    st.metric(
        "Avg Trip Duration",
        f"{year_data['avg_duration_min']:.1f} min",
    )


# -------------------------------------------------------------------
# Monthly trends
# -------------------------------------------------------------------

st.subheader("Monthly Trends")

metric_choice = st.radio(
    "Metric",
    ["Trips", "Revenue"],
    horizontal=True,
)

if metric_choice == "Trips":
    chart = (
        alt.Chart(year_monthly)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "month_start:T",
                title="Month",
            ),
            y=alt.Y(
                "total_trips:Q",
                title="Trips",
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip(
                    "month_start:T",
                    title="Month",
                    format="%B %Y",
                ),
                alt.Tooltip(
                    "total_trips:Q",
                    title="Trips",
                    format=",",
                ),
            ],
        )
        .properties(
            height=360,
        )
    )

else:
    chart = (
        alt.Chart(year_monthly)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "month_start:T",
                title="Month",
            ),
            y=alt.Y(
                "total_revenue:Q",
                title="Revenue ($)",
                scale=alt.Scale(zero=False),
            ),
            tooltip=[
                alt.Tooltip(
                    "month_start:T",
                    title="Month",
                    format="%B %Y",
                ),
                alt.Tooltip(
                    "total_revenue:Q",
                    title="Revenue",
                    format="$,.0f",
                ),
            ],
        )
        .properties(
            height=360,
        )
    )

st.altair_chart(
    chart,
    use_container_width=True,
)


# -------------------------------------------------------------------
# Pickup locations + boroughs
# -------------------------------------------------------------------

left, right = st.columns([2, 1])

with left:
    st.subheader("Top 10 Pickup Zones")

    top_zones = (
        pickup_zones
        .groupby(
            ["borough", "zone"],
            as_index=False,
        )
        .agg(
            total_trips=("total_trips", "sum"),
            total_revenue=("total_revenue", "sum"),
        )
        .nlargest(
            10,
            "total_trips",
        )
        .sort_values(
            "total_trips",
        )
    )

    zone_chart = (
        alt.Chart(top_zones)
        .mark_bar()
        .encode(
            x=alt.X(
                "total_trips:Q",
                title="Trips",
            ),
            y=alt.Y(
                "zone:N",
                title=None,
                sort=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "zone:N",
                    title="Zone",
                ),
                alt.Tooltip(
                    "borough:N",
                    title="Borough",
                ),
                alt.Tooltip(
                    "total_trips:Q",
                    title="Trips",
                    format=",",
                ),
                alt.Tooltip(
                    "total_revenue:Q",
                    title="Revenue",
                    format="$,.0f",
                ),
            ],
        )
        .properties(
            height=400,
        )
    )

    st.altair_chart(
        zone_chart,
        use_container_width=True,
    )


with right:
    st.subheader("Trips by Borough")

    boroughs = (
        pickup_zones
        .groupby(
            "borough",
            as_index=False,
        )["total_trips"]
        .sum()
        .sort_values(
            "total_trips",
            ascending=False,
        )
    )

    borough_chart = (
        alt.Chart(boroughs)
        .mark_arc(
            innerRadius=55,
        )
        .encode(
            theta=alt.Theta(
                "total_trips:Q",
            ),
            color=alt.Color(
                "borough:N",
                legend=alt.Legend(
                    title=None,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "borough:N",
                    title="Borough",
                ),
                alt.Tooltip(
                    "total_trips:Q",
                    title="Trips",
                    format=",",
                ),
            ],
        )
        .properties(
            height=400,
        )
    )

    st.altair_chart(
        borough_chart,
        use_container_width=True,
    )


# -------------------------------------------------------------------
# Weekday × hour heatmap
# -------------------------------------------------------------------

st.subheader("Trips by Weekday & Hour")

weekday_names = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

hourly["weekday_name"] = hourly["weekday"].map(
    weekday_names
)

weekday_order = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

heatmap = (
    alt.Chart(hourly)
    .mark_rect()
    .encode(
        x=alt.X(
            "pickup_hour:O",
            title="Pickup Hour",
        ),
        y=alt.Y(
            "weekday_name:N",
            title=None,
            sort=weekday_order,
        ),
        color=alt.Color(
            "total_trips:Q",
            title="Trips",
        ),
        tooltip=[
            alt.Tooltip(
                "weekday_name:N",
                title="Weekday",
            ),
            alt.Tooltip(
                "pickup_hour:O",
                title="Hour",
            ),
            alt.Tooltip(
                "total_trips:Q",
                title="Trips",
                format=",",
            ),
        ],
    )
    .properties(
        height=350,
    )
)

st.altair_chart(
    heatmap,
    use_container_width=True,
)


# -------------------------------------------------------------------
# Data information
# -------------------------------------------------------------------

st.divider()

latest_date = pd.to_datetime(
    last_updated.iloc[0]["latest_trip_date"]
)

info1, info2, info3 = st.columns(3)

with info1:
    st.caption(
        f"Latest trip data: {latest_date:%B %d, %Y}"
    )

with info2:
    st.caption(
        "Source: NYC Taxi & Limousine Commission"
    )

with info3:
    st.caption(
        "Analytics layer: dbt + Amazon Athena"
    )