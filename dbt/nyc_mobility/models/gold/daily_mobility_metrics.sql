{{ config(
    materialized='table'
) }}

with silver as (

    select
        cast(tpep_pickup_datetime as date) as trip_date,
        trip_distance,
        duration_min,
        total_amount,
        duration_quality,
        distance_quality,
        financial_quality,
        date_quality
    from nyc_mobility.yellow_tripdata
    where date_quality = 'VALID'

),

daily as (

    select
        trip_date,

        count(*) as total_trips,

        sum(total_amount) as total_revenue,

        avg(total_amount) as avg_revenue_per_trip,

        avg(
            case
                when distance_quality = 'VALID'
                then trip_distance
            end
        ) as avg_valid_trip_distance,

        avg(
            case
                when duration_quality = 'VALID'
                then duration_min
            end
        ) as avg_valid_duration_min,

        sum(
            case
                when distance_quality = 'SUSPICIOUS_EXTREME'
                then 1
                else 0
            end
        ) as suspicious_distance_trips,

        sum(
            case
                when duration_quality != 'VALID'
                then 1
                else 0
            end
        ) as non_valid_duration_trips,

        sum(
            case
                when financial_quality != 'STANDARD'
                then 1
                else 0
            end
        ) as non_standard_financial_trips

    from silver
    group by trip_date

)

select *
from daily