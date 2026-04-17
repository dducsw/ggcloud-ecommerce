-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `cloud-data-project-492514`.`thelook_staging_thelook_datawarehouse`.`fact_events` as DBT_INTERNAL_DEST
        using (

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
from `cloud-data-project-492514`.`thelook_staging_thelook_staging`.`stg_events`

where created_at >= (
    select coalesce(max(created_at), timestamp('1970-01-01'))
    from `cloud-data-project-492514`.`thelook_staging_thelook_datawarehouse`.`fact_events`
)

        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.event_id = DBT_INTERNAL_DEST.event_id))

    
    when matched then update set
        `event_id` = DBT_INTERNAL_SOURCE.`event_id`,`user_id` = DBT_INTERNAL_SOURCE.`user_id`,`sequence_number` = DBT_INTERNAL_SOURCE.`sequence_number`,`session_id` = DBT_INTERNAL_SOURCE.`session_id`,`ip_address` = DBT_INTERNAL_SOURCE.`ip_address`,`city` = DBT_INTERNAL_SOURCE.`city`,`state` = DBT_INTERNAL_SOURCE.`state`,`postal_code` = DBT_INTERNAL_SOURCE.`postal_code`,`browser` = DBT_INTERNAL_SOURCE.`browser`,`traffic_source` = DBT_INTERNAL_SOURCE.`traffic_source`,`event_type` = DBT_INTERNAL_SOURCE.`event_type`,`uri` = DBT_INTERNAL_SOURCE.`uri`,`created_at` = DBT_INTERNAL_SOURCE.`created_at`
    

    when not matched then insert
        (`event_id`, `user_id`, `sequence_number`, `session_id`, `ip_address`, `city`, `state`, `postal_code`, `browser`, `traffic_source`, `event_type`, `uri`, `created_at`)
    values
        (`event_id`, `user_id`, `sequence_number`, `session_id`, `ip_address`, `city`, `state`, `postal_code`, `browser`, `traffic_source`, `event_type`, `uri`, `created_at`)


    