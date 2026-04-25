{{
  config(
    materialized='incremental',
    unique_key='event_id',
    partition_by={
      'field': 'created_at',
      'data_type': 'timestamp'
    }
  )
}}

with events_base as (
    select
        e.event_id,
        coalesce(u.user_key, {{ generate_surrogate_key(['-1']) }}) as user_key,
        e.user_id,
        e.sequence_number,
        e.session_id,
        cast(format_date('%Y%m%d', date(e.created_at)) as int64) as created_date_key,
        e.ip_address,
        e.city,
        e.state,
        e.postal_code,
        e.browser,
        e.traffic_source,
        e.event_type,
        case 
            when lower(trim(e.event_type)) = 'purchase' then true 
            else false 
        end as is_checkout_event,
        e.uri,
        e.created_at as source_updated_at,
        current_timestamp() as dwh_updated_at,
        e.created_at
    from {{ ref('stg_events') }} e
    left join {{ ref('dim_users') }} u
      on e.user_id = u.user_id
)

select *
from events_base
{% if is_incremental() %}
where created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from {{ this }}
)
{% endif %}
