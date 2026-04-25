-- Test: Ensure no negative prices exist in order items and products
-- This test will fail (return rows) if any negative prices are found

select 
    'order_items' as source_table,
    order_item_id as record_id,
    sale_price as price_value
from {{ ref('stg_order_items') }}
where sale_price < 0

union all

select 
    'products' as source_table,
    product_id as record_id,
    cost as price_value
from {{ ref('stg_products') }}
where cost < 0

union all

select 
    'products' as source_table,
    product_id as record_id,
    retail_price as price_value
from {{ ref('stg_products') }}
where retail_price < 0
