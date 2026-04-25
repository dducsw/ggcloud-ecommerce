-- Test: Verify revenue consistency between fact_order_items and fact_orders
-- This test will fail if aggregated item revenue doesn't match order-level revenue

with sales_revenue as (
    select 
        order_id,
        sum(sale_price) as sales_total_revenue
    from {{ ref('fact_order_items') }}
    group by order_id
),
order_revenue as (
    select 
        order_id,
        total_revenue
    from {{ ref('fact_orders') }}
)
select 
    sr.order_id,
    sr.sales_total_revenue,
    or_.total_revenue,
    abs(sr.sales_total_revenue - or_.total_revenue) as revenue_diff
from sales_revenue sr
join order_revenue or_ 
    on sr.order_id = or_.order_id
where abs(sr.sales_total_revenue - or_.total_revenue) > 0.01
