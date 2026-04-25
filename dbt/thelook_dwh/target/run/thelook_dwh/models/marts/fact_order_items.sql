
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
      
    partition by timestamp_trunc(created_at, day)
    

    
    OPTIONS()
    as (
      

with order_items_enriched as (
    select
        oi.order_item_id,
        oi.order_id,
        coalesce(u.user_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as user_key,
        oi.user_id,
        coalesce(p.product_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as product_key,
        oi.product_id,
        coalesce(oi.inventory_item_id, -1) as inventory_item_id,
        coalesce(dc.dc_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as dc_key,
        cast(format_date('%Y%m%d', date(oi.created_at)) as int64) as created_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.shipped_at)) as int64), 0) as shipped_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.delivered_at)) as int64), 0) as delivered_date_key,
        coalesce(cast(format_date('%Y%m%d', date(oi.returned_at)) as int64), 0) as returned_date_key,
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
        coalesce(inv.cost, p.cost) as cost,
        oi.sale_price - coalesce(inv.cost, p.cost) as profit,
        coalesce(oi.returned_at, oi.delivered_at, oi.shipped_at, oi.created_at) as source_updated_at,
        current_timestamp() as dwh_updated_at,
        case 
            when coalesce(oi.sale_price, 0) = 0 then 0.0 
            else (oi.sale_price - coalesce(inv.cost, p.cost)) / oi.sale_price 
        end as margin_percentage
    from `cloud-data-project-492514`.`thelook_staging`.`stg_order_items` oi
    left join `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items` inv
      on oi.inventory_item_id = inv.inventory_item_id
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_users` u
      on oi.user_id = u.user_id
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_products` p
      on oi.product_id = p.product_id
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_distribution_centers` dc
      on inv.product_distribution_center_id = dc.distribution_center_id
)

select *
from order_items_enriched

    );
  