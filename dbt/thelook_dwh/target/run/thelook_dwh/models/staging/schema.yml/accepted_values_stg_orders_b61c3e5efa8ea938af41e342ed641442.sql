
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        status as value_field,
        count(*) as n_records

    from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`
    group by status

)

select *
from all_values
where value_field not in (
    'Processing','Shipped','Complete','Returned','Cancelled','Unknown'
)



  
  
      
    ) dbt_internal_test