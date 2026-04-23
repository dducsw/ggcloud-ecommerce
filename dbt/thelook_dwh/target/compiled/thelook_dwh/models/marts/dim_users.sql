

with user_order_stats as (
    select
        user_id,
        min(created_at) as first_purchase_date,
        max(created_at) as latest_purchase_date,
        count(distinct order_id) as total_orders
    from `cloud-data-project-492514`.`thelook_staging`.`stg_orders`
    group by user_id
),

users_base as (
    select
        u.user_id,
        u.first_name,
        u.last_name,
        u.email,
        u.age,
        u.gender,
        u.street_address,
        u.postal_code,
        u.city,
        u.state,
        u.country,
        u.latitude,
        u.longitude,
        u.traffic_source,
        u.created_at,
        u.updated_at,
        
        s.first_purchase_date,
        s.latest_purchase_date,
        coalesce(s.total_orders, 0) as total_orders
    from `cloud-data-project-492514`.`thelook_staging`.`stg_users` u
    left join user_order_stats s on u.user_id = s.user_id
)

select
    user_id,
    first_name,
    last_name,
    email,
    age,
    case
        when age is null then 'Unknown'
        when age < 18 then 'Under 18'
        when age < 60 then 'Adult'
        else 'Senior'
    end as age_group,
    case
        when first_purchase_date is null then 'Potential'
        when first_purchase_date = latest_purchase_date then 'New'
        else 'Returning'
    end as customer_status,
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
    updated_at,
    first_purchase_date,
    latest_purchase_date,
    total_orders
from users_base