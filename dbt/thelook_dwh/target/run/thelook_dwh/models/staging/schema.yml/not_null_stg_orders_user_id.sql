
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select user_id
from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`
where user_id is null



  
  
      
    ) dbt_internal_test