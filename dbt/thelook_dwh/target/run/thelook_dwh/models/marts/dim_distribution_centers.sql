
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_distribution_centers`
      
    
    

    
    OPTIONS()
    as (
      

select
    distribution_center_id,
    distribution_center_name,
    latitude,
    longitude
from `cloud-data-project-492514`.`thelook_staging`.`stg_distribution_centers`
    );
  