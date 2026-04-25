
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select inventory_item_id
from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_inventory`
where inventory_item_id is null



  
  
      
    ) dbt_internal_test