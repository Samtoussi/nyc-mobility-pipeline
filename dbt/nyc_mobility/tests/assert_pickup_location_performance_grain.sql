select
    trip_date,
    pickup_location_id,
    count(*) as row_count

from {{ ref('pickup_location_performance') }}

group by
    trip_date,
    pickup_location_id

having count(*) > 1