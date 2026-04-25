

with inventory_base as (
    select
        i.inventory_item_id,
        coalesce(p.product_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as product_key,
        i.product_id,
        coalesce(dc.dc_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as dc_key,
        i.product_distribution_center_id as distribution_center_id,
        i.created_at,
        i.sold_at,
        i.cost,
        coalesce(i.sold_at, i.created_at) as source_updated_at
    from `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items` i
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_products` p
      on i.product_id = p.product_id
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_distribution_centers` dc
      on i.product_distribution_center_id = dc.distribution_center_id
    
)

select
    inventory_item_id,
    product_key,
    product_id,
    dc_key,
    distribution_center_id,
    cast(format_date('%Y%m%d', date(created_at)) as int64) as created_date_key,
    coalesce(cast(format_date('%Y%m%d', date(sold_at)) as int64), 0) as sold_date_key,
    created_at,
    sold_at,
    cost,
    source_updated_at,
    current_timestamp() as dwh_updated_at,
    case
        when sold_at is not null then 'Sold'
        when created_at < timestamp_sub(current_timestamp(), interval 180 day) then 'Slow-Moving'
        else 'Available'
    end as inventory_status,
    case
        when sold_at is not null then true
        else false
    end as is_sold,
    timestamp_diff(sold_at, created_at, day) as days_in_inventory
from inventory_base