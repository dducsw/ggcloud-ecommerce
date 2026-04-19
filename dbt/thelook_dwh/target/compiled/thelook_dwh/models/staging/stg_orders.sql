

with orders_base as (
    select
        cast(order_id as int64) as order_id,
        cast(user_id as int64) as user_id,
        coalesce(cast(status as string), 'Unknown') as status,
        coalesce(cast(gender as string), 'Unknown') as gender,
        case
    when created_at is null then null
    when regexp_contains(cast(created_at as string), r'^\d+$') then
        case
            when length(cast(created_at as string)) >= 16 then timestamp_micros(cast(created_at as int64))
            when length(cast(created_at as string)) >= 13 then timestamp_millis(cast(created_at as int64))
            else timestamp_seconds(cast(created_at as int64))
        end
    else safe_cast(cast(created_at as string) as timestamp)
end as created_at,
        case
    when shipped_at is null then null
    when regexp_contains(cast(shipped_at as string), r'^\d+$') then
        case
            when length(cast(shipped_at as string)) >= 16 then timestamp_micros(cast(shipped_at as int64))
            when length(cast(shipped_at as string)) >= 13 then timestamp_millis(cast(shipped_at as int64))
            else timestamp_seconds(cast(shipped_at as int64))
        end
    else safe_cast(cast(shipped_at as string) as timestamp)
end as shipped_at,
        case
    when delivered_at is null then null
    when regexp_contains(cast(delivered_at as string), r'^\d+$') then
        case
            when length(cast(delivered_at as string)) >= 16 then timestamp_micros(cast(delivered_at as int64))
            when length(cast(delivered_at as string)) >= 13 then timestamp_millis(cast(delivered_at as int64))
            else timestamp_seconds(cast(delivered_at as int64))
        end
    else safe_cast(cast(delivered_at as string) as timestamp)
end as delivered_at,
        case
    when returned_at is null then null
    when regexp_contains(cast(returned_at as string), r'^\d+$') then
        case
            when length(cast(returned_at as string)) >= 16 then timestamp_micros(cast(returned_at as int64))
            when length(cast(returned_at as string)) >= 13 then timestamp_millis(cast(returned_at as int64))
            else timestamp_seconds(cast(returned_at as int64))
        end
    else safe_cast(cast(returned_at as string) as timestamp)
end as returned_at,
        cast(num_of_item as int64) as num_of_item,
        -- CDC metadata: dùng để dedup và incremental
        cast(cdc_timestamp as int64) as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from `cloud-data-project-492514`.`thelook_staging`.`orders`
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