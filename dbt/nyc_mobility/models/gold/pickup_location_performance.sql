{{ config(
    materialized='table'
) }}

with valid_trips as (

    select
        cast(tpep_pickup_datetime as date) as trip_date,
        PULocationID,
        trip_distance,
        duration_min,
        total_amount

    from nyc_mobility.yellow_tripdata

    where date_quality = 'VALID'
      and duration_quality = 'VALID'
      and distance_quality = 'VALID'

),

location_metrics as (

    select
        trip_date,
        PULocationID as pickup_location_id,

        count(*) as total_trips,
        sum(total_amount) as total_revenue,
        avg(total_amount) as avg_revenue_per_trip,
        avg(trip_distance) as avg_trip_distance,
        avg(duration_min) as avg_duration_min

    from valid_trips

    group by
        trip_date,
        PULocationID

)

select
    m.trip_date,
    m.pickup_location_id,
    z.Borough as borough,
    z.Zone as zone,
    z.service_zone,

    m.total_trips,
    m.total_revenue,
    m.avg_revenue_per_trip,
    m.avg_trip_distance,
    m.avg_duration_min

from location_metrics m

left join {{ ref('taxi_zone_lookup') }} z
    on m.pickup_location_id = z.LocationID