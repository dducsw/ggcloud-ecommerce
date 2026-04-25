
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`fact_events`
      
    partition by timestamp_trunc(created_at, day)
    

    
    OPTIONS()
    as (
      

with events_base as (
    select
        e.event_id,
        coalesce(u.user_key, to_hex(md5(concat('c0:', coalesce(cast(-1 as string), '__null__'))))) as user_key,
        e.user_id,
        e.sequence_number,
        e.session_id,
        cast(format_date('%Y%m%d', date(e.created_at)) as int64) as created_date_key,
        e.ip_address,
        e.city,
        e.state,
        e.postal_code,
        e.browser,
        e.traffic_source,
        e.event_type,
        case 
            when lower(trim(e.event_type)) = 'purchase' then true 
            else false 
        end as is_checkout_event,
        e.uri,
        e.created_at as source_updated_at,
        current_timestamp() as dwh_updated_at,
        e.created_at
    from `cloud-data-project-492514`.`thelook_staging`.`stg_events` e
    left join `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_users` u
      on e.user_id = u.user_id
)

select *
from events_base

    );
  