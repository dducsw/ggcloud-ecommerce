-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_dashboard_daily` as DBT_INTERNAL_DEST
        using (

with orders_daily as (
    select
        date(created_at) as date,
        coalesce(sum(total_revenue), 0) as revenue,
        coalesce(sum(total_cost), 0) as cost,
        coalesce(sum(gross_margin), 0) as margin,
        count(distinct order_id) as orders
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`
    
    where created_at >= (
        select timestamp_sub(coalesce(max(timestamp(date)), timestamp('1970-01-01')), interval 2 day)
        from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_dashboard_daily`
    )
    
    group by 1
),

events_daily as (
    select
        date(created_at) as date,
        count(distinct user_id) as total_users,
        count(distinct session_id) as total_sessions,
    count(distinct if(is_checkout_event, session_id, null)) as checkout_events
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_events`
    
    where created_at >= (
        select timestamp_sub(coalesce(max(timestamp(date)), timestamp('1970-01-01')), interval 2 day)
        from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_dashboard_daily`
    )
    
    group by 1
)

select
    coalesce(o.date, e.date) as date,
    coalesce(o.revenue, 0) as revenue,
    coalesce(o.cost, 0) as cost,
    coalesce(o.margin, 0) as margin,
    coalesce(o.orders, 0) as orders,
    coalesce(e.total_users, 0) as total_users,
    coalesce(e.total_sessions, 0) as total_sessions,
    coalesce(e.checkout_events, 0) as checkout_events,
    coalesce(safe_divide(e.checkout_events, e.total_sessions), 0) as cvr
from orders_daily o
full outer join events_daily e
  on o.date = e.date
        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.date = DBT_INTERNAL_DEST.date))

    
    when matched then update set
        `date` = DBT_INTERNAL_SOURCE.`date`,`revenue` = DBT_INTERNAL_SOURCE.`revenue`,`cost` = DBT_INTERNAL_SOURCE.`cost`,`margin` = DBT_INTERNAL_SOURCE.`margin`,`orders` = DBT_INTERNAL_SOURCE.`orders`,`total_users` = DBT_INTERNAL_SOURCE.`total_users`,`total_sessions` = DBT_INTERNAL_SOURCE.`total_sessions`,`checkout_events` = DBT_INTERNAL_SOURCE.`checkout_events`,`cvr` = DBT_INTERNAL_SOURCE.`cvr`
    

    when not matched then insert
        (`date`, `revenue`, `cost`, `margin`, `orders`, `total_users`, `total_sessions`, `checkout_events`, `cvr`)
    values
        (`date`, `revenue`, `cost`, `margin`, `orders`, `total_users`, `total_sessions`, `checkout_events`, `cvr`)


    