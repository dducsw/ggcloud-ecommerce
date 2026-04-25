
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select dc_key
from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_inventory`
where dc_key is null



  
  
      
    ) dbt_internal_test