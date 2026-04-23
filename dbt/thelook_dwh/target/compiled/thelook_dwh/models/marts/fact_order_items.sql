

select
    oi.order_item_id,
    oi.order_id,
    oi.user_id,
    oi.product_id,
    coalesce(oi.inventory_item_id, -1) as inventory_item_id,
    oi.status,
    case 
        when oi.status in ('Returned', 'Cancelled') then true 
        else false 
    end as is_returned,
    oi.created_at,
    oi.shipped_at,
    oi.delivered_at,
    oi.returned_at,
    oi.sale_price,
    inv.cost,
    oi.sale_price - inv.cost as profit,
    case 
        when coalesce(oi.sale_price, 0) = 0 then 0.0 
        else (oi.sale_price - inv.cost) / oi.sale_price 
    end as margin_percentage
from `cloud-data-project-492514`.`thelook_staging`.`stg_order_items` oi
left join `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items` inv
  on oi.inventory_item_id = inv.inventory_item_id

where oi.created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
)
