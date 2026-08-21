{{ config(
    materialized='table'
) }}

with monthly as (

    select
        year,
        total_trips,
        total_revenue,
        avg_revenue_per_trip,
        avg_trip_distance,
        avg_duration_min

    from {{ ref('monthly_mobility_trends') }}

),

yearly as (

    select
        year,

        sum(total_trips) as total_trips,

        sum(total_revenue) as total_revenue,

        sum(total_revenue)
            / nullif(sum(total_trips), 0)
            as avg_revenue_per_trip,

        sum(
            avg_trip_distance * total_trips
        )
            / nullif(sum(total_trips), 0)
            as avg_trip_distance,

        sum(
            avg_duration_min * total_trips
        )
            / nullif(sum(total_trips), 0)
            as avg_duration_min

    from monthly

    group by year

)

select *
from yearly
order by year