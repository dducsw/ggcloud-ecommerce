-- Test: Ensure no timestamps are in the future
-- This test will fail if any created_at dates are beyond current timestamp

select 
    'orders' as source_table,
    order_id as record_id,
    created_at as timestamp_value
from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`
where created_at > current_timestamp

union all

select 
    'order_items' as source_table,
    order_item_id as record_id,
    created_at as timestamp_value
from `cloud-data-project-492514`.`thelook_staging`.`stg_order_items`
where created_at > current_timestamp

union all

select 
    'users' as source_table,
    user_id as record_id,
    created_at as timestamp_value
from `cloud-data-project-492514`.`thelook_staging`.`stg_users`
where created_at > current_timestamp