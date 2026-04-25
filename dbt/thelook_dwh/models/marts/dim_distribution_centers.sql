{{ config(materialized='table') }}

with valid_distribution_centers as (
    select
        {{ generate_surrogate_key(['distribution_center_id']) }} as dc_key,
        distribution_center_id,
        distribution_center_name,
        latitude,
        longitude
    from {{ ref('stg_distribution_centers') }}
)

select
    dc_key,
    distribution_center_id,
    distribution_center_name,
    latitude,
    longitude,
    cast(null as timestamp) as source_updated_at,
    current_timestamp() as dwh_updated_at
from valid_distribution_centers

union all

select
    {{ generate_surrogate_key(['-1']) }} as dc_key,
    -1 as distribution_center_id,
    'Unknown Distribution Center' as distribution_center_name,
    0.0 as latitude,
    0.0 as longitude,
    cast(null as timestamp) as source_updated_at,
    current_timestamp() as dwh_updated_at
from (select 1) as seed
where not exists (
    select 1
    from valid_distribution_centers
    where distribution_center_id = -1
)
