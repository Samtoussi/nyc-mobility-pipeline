{{ config(
    materialized='table'
) }}

with daily as (

    select
        trip_date,
        total_trips,
        total_revenue,
        avg_revenue_per_trip,
        avg_valid_trip_distance,
        avg_valid_duration_min

    from {{ ref('daily_mobility_metrics') }}

),

monthly as (

    select
        year(trip_date) as year,
        month(trip_date) as month,

        date_trunc(
            'month',
            trip_date
        ) as month_start,

        sum(total_trips) as total_trips,

        sum(total_revenue) as total_revenue,

        sum(total_revenue)
            / nullif(sum(total_trips), 0)
            as avg_revenue_per_trip,

        sum(
            avg_valid_trip_distance * total_trips
        )
            / nullif(sum(total_trips), 0)
            as avg_trip_distance,

        sum(
            avg_valid_duration_min * total_trips
        )
            / nullif(sum(total_trips), 0)
            as avg_duration_min

    from daily

    group by
        year(trip_date),
        month(trip_date),
        date_trunc(
            'month',
            trip_date
        )

)

select *
from monthly
order by month_start