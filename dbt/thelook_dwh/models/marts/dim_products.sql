{{ config(materialized='table') }}

with valid_products as (
    select
        product_id,
        product_name,
        category,
        brand,
        department,
        sku,
        retail_price,
        distribution_center_id,
        created_at
    from {{ ref('stg_products') }}
)

select
    product_id,
    product_name,
    category,
    brand,
    department,
    sku,
    retail_price,
    distribution_center_id,
    created_at
from valid_products

union all

select
    -1 as product_id,
    'Unknown Product' as product_name,
    'Unknown' as category,
    'Unknown' as brand,
    'Unknown' as department,
    'N/A' as sku,
    0 as retail_price,
    -1 as distribution_center_id,
    timestamp('1970-01-01') as created_at
where not exists (
    select 1
    from valid_products
    where product_id = -1
)
