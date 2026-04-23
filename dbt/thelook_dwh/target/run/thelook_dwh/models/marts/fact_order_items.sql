-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items` as DBT_INTERNAL_DEST
        using (

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

        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.order_item_id = DBT_INTERNAL_DEST.order_item_id))

    
    when matched then update set
        `order_item_id` = DBT_INTERNAL_SOURCE.`order_item_id`,`order_id` = DBT_INTERNAL_SOURCE.`order_id`,`user_id` = DBT_INTERNAL_SOURCE.`user_id`,`product_id` = DBT_INTERNAL_SOURCE.`product_id`,`inventory_item_id` = DBT_INTERNAL_SOURCE.`inventory_item_id`,`status` = DBT_INTERNAL_SOURCE.`status`,`is_returned` = DBT_INTERNAL_SOURCE.`is_returned`,`created_at` = DBT_INTERNAL_SOURCE.`created_at`,`shipped_at` = DBT_INTERNAL_SOURCE.`shipped_at`,`delivered_at` = DBT_INTERNAL_SOURCE.`delivered_at`,`returned_at` = DBT_INTERNAL_SOURCE.`returned_at`,`sale_price` = DBT_INTERNAL_SOURCE.`sale_price`,`cost` = DBT_INTERNAL_SOURCE.`cost`,`profit` = DBT_INTERNAL_SOURCE.`profit`,`margin_percentage` = DBT_INTERNAL_SOURCE.`margin_percentage`
    

    when not matched then insert
        (`order_item_id`, `order_id`, `user_id`, `product_id`, `inventory_item_id`, `status`, `is_returned`, `created_at`, `shipped_at`, `delivered_at`, `returned_at`, `sale_price`, `cost`, `profit`, `margin_percentage`)
    values
        (`order_item_id`, `order_id`, `user_id`, `product_id`, `inventory_item_id`, `status`, `is_returned`, `created_at`, `shipped_at`, `delivered_at`, `returned_at`, `sale_price`, `cost`, `profit`, `margin_percentage`)


    