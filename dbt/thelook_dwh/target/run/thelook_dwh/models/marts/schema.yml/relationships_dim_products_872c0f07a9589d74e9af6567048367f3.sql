
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with child as (
    select distribution_center_id as from_field
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_products`
    where distribution_center_id is not null
),

parent as (
    select distribution_center_id as to_field
    from `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_distribution_centers`
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null



  
  
      
    ) dbt_internal_test