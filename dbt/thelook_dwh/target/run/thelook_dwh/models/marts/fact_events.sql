
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_events`
      
    partition by timestamp_trunc(created_at, day)
    

    
    OPTIONS()
    as (
      

select
    event_id,
    user_id,
    sequence_number,
    session_id,
    ip_address,
    city,
    state,
    postal_code,
    browser,
    traffic_source,
    event_type,
    uri,
    created_at
from `cloud-data-project-492514`.`thelook_staging`.`stg_events`

    );
  