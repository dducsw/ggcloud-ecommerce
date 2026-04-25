
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select country
from `cloud-data-project-492514`.`thelook_staging`.`stg_users`
where country is null



  
  
      
    ) dbt_internal_test