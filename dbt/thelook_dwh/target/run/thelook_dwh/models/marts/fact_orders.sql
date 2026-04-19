
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`
      
    partition by timestamp_trunc(created_at, day)
    

    
    OPTIONS()
    as (
      

select
    order_id,
    user_id,
    status,
    created_at,
    shipped_at,
    delivered_at,
    returned_at,
    num_of_item,
    cdc_timestamp,
    cdc_operation
from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`

    );
  