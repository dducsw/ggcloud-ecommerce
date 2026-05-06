{{ config(materialized='view') }}

with base as (
    select
        cast(id as int64) as product_id,
        cast(cost as numeric) as cost,
        cast(category as string) as category,
        coalesce(cast(name as string), 'Unknown Product') as product_name,
        cast(brand as string) as brand,
        cast(retail_price as numeric) as retail_price,
        cast(department as string) as department,
        cast(sku as string) as sku,
        cast(distribution_center_id as int64) as distribution_center_id,
        {{ to_cdc_timestamp('cdc_timestamp') }} as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from {{ source('thelook_ecommerce', 'products') }}
),
deduped as (
    select *,
        row_number() over (partition by product_id order by cdc_timestamp desc) as rn
    from base
)
select 
    *,
    timestamp_millis(cdc_timestamp) as source_updated_at
from deduped 
where rn = 1
and product_id is not null
