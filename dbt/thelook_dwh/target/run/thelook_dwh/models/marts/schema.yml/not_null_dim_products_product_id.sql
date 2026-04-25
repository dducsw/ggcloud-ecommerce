
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select product_id
from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_products`
where product_id is null



  
  
      
    ) dbt_internal_test