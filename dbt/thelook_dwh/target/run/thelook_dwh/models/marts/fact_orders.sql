-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders` as DBT_INTERNAL_DEST
        using (

with 

    -- Tìm tất cả các order_id bị ảnh hưởng từ 2 phía để đảm bảo không miss data khi order_item update
    impacted_orders as (
        select order_id 
        from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`
        where cdc_timestamp >= (select coalesce(max(cdc_timestamp), 0) from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`)
        
        union distinct
        
        select order_id 
        from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
        -- Lookback 1 day to catch any late arriving/updated items relative to the target table
        where created_at >= (select timestamp_sub(coalesce(max(created_at), timestamp('1970-01-01')), interval 1 day) from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`)
    ),


order_stats as (
    select
        order_id,
        sum(sale_price) as total_revenue,
        sum(cost) as total_cost,
        sum(profit) as gross_margin
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
    
    -- Lọc chỉ xử lý aggregation cho các đơn hàng bị ảnh hưởng để tối ưu performance mảng tính sum
    where order_id in (select order_id from impacted_orders)
    
    group by order_id
),

orders_base as (
    select
        o.order_id,
        o.user_id,
        o.status,
        o.created_at,
        o.shipped_at,
        o.delivered_at,
        o.returned_at,
        o.num_of_item,
        o.cdc_timestamp,
        o.cdc_operation
    from `cloud-data-project-492514`.`thelook_staging`.`stg_orders` o
    
    inner join impacted_orders io on o.order_id = io.order_id
    
),

orders_with_stats as (
    select
        o.order_id,
        o.user_id,
        o.status,
        o.created_at,
        o.shipped_at,
        o.delivered_at,
        o.returned_at,
        o.num_of_item,
        o.cdc_timestamp,
        o.cdc_operation,
        
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
        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.order_id = DBT_INTERNAL_DEST.order_id))

    
    when matched then update set
        `order_id` = DBT_INTERNAL_SOURCE.`order_id`,`user_id` = DBT_INTERNAL_SOURCE.`user_id`,`status` = DBT_INTERNAL_SOURCE.`status`,`created_at` = DBT_INTERNAL_SOURCE.`created_at`,`shipped_at` = DBT_INTERNAL_SOURCE.`shipped_at`,`delivered_at` = DBT_INTERNAL_SOURCE.`delivered_at`,`returned_at` = DBT_INTERNAL_SOURCE.`returned_at`,`num_of_item` = DBT_INTERNAL_SOURCE.`num_of_item`,`cdc_timestamp` = DBT_INTERNAL_SOURCE.`cdc_timestamp`,`cdc_operation` = DBT_INTERNAL_SOURCE.`cdc_operation`,`total_revenue` = DBT_INTERNAL_SOURCE.`total_revenue`,`total_cost` = DBT_INTERNAL_SOURCE.`total_cost`,`gross_margin` = DBT_INTERNAL_SOURCE.`gross_margin`,`margin_percentage` = DBT_INTERNAL_SOURCE.`margin_percentage`,`shipping_duration_days` = DBT_INTERNAL_SOURCE.`shipping_duration_days`,`delivery_duration_days` = DBT_INTERNAL_SOURCE.`delivery_duration_days`,`order_duration_days` = DBT_INTERNAL_SOURCE.`order_duration_days`,`order_type` = DBT_INTERNAL_SOURCE.`order_type`,`is_delayed` = DBT_INTERNAL_SOURCE.`is_delayed`
    

    when not matched then insert
        (`order_id`, `user_id`, `status`, `created_at`, `shipped_at`, `delivered_at`, `returned_at`, `num_of_item`, `cdc_timestamp`, `cdc_operation`, `total_revenue`, `total_cost`, `gross_margin`, `margin_percentage`, `shipping_duration_days`, `delivery_duration_days`, `order_duration_days`, `order_type`, `is_delayed`)
    values
        (`order_id`, `user_id`, `status`, `created_at`, `shipped_at`, `delivered_at`, `returned_at`, `num_of_item`, `cdc_timestamp`, `cdc_operation`, `total_revenue`, `total_cost`, `gross_margin`, `margin_percentage`, `shipping_duration_days`, `delivery_duration_days`, `order_duration_days`, `order_type`, `is_delayed`)


    