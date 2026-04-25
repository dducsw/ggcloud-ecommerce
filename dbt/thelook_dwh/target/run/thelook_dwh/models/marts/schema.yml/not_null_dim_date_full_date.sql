
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select full_date
from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_date`
where full_date is null



  
  
      
    ) dbt_internal_test