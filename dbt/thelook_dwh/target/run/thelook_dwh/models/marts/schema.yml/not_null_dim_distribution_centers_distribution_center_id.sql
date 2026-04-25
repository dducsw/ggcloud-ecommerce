
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select distribution_center_id
from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_distribution_centers`
where distribution_center_id is null



  
  
      
    ) dbt_internal_test