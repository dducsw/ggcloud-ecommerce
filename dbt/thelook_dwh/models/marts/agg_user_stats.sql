{{
  config(
    materialized='incremental',
    unique_key='user_id'
  )
}}

{% set lookback_filter %}
    timestamp_sub(
        coalesce(max(source_updated_at), timestamp('1970-01-01')),
        interval 3 day
    )
{% endset %}

with impacted_users as (
    -- Thu thập user_ids bị ảnh hưởng từ cả 2 phía:
    -- (1) Users có profile thay đổi (ví dụ: địa chỉ, traffic_source...)
    select user_id
    from {{ ref('dim_users') }}
    where user_id != -1  -- Exclude unknown member
    {% if is_incremental() %}
      and source_updated_at >= (select {{ lookback_filter }} from {{ this }})
    {% endif %}

    union distinct

    -- (2) Users có đơn hàng mới hoặc được cập nhật
    select user_id
    from {{ ref('fact_orders') }}
    {% if is_incremental() %}
    where source_updated_at >= (select {{ lookback_filter }} from {{ this }})
    {% endif %}
)

select
    du.user_id,
    min(fo.created_at)                      as first_purchase_date,
    max(fo.created_at)                      as latest_purchase_date,
    count(distinct fo.order_id)             as total_orders,
    coalesce(sum(fo.total_revenue), 0)      as lifetime_value,
    case
        when count(distinct fo.order_id) = 0 then 'Potential'
        when count(distinct fo.order_id) = 1 then 'New'
        else 'Returning'
    end                                     as customer_status,
    max(coalesce(fo.source_updated_at, du.source_updated_at)) as source_updated_at,
    current_timestamp()                     as dwh_updated_at
from {{ ref('dim_users') }} du
inner join impacted_users iu
    on du.user_id = iu.user_id
left join {{ ref('fact_orders') }} fo
    on du.user_id = fo.user_id
group by du.user_id
