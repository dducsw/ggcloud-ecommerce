
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select distribution_center_name
from `cloud-data-project-492514`.`thelook_staging`.`stg_distribution_centers`
where distribution_center_name is null



  
  
      
    ) dbt_internal_test