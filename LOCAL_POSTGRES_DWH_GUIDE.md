# Local PostgreSQL DWH Flow

This flow builds a local warehouse directly in PostgreSQL so you can validate transformations before cloud deployment.

## What it creates

Target schema default: dwh_local

Tables created:
- stg_users
- stg_products
- stg_distribution_centers
- stg_orders
- stg_order_items
- stg_events
- dim_users
- dim_products
- dim_distribution_centers
- fact_orders
- fact_order_items
- fact_events

## Prerequisites

- Docker services running for postgres-source and datagen
- Python virtual environment activated
- Required packages installed from requirements.txt

## Build local warehouse

From repository root:

PowerShell command:
./infra/local_dwh/run_local_postgres_dwh.ps1 -Reset

This builds data from source schema demo into target schema dwh_local.

## Verify row counts quickly

PowerShell command:
docker exec -it postgres-source psql -U db_user -d thelook_db -c "select schemaname, tablename from pg_tables where schemaname='dwh_local' order by tablename;"

PowerShell command:
docker exec -it postgres-source psql -U db_user -d thelook_db -c "select count(*) as fact_orders_count from dwh_local.fact_orders;"

PowerShell command:
docker exec -it postgres-source psql -U db_user -d thelook_db -c "select count(*) as fact_events_count from dwh_local.fact_events;"

## Run data quality validation (PASS/FAIL)

PowerShell command:
./infra/local_dwh/validate_local_dwh.ps1

The script checks:
- Fact tables have data
- Duplicate keys in fact tables
- Null key columns in fact tables
- Orphan relations from facts to dimensions
- Negative values for key metrics

## How to view this local warehouse data

Open interactive psql:

PowerShell command:
docker exec -it postgres-source psql -U db_user -d thelook_db

Useful SQL commands in psql:

```sql
\dn
\dt dwh_local.*
select * from dwh_local.fact_orders order by created_at desc limit 20;
select * from dwh_local.fact_order_items order by created_at desc limit 20;
select * from dwh_local.fact_events order by created_at desc limit 20;
```

Quick one-liner from PowerShell (without interactive psql):

PowerShell command:
docker exec -it postgres-source psql -U db_user -d thelook_db -c "select * from dwh_local.fact_orders order by created_at desc limit 10;"

## Drop local warehouse when done

PowerShell command:
./infra/local_dwh/run_local_postgres_dwh.ps1 -DropOnly

## Notes

- The staging layer includes dedup using row_number partition by business key ordered by created_at desc.
- Basic null handling and non-negative checks are applied for key metrics.
- If a CDC operation column is available in source tables, add delete filtering where commented in the script.
