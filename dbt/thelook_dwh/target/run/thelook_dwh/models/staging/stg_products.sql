

  create or replace view `cloud-data-project-492514`.`thelook_staging`.`stg_products`
  OPTIONS()
  as 

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
    timestamp_millis(cast(cdc_timestamp as int64)) as created_at
from `cloud-data-project-492514`.`thelook_staging`.`products`;

