select
    weekday,
    pickup_hour,
    count(*) as row_count

from {{ ref('hourly_mobility_patterns') }}

group by
    weekday,
    pickup_hour

having count(*) > 1