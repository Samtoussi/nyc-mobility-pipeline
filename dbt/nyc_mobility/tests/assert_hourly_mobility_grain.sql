select
    trip_date,
    weekday,
    pickup_hour,
    count(*) as row_count

from {{ ref('hourly_mobility_patterns') }}

group by
    trip_date,
    weekday,
    pickup_hour

having count(*) > 1