{{ config(materialized='view') }}

with events_base as (
    select
        -- BQ streaming table dùng 'id', không có 'event_id'
        cast(id as int64) as event_id,
        cast(user_id as int64) as user_id,
        cast(sequence_number as int64) as sequence_number,
        coalesce(cast(session_id as string), 'N/A') as session_id,
        coalesce(cast(ip_address as string), 'N/A') as ip_address,
        coalesce(cast(city as string), 'Unknown') as city,
        coalesce(cast(state as string), 'Unknown') as state,
        coalesce(cast(postal_code as string), 'N/A') as postal_code,
        coalesce(cast(browser as string), 'Unknown') as browser,
        coalesce(cast(traffic_source as string), 'Unknown') as traffic_source,
        coalesce(cast(uri as string), 'N/A') as uri,
        coalesce(cast(event_type as string), 'Unknown') as event_type,
        coalesce({{ to_bq_timestamp('created_at') }}, timestamp_millis({{ to_cdc_timestamp('cdc_timestamp') }})) as created_at,
        -- CDC metadata
        {{ to_cdc_timestamp('cdc_timestamp') }} as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from {{ source('thelook_ecommerce', 'events') }}
    where cast(id as int64) is not null
      and cast(user_id as int64) is not null
      and cast(sequence_number as int64) >= 0
      and coalesce(cast(cdc_operation as string), 'c') != 'd'
),
latest_events as (
    select
        *,
        row_number() over (
            partition by event_id
            -- Dùng cdc_timestamp để dedup đúng version mới nhất
            order by cdc_timestamp desc
        ) as rn
    from events_base
)
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
    created_at,
    cdc_timestamp,
    cdc_operation
from latest_events
where rn = 1
