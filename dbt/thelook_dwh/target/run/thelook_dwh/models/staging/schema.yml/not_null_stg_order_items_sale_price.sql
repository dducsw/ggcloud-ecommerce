
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select sale_price
from `cloud-data-project-492514`.`thelook_staging`.`stg_order_items`
where sale_price is null



  
  
      
    ) dbt_internal_test