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
    case 
        when lower(trim(event_type)) = 'purchase' then true 
        else false 
    end as is_checkout_event,
    uri,
    created_at
from {{ ref('stg_events') }}
{% if is_incremental() %}
where created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from {{ this }}
)
{% endif %}
