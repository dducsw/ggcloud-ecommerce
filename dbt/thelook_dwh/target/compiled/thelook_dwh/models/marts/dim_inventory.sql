

select
    inventory_item_id,
    product_id,
    cost,
    created_at,
    sold_at,
    case 
        when sold_at is not null then true 
        else false 
    end as is_sold,
    timestamp_diff(sold_at, created_at, DAY) as days_in_inventory,
    product_category,
    product_name,
    product_brand,
    product_retail_price,
    product_department,
    product_sku,
    product_distribution_center_id
from `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items`