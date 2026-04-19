

  create or replace view `cloud-data-project-492514`.`thelook_staging`.`stg_users`
  OPTIONS()
  as 

select
    cast(id as int64) as user_id,
    cast(first_name as string) as first_name,
    cast(last_name as string) as last_name,
    cast(email as string) as email,
    cast(age as int64) as age,
    cast(gender as string) as gender,
    cast(street_address as string) as street_address,
    cast(postal_code as string) as postal_code,
    cast(city as string) as city,
    cast(state as string) as state,
    cast(country as string) as country,
    cast(latitude as float64) as latitude,
    cast(longitude as float64) as longitude,
    cast(traffic_source as string) as traffic_source,
    case
    when created_at is null then null
    when regexp_contains(cast(created_at as string), r'^\d+$') then
        case
            when length(cast(created_at as string)) >= 16 then timestamp_micros(cast(created_at as int64))
            when length(cast(created_at as string)) >= 13 then timestamp_millis(cast(created_at as int64))
            else timestamp_seconds(cast(created_at as int64))
        end
    else safe_cast(cast(created_at as string) as timestamp)
end as created_at,
    case
    when updated_at is null then null
    when regexp_contains(cast(updated_at as string), r'^\d+$') then
        case
            when length(cast(updated_at as string)) >= 16 then timestamp_micros(cast(updated_at as int64))
            when length(cast(updated_at as string)) >= 13 then timestamp_millis(cast(updated_at as int64))
            else timestamp_seconds(cast(updated_at as int64))
        end
    else safe_cast(cast(updated_at as string) as timestamp)
end as updated_at
from `cloud-data-project-492514`.`thelook_staging`.`users`;

