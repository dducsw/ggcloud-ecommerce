{{ config(materialized='view') }}

with orders_base as (
    select
        cast(order_id as int64) as order_id,
        cast(user_id as int64) as user_id,
        coalesce(cast(status as string), 'Unknown') as status,
        coalesce(cast(gender as string), 'Unknown') as gender,
        coalesce({{ to_bq_timestamp('created_at') }}, {{ to_bq_timestamp('cdc_timestamp') }}) as created_at,
        {{ to_bq_timestamp('shipped_at') }} as shipped_at,
        {{ to_bq_timestamp('delivered_at') }} as delivered_at,
        {{ to_bq_timestamp('returned_at') }} as returned_at,
        cast(num_of_item as int64) as num_of_item,
        -- CDC metadata: dùng để dedup và incremental
        cast(cdc_timestamp as int64) as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from {{ source('thelook_ecommerce', 'orders') }}
        where cast(order_id as int64) is not null
      and cast(user_id as int64) is not null
      and cast(num_of_item as int64) >= 0
      -- Bỏ qua hard delete CDC events
      and coalesce(cast(cdc_operation as string), 'c') != 'd'
),
latest_orders as (
    select
        *,
        row_number() over (
            partition by order_id
            -- Dùng cdc_timestamp: thời điểm CDC event, KHÔNG phải business created_at
            -- Đảm bảo chọn đúng version mới nhất khi có update (status, shipped_at...)
            order by cdc_timestamp desc
        ) as rn
    from orders_base
)
select
    order_id,
    user_id,
    status,
    gender,
    created_at,
    shipped_at,
    delivered_at,
    returned_at,
    num_of_item,
    cdc_timestamp,
    cdc_operation
from latest_orders
where rn = 1
