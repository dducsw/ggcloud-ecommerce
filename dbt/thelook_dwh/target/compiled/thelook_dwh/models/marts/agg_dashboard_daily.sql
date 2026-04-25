

with orders_daily as (
    select
        date(created_at) as date,
        coalesce(sum(total_revenue), 0) as revenue,
        coalesce(sum(total_cost), 0) as cost,
        coalesce(sum(gross_margin), 0) as margin,
        count(distinct order_id) as orders,
        max(source_updated_at) as orders_source_updated_at
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`
    
    group by 1
),

events_daily as (
    select
        date(created_at) as date,
        count(distinct user_id) as total_users,
        count(distinct session_id) as total_sessions,
        count(distinct if(is_checkout_event, session_id, null)) as purchase_sessions,
        max(source_updated_at) as events_source_updated_at
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_events`
    
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
    coalesce(e.purchase_sessions, 0) as purchase_sessions,
    greatest(
        coalesce(o.orders_source_updated_at, timestamp('1970-01-01')),
        coalesce(e.events_source_updated_at, timestamp('1970-01-01'))
    ) as source_updated_at,
    current_timestamp() as dwh_updated_at,
    coalesce(safe_divide(e.purchase_sessions, e.total_sessions), 0) as purchase_cvr
from orders_daily o
full outer join events_daily e
  on o.date = e.date