{{
  config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='merge',
    partition_by={
      'field': 'created_at',
      'data_type': 'timestamp'
    }
  )
}}

with 
{% if is_incremental() %}
    -- Tìm tất cả các order_id bị ảnh hưởng từ 2 phía để đảm bảo không miss data khi order_item update
    impacted_orders as (
        select order_id 
        from {{ ref('stg_orders') }}
        where cdc_timestamp >= (select coalesce(max(cdc_timestamp), 0) from {{ this }})
        
        union distinct
        
        select order_id 
        from {{ ref('fact_order_items') }}
        -- Lookback 1 day to catch any late arriving/updated items relative to the target table
        where created_at >= (select timestamp_sub(coalesce(max(created_at), timestamp('1970-01-01')), interval 1 day) from {{ this }})
    ),
{% endif %}

order_stats as (
    select
        order_id,
        sum(sale_price) as total_revenue,
        sum(cost) as total_cost,
        sum(profit) as gross_margin
    from {{ ref('fact_order_items') }}
    {% if is_incremental() %}
    -- Lọc chỉ xử lý aggregation cho các đơn hàng bị ảnh hưởng để tối ưu performance mảng tính sum
    where order_id in (select order_id from impacted_orders)
    {% endif %}
    group by order_id
),

orders_base as (
    select
        o.order_id,
        coalesce(u.user_key, {{ generate_surrogate_key(['-1']) }}) as user_key,
        o.user_id,
        o.status,
        cast(format_date('%Y%m%d', date(o.created_at)) as int64) as created_date_key,
        coalesce(cast(format_date('%Y%m%d', date(o.shipped_at)) as int64), 0) as shipped_date_key,
        coalesce(cast(format_date('%Y%m%d', date(o.delivered_at)) as int64), 0) as delivered_date_key,
        coalesce(cast(format_date('%Y%m%d', date(o.returned_at)) as int64), 0) as returned_date_key,
        o.created_at,
        o.shipped_at,
        o.delivered_at,
        o.returned_at,
        o.num_of_item,
        coalesce(o.returned_at, o.delivered_at, o.shipped_at, o.created_at) as source_updated_at,
        o.cdc_timestamp,
        o.cdc_operation
    from {{ ref('stg_orders') }} o
    left join {{ ref('dim_users') }} u
      on o.user_id = u.user_id
    {% if is_incremental() %}
    inner join impacted_orders io on o.order_id = io.order_id
    {% endif %}
),

orders_with_stats as (
    select
        o.order_id,
        o.user_key,
        o.user_id,
        o.status,
        o.created_date_key,
        o.shipped_date_key,
        o.delivered_date_key,
        o.returned_date_key,
        o.created_at,
        o.shipped_at,
        o.delivered_at,
        o.returned_at,
        o.num_of_item,
        o.source_updated_at,
        current_timestamp() as dwh_updated_at,
        
        coalesce(s.total_revenue, 0) as total_revenue,
        coalesce(s.total_cost, 0) as total_cost,
        coalesce(s.gross_margin, 0) as gross_margin,
        
        case 
            when coalesce(s.total_revenue, 0) = 0 then 0.0 
            else coalesce(s.gross_margin, 0) / s.total_revenue 
        end as margin_percentage,
        
        -- Durations
        timestamp_diff(o.shipped_at, o.created_at, DAY) as shipping_duration_days,
        timestamp_diff(o.delivered_at, o.shipped_at, DAY) as delivery_duration_days,
        timestamp_diff(o.delivered_at, o.created_at, DAY) as order_duration_days,
        
        -- Business logic
        case when o.num_of_item = 1 then 'Single' else 'Multi' end as order_type,
        case when timestamp_diff(o.delivered_at, o.shipped_at, DAY) > 5 then true else false end as is_delayed

    from orders_base o
    left join order_stats s on o.order_id = s.order_id
)

select *
from orders_with_stats
