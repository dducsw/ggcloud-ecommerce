-- Test: Ensure order status timestamps follow logical sequence
-- Processing -> Shipped -> Delivered -> (optionally) Returned

select 
    order_id,
    status,
    created_at,
    shipped_at,
    delivered_at,
    returned_at
from {{ ref('stg_orders') }}
where 
    -- Shipped date cannot be before created date
    (shipped_at is not null and shipped_at < created_at)
    -- Delivered date cannot be before shipped date
    or (delivered_at is not null and shipped_at is not null and delivered_at < shipped_at)
    -- Returned date cannot be before delivered date
    or (returned_at is not null and delivered_at is not null and returned_at < delivered_at)
    -- Delivered status must have delivered_at timestamp
    or (status = 'Complete' and delivered_at is null)
    -- Returned status must have returned_at timestamp
    or (status = 'Returned' and returned_at is null)
