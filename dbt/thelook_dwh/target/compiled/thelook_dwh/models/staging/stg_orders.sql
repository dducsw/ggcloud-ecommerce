

with orders_base as (
    select
        cast(coalesce(id, order_id) as int64) as order_id,
        cast(user_id as int64) as user_id,
        coalesce(cast(status as string), 'Unknown') as status,
        coalesce(cast(gender as string), 'Unknown') as gender,
        cast(created_at as timestamp) as created_at,
        cast(shipped_at as timestamp) as shipped_at,
        cast(delivered_at as timestamp) as delivered_at,
        cast(returned_at as timestamp) as returned_at,
        cast(num_of_item as int64) as num_of_item,
        -- CDC metadata: dùng để dedup và incremental
        cast(cdc_timestamp as int64) as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from `cloud-data-project-492514`.`thelook_staging`.`orders`
    where cast(coalesce(id, order_id) as int64) is not null
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