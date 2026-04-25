
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select user_id
from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_user_stats`
where user_id is null



  
  
      
    ) dbt_internal_test