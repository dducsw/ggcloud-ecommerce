
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select date
from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_dashboard_daily`
where date is null



  
  
      
    ) dbt_internal_test