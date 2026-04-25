
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_products`
      
    
    

    
    OPTIONS()
    as (
      

with valid_products as (
    select
        to_hex(md5(concat('c0:', coalesce(cast(product_id as string), '__null__')))) as product_key,
        product_id,
        product_name,
        category,
        brand,
        department,
        sku,
        retail_price,
        cost,
        retail_price - cost as margin_value,
        distribution_center_id,
        source_updated_at
    from `cloud-data-project-492514`.`thelook_staging`.`stg_products`
)

select
    product_key,
    product_id,
    product_name,
    category,
    brand,
    department,
    sku,
    retail_price,
    cost,
    margin_value,
    distribution_center_id,
    source_updated_at,
    current_timestamp() as dwh_updated_at
from valid_products

union all

select
    to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__')))) as product_key,
    -1 as product_id,
    'Unknown Product' as product_name,
    'Unknown' as category,
    'Unknown' as brand,
    'Unknown' as department,
    'N/A' as sku,
    0 as retail_price,
    0 as cost,
    0 as margin_value,
    -1 as distribution_center_id,
    timestamp('1970-01-01') as source_updated_at,
    current_timestamp() as dwh_updated_at
from (select 1) as seed
where not exists (
    select 1
    from valid_products
    where product_id = -1
)
    );
  