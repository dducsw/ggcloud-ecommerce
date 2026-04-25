
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select user_key
from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_order_items`
where user_key is null



  
  
      
    ) dbt_internal_test