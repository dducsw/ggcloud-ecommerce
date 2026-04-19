

select
    oi.order_item_id,
    oi.order_id,
    oi.user_id,
    oi.product_id,
  coalesce(oi.inventory_item_id, -1) as inventory_item_id,
    oi.status,
    oi.created_at,
    oi.shipped_at,
    oi.delivered_at,
    oi.returned_at,
    oi.sale_price,
    inv.cost,
    oi.sale_price - inv.cost as profit
from `cloud-data-project-492514`.`thelook_staging`.`stg_order_items` oi
left join `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items` inv
  on oi.inventory_item_id = inv.inventory_item_id
