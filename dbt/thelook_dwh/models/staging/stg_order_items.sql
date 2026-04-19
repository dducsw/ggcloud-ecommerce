{{ config(materialized='view') }}

with order_items_base as (
    select
        cast(id as int64) as order_item_id,
        cast(order_id as int64) as order_id,
        cast(user_id as int64) as user_id,
        cast(product_id as int64) as product_id,
        cast(inventory_item_id as int64) as inventory_item_id,
        coalesce(cast(status as string), 'Unknown') as status,
        {{ to_bq_timestamp('created_at') }} as created_at,
        {{ to_bq_timestamp('shipped_at') }} as shipped_at,
        {{ to_bq_timestamp('delivered_at') }} as delivered_at,
        {{ to_bq_timestamp('returned_at') }} as returned_at,
        cast(sale_price as numeric) as sale_price
    from {{ source('thelook_ecommerce', 'order_items') }}
    where cast(id as int64) is not null
      and cast(order_id as int64) is not null
      and cast(user_id as int64) is not null
      and cast(product_id as int64) is not null
      and cast(sale_price as numeric) >= 0
      -- If CDC operation column is available, exclude hard deletes here:
      -- and coalesce(cdc_op, 'c') != 'd'
),
latest_order_items as (
    select
        *,
        row_number() over (
            partition by order_item_id
            order by created_at desc
        ) as rn
    from order_items_base
)
select
    order_item_id,
    order_id,
    user_id,
    product_id,
    inventory_item_id,
    status,
    created_at,
    shipped_at,
    delivered_at,
    returned_at,
    sale_price
from latest_order_items
where rn = 1
