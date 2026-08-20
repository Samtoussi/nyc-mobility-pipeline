{{ config(
    materialized='table'
) }}

with valid_trips as (

    select
        cast(tpep_pickup_datetime as date) as trip_date,
        tpep_pickup_datetime,
        trip_distance,
        total_amount,
        duration_min

    from nyc_mobility.yellow_tripdata

    where date_quality = 'VALID'
      and duration_quality = 'VALID'
      and distance_quality = 'VALID'

)

select
    trip_date,
    day_of_week(tpep_pickup_datetime) as weekday,
    hour(tpep_pickup_datetime) as pickup_hour,

    count(*) as total_trips,
    avg(trip_distance) as avg_trip_distance,
    avg(duration_min) as avg_duration_min,
    avg(total_amount) as avg_revenue_per_trip

from valid_trips

group by
    trip_date,
    day_of_week(tpep_pickup_datetime),
    hour(tpep_pickup_datetime)