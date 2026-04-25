
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select created_at
from `cloud-data-project-492514`.`thelook_staging`.`stg_inventory_items`
where created_at is null



  
  
      
    ) dbt_internal_test