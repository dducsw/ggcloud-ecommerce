
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        customer_status as value_field,
        count(*) as n_records

    from `cloud-data-project-492514`.`thelook_datawarehouse`.`agg_user_stats`
    group by customer_status

)

select *
from all_values
where value_field not in (
    'Potential','New','Returning'
)



  
  
      
    ) dbt_internal_test