-- Test: Verify num_of_item in orders matches actual count in order_items
-- This test will fail if there's a mismatch between header and detail counts

with order_item_counts as (
    select 
        order_id,
        count(*) as actual_item_count
    from {{ ref('stg_order_items') }}
    group by order_id
),
orders_with_counts as (
    select 
        o.order_id,
        o.num_of_item as declared_item_count,
        coalesce(oic.actual_item_count, 0) as actual_item_count
    from {{ ref('stg_orders') }} o
    left join order_item_counts oic 
        on o.order_id = oic.order_id
)
select 
    order_id,
    declared_item_count,
    actual_item_count,
    declared_item_count - actual_item_count as discrepancy
from orders_with_counts
where declared_item_count != actual_item_count
