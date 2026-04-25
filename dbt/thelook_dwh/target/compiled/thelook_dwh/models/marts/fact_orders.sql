

with 


order_stats as (
    select
        order_id,
        sum(sale_price) as total_revenue,
        sum(cost) as total_cost,
        sum(profit) as gross_margin
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
    
    group by order_id
),

orders_base as (
    select
        o.order_id,
        coalesce(u.user_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as user_key,
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
    from `cloud-data-project-492514`.`thelook_staging`.`stg_orders` o
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_users` u
      on o.user_id = u.user_id
    
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