{{ config(materialized='view') }}

select
    cast(id as int64) as inventory_item_id,
    cast(product_id as int64) as product_id,
    {{ to_bq_timestamp('created_at') }} as created_at,
    {{ to_bq_timestamp('sold_at') }} as sold_at,
    cast(cost as numeric) as cost,
    cast(product_category as string) as product_category,
    cast(product_name as string) as product_name,
    cast(product_brand as string) as product_brand,
    cast(product_retail_price as numeric) as product_retail_price,
    cast(product_department as string) as product_department,
    cast(product_sku as string) as product_sku,
    cast(product_distribution_center_id as int64) as product_distribution_center_id
from {{ source('thelook_ecommerce', 'inventory_items') }}
