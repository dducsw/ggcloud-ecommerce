
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select revenue
from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_dashboard_daily`
where revenue is null



  
  
      
    ) dbt_internal_test