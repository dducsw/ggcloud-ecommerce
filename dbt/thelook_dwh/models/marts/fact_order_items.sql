{{
  config(
    materialized='incremental',
    unique_key='order_item_id',
    incremental_strategy='merge',
    partition_by={
      'field': 'created_at',
      'data_type': 'timestamp'
    }
  )
}}

with order_items_deduped as (
    -- Dedup để MERGE không gặp lỗi nhiều source row cho 1 unique key
    select *
    from (
        select
            *,
            row_number() over (partition by order_item_id order by cdc_timestamp desc) as rn
        from {{ ref('stg_order_items') }}
    )
    where rn = 1
),

inventory_deduped as (
    select *
    from (
        select
            *,
            row_number() over (partition by inventory_item_id order by cdc_timestamp desc) as rn
        from {{ ref('stg_inventory_items') }}
    )
    where rn = 1
),

order_items_enriched as (
    select
        oi.order_item_id,
        oi.order_id,
        coalesce(u.user_key, {{ generate_surrogate_key(['-1']) }}) as user_key,
        oi.user_id,
        coalesce(p.product_key, {{ generate_surrogate_key(['-1']) }}) as product_key,
        oi.product_id,
        coalesce(oi.inventory_item_id, -1) as inventory_item_id,
        coalesce(dc.dc_key, {{ generate_surrogate_key(['-1']) }}) as dc_key,
        cast(format_date('%Y%m%d', date(oi.created_at)) as int64) as created_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.shipped_at)) as int64), 0) as shipped_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.delivered_at)) as int64), 0) as delivered_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.returned_at)) as int64), 0) as returned_date_key,
        oi.status,
        case 
            when oi.status in ('Returned', 'Cancelled') then true 
            else false 
        end as is_returned,
        oi.created_at,
        oi.shipped_at,
        oi.delivered_at,
        oi.returned_at,
        oi.sale_price,
        coalesce(inv.cost, p.cost, 0) as cost,
        oi.sale_price - coalesce(inv.cost, p.cost, 0) as profit,
        coalesce(oi.returned_at, oi.delivered_at, oi.shipped_at, oi.created_at) as source_updated_at,
        current_timestamp() as dwh_updated_at,
        case 
            when coalesce(oi.sale_price, 0) = 0 then 0.0 
            else (oi.sale_price - coalesce(inv.cost, p.cost, 0)) / oi.sale_price 
        end as margin_percentage
    from order_items_deduped oi
    left join inventory_deduped inv
      on oi.inventory_item_id = inv.inventory_item_id
    left join {{ ref('dim_users') }} u
      on oi.user_id = u.user_id
    left join {{ ref('dim_products') }} p
      on oi.product_id = p.product_id
    left join {{ ref('dim_distribution_centers') }} dc
      on inv.product_distribution_center_id = dc.distribution_center_id
)

select *
from order_items_enriched
{% if is_incremental() %}
where source_updated_at >= (
    select timestamp_sub(
        coalesce(max(source_updated_at), timestamp('1970-01-01')),
        interval 3 day
    )
    from {{ this }}
)
{% endif %}
