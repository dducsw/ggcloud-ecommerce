

select
    cast(id as int64) as product_id,
    cast(cost as numeric) as cost,
    cast(category as string) as category,
    cast(name as string) as product_name,
    cast(brand as string) as brand,
    cast(retail_price as numeric) as retail_price,
    cast(department as string) as department,
    cast(sku as string) as sku,
    cast(distribution_center_id as int64) as distribution_center_id,
    cast(created_at as timestamp) as created_at
from `cloud-data-project-492514`.`thelook_staging`.`products`