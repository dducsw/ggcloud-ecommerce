

with order_items_base as (
    select
        cast(id as int64) as order_item_id,
        cast(order_id as int64) as order_id,
        cast(user_id as int64) as user_id,
        cast(product_id as int64) as product_id,
        cast(inventory_item_id as int64) as inventory_item_id,
        coalesce(cast(status as string), 'Unknown') as status,
        cast(created_at as timestamp) as created_at,
        cast(shipped_at as timestamp) as shipped_at,
        cast(delivered_at as timestamp) as delivered_at,
        cast(returned_at as timestamp) as returned_at,
        cast(sale_price as numeric) as sale_price
    from `cloud-data-project-492514`.`thelook_staging`.`order_items`
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