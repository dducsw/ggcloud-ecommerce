
    
    

with child as (
    select created_date_key as from_field
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_orders`
    where created_date_key is not null
),

parent as (
    select date_key as to_field
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_date`
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


