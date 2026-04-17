

select
    event_id,
    user_id,
    sequence_number,
    session_id,
    ip_address,
    city,
    state,
    postal_code,
    browser,
    traffic_source,
    event_type,
    uri,
    created_at
from `cloud-data-project-492514`.`thelook_staging_thelook_staging`.`stg_events`

where created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from `cloud-data-project-492514`.`thelook_staging_thelook_datawarehouse`.`fact_events`
)
