{{ config(materialized='view') }}

with base as (
    select
        cast(id as int64) as distribution_center_id,
        cast(name as string) as distribution_center_name,
        cast(latitude as float64) as latitude,
        cast(longitude as float64) as longitude,
        {{ to_cdc_timestamp('cdc_timestamp') }} as cdc_timestamp,
        cast(cdc_operation as string) as cdc_operation
    from {{ source('thelook_ecommerce', 'distribution_centers') }}
),
deduped as (
    select *,
        row_number() over (partition by distribution_center_id order by cdc_timestamp desc) as rn
    from base
)
select * except(rn) from deduped where rn = 1
