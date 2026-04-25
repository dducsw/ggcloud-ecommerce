
  
    

    create or replace table `cloud-data-project-492514`.`thelook_datawarehouse`.`dim_date`
      
    
    

    
    OPTIONS()
    as (
      




with calendar as (
    select day as full_date
    from unnest(generate_date_array(date('2019-01-01'), date('2027-12-31'))) as day
)

select
    cast(format_date('%Y%m%d', full_date) as int64) as date_key,
    full_date,
    extract(day from full_date) as day_of_month,
    extract(dayofweek from full_date) as day_of_week,
    format_date('%A', full_date) as day_name,
    extract(week from full_date) as week_of_year,
    extract(isoweek from full_date) as iso_week_of_year,
    extract(month from full_date) as month_of_year,
    format_date('%B', full_date) as month_name,
    extract(quarter from full_date) as quarter_of_year,
    extract(year from full_date) as year_number,
    extract(isoyear from full_date) as iso_year_number,
    cast(null as timestamp) as source_updated_at,
    current_timestamp() as dwh_updated_at,
    case
        when extract(dayofweek from full_date) in (1, 7) then true
        else false
    end as is_weekend
from calendar

union all

-- Sentinel row: date_key = 0 → FK fallback cho "unknown date"
-- Guard: chỉ insert nếu 1970-01-01 nằm ngoài calendar range (tránh duplicate)
-- BigQuery yêu cầu FROM clause khi có WHERE clause
select
    0 as date_key,
    date('1970-01-01') as full_date,
    0 as day_of_month,
    0 as day_of_week,
    'Unknown' as day_name,
    0 as week_of_year,
    0 as iso_week_of_year,
    0 as month_of_year,
    'Unknown' as month_name,
    0 as quarter_of_year,
    0 as year_number,
    0 as iso_year_number,
    cast(null as timestamp) as source_updated_at,
    current_timestamp() as dwh_updated_at,
    false as is_weekend
from (select 1) as _sentinel
where date('1970-01-01') < date('2019-01-01')
    );
  