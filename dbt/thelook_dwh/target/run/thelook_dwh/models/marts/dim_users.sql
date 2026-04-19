
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_users`
      
    
    

    
    OPTIONS()
    as (
      

select
    user_id,
    first_name,
    last_name,
    email,
    age,
    gender,
    street_address,
    postal_code,
    city,
    state,
    country,
    latitude,
    longitude,
    traffic_source,
    created_at,
    updated_at
from `cloud-data-project-492514`.`thelook_staging`.`stg_users`
    );
  