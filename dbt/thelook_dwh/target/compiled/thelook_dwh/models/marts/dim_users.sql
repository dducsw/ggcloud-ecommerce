

with users_base as (
    select
        u.user_id,
        u.first_name,
        u.last_name,
        u.email,
        u.age,
        u.gender,
        u.street_address,
        u.postal_code,
        u.city,
        u.state,
        u.country,
        u.latitude,
        u.longitude,
        u.traffic_source,
        u.created_at,
        u.updated_at as source_updated_at
    from `cloud-data-project-492514`.`thelook_staging`.`stg_users` u
)

select
    to_hex(md5(concat('c0:', coalesce(cast(user_id as string), '__null__')))) as user_key,
    user_id,
    first_name,
    last_name,
    email,
    age,
    case
        when age is null then 'Unknown'
        when age < 18 then 'Under 18'
        when age < 60 then 'Adult'
        else 'Senior'
    end as age_group,
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
    source_updated_at,
    current_timestamp() as dwh_updated_at
from users_base

union all

-- Unknown member: FK fallback khi user không tìm thấy trong source
-- BigQuery yêu cầu FROM clause khi có WHERE clause
select
    to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__')))) as user_key,
    -1 as user_id,
    'Unknown' as first_name,
    'Unknown' as last_name,
    'unknown@example.com' as email,
    null as age,
    'Unknown' as age_group,
    'Unknown' as gender,
    'Unknown' as street_address,
    'N/A' as postal_code,
    'Unknown' as city,
    'Unknown' as state,
    'Unknown' as country,
    0.0 as latitude,
    0.0 as longitude,
    'Unknown' as traffic_source,
    timestamp('1970-01-01') as created_at,
    timestamp('1970-01-01') as source_updated_at,
    current_timestamp() as dwh_updated_at
from (select 1) as _sentinel
where not exists (
    select 1
    from users_base
    where user_id = -1
)