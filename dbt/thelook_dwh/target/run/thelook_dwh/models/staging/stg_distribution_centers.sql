

  create or replace view `cloud-data-project-492514`.`thelook_staging`.`stg_distribution_centers`
  OPTIONS()
  as 

select
    cast(id as int64) as distribution_center_id,
    cast(name as string) as distribution_center_name,
    cast(latitude as float64) as latitude,
    cast(longitude as float64) as longitude
from `cloud-data-project-492514`.`thelook_staging`.`dist_centers`;

