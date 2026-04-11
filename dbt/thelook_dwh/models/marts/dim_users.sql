{{ config(materialized='table') }}

select
    user_id,
    first_name,
    last_name,
    email,
    age,
    gender,
    street_address,
    postal_code,
    city,
    state,
    country,
    latitude,
    longitude,
    traffic_source,
    created_at,
    updated_at
from {{ ref('stg_users') }}
