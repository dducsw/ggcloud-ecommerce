{{
  config(
    materialized='incremental',
    unique_key='order_id',
    partition_by={
      'field': 'created_at',
      'data_type': 'timestamp'
    }
  )
}}

select
    order_id,
    user_id,
    status,
    created_at,
    shipped_at,
    delivered_at,
    returned_at,
    num_of_item
from {{ ref('stg_orders') }}
{% if is_incremental() %}
where created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from {{ this }}
)
{% endif %}
