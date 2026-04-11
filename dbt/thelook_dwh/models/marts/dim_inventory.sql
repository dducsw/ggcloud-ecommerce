{{ config(materialized='table') }}

select
    inventory_item_id,
    product_id,
    cost,
    created_at,
    sold_at,
    product_category,
    product_name,
    product_brand,
    product_retail_price,
    product_department,
    product_sku,
    product_distribution_center_id
from {{ ref('stg_inventory_items') }}
