
    
    

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


