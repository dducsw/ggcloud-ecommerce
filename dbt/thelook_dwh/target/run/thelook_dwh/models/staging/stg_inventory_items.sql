

  create or replace view `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items`
  OPTIONS()
  as 

select
    cast(id as int64) as inventory_item_id,
    cast(product_id as int64) as product_id,
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
    when sold_at is null then null
    when regexp_contains(cast(sold_at as string), r'^\d+$') then
        case
            when length(cast(sold_at as string)) >= 16 then timestamp_micros(cast(sold_at as int64))
            when length(cast(sold_at as string)) >= 13 then timestamp_millis(cast(sold_at as int64))
            else timestamp_seconds(cast(sold_at as int64))
        end
    else safe_cast(cast(sold_at as string) as timestamp)
end as sold_at,
    cast(cost as numeric) as cost,
    cast(product_category as string) as product_category,
    cast(product_name as string) as product_name,
    cast(product_brand as string) as product_brand,
    cast(product_retail_price as numeric) as product_retail_price,
    cast(product_department as string) as product_department,
    cast(product_sku as string) as product_sku,
    cast(product_distribution_center_id as int64) as product_distribution_center_id
from `cloud-data-project-492514`.`thelook_staging`.`inventory_items`;

