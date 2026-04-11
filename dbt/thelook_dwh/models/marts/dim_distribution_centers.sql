{{ config(materialized='table') }}

select
    distribution_center_id,
    distribution_center_name,
    latitude,
    longitude
from {{ ref('stg_distribution_centers') }}
