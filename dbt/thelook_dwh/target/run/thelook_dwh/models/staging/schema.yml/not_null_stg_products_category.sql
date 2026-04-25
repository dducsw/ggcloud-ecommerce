
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select category
from `cloud-data-project-492514`.`thelook_staging`.`stg_products`
where category is null



  
  
      
    ) dbt_internal_test