

  create or replace view `cloud-data-project-492514`.`thelook_staging`.`stg_order_items`
  OPTIONS()
  as 

with order_items_base as (
    select
        cast(id as int64) as order_item_id,
        cast(order_id as int64) as order_id,
        cast(user_id as int64) as user_id,
        cast(product_id as int64) as product_id,
        cast(inventory_item_id as int64) as inventory_item_id,
        coalesce(cast(status as string), 'Unknown') as status,
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
        cast(sale_price as numeric) as sale_price,
        cast(cdc_timestamp as int64) as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from `cloud-data-project-492514`.`thelook_staging`.`order_items`
    where cast(id as int64) is not null
      and cast(order_id as int64) is not null
      and cast(user_id as int64) is not null
      and cast(product_id as int64) is not null
      and cast(sale_price as numeric) >= 0
      and case
    when created_at is null then null
    when regexp_contains(cast(created_at as string), r'^\d+$') then
        case
            when length(cast(created_at as string)) >= 16 then timestamp_micros(cast(created_at as int64))
            when length(cast(created_at as string)) >= 13 then timestamp_millis(cast(created_at as int64))
            else timestamp_seconds(cast(created_at as int64))
        end
    else safe_cast(cast(created_at as string) as timestamp)
end is not null
      and coalesce(cast(cdc_operation as string), 'c') != 'd'
),
latest_order_items as (
    select
        *,
        row_number() over (
            partition by order_item_id
            order by cdc_timestamp desc, created_at desc
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
    sale_price,
    cdc_timestamp,
    cdc_operation
from latest_order_items
where rn = 1;

