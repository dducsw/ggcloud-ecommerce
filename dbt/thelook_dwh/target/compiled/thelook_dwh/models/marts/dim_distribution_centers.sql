

with valid_distribution_centers as (
    select
        to_hex(md5(concat('c0:', coalesce(cast(distribution_center_id as string), '__null__')))) as dc_key,
        distribution_center_id,
        distribution_center_name,
        latitude,
        longitude
    from `cloud-data-project-492514`.`thelook_staging`.`stg_distribution_centers`
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
    to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__')))) as dc_key,
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