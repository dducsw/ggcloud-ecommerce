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
    num_of_item,
    cdc_timestamp,
    cdc_operation
from {{ ref('stg_orders') }}
{% if is_incremental() %}
-- Dùng cdc_timestamp (được Beam gàn từ Debezium ts_ms) thay vì created_at.
-- Bắt được CDC update của orders cũ (status: processing→shipped→delivered)
-- khi created_at không thay đổi.
where cdc_timestamp >= (
    select coalesce(max(cdc_timestamp), 0)
    from {{ this }}
)
{% endif %}
