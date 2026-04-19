{{ config(materialized='view') }}

select
    cast(id as int64) as user_id,
    cast(first_name as string) as first_name,
    cast(last_name as string) as last_name,
    cast(email as string) as email,
    cast(age as int64) as age,
    cast(gender as string) as gender,
    cast(street_address as string) as street_address,
    cast(postal_code as string) as postal_code,
    cast(city as string) as city,
    cast(state as string) as state,
    cast(country as string) as country,
    cast(latitude as float64) as latitude,
    cast(longitude as float64) as longitude,
    cast(traffic_source as string) as traffic_source,
    {{ to_bq_timestamp('created_at') }} as created_at,
    {{ to_bq_timestamp('updated_at') }} as updated_at
from {{ source('thelook_ecommerce', 'users') }}
