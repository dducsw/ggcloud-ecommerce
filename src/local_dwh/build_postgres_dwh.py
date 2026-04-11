import argparse
import re
from typing import Iterable

import psycopg2
from psycopg2 import sql


TABLES_TO_REPORT = [
    "stg_users",
    "stg_products",
    "stg_distribution_centers",
    "stg_orders",
    "stg_order_items",
    "stg_events",
    "dim_users",
    "dim_products",
    "dim_distribution_centers",
    "fact_orders",
    "fact_order_items",
    "fact_events",
]


def validate_schema_name(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Invalid schema name: {name}")
    return name


def execute_statements(cur, statements: Iterable[str]) -> None:
    for stmt in statements:
        cur.execute(stmt)


def create_staging(cur, source_schema: str, target_schema: str) -> None:
    statements = [
        f"""
        create table {target_schema}.stg_users as
        select
            cast(id as bigint) as user_id,
            coalesce(cast(first_name as text), 'Unknown') as first_name,
            coalesce(cast(last_name as text), 'Unknown') as last_name,
            coalesce(cast(email as text), 'N/A') as email,
            cast(age as int) as age,
            coalesce(cast(gender as text), 'Unknown') as gender,
            coalesce(cast(street_address as text), 'N/A') as street_address,
            coalesce(cast(postal_code as text), 'N/A') as postal_code,
            coalesce(cast(city as text), 'Unknown') as city,
            coalesce(cast(state as text), 'Unknown') as state,
            coalesce(cast(country as text), 'Unknown') as country,
            cast(latitude as double precision) as latitude,
            cast(longitude as double precision) as longitude,
            coalesce(cast(traffic_source as text), 'Unknown') as traffic_source,
            cast(created_at as timestamp) as created_at,
            cast(updated_at as timestamp) as updated_at
        from {source_schema}.users
        where id is not null
        """,
        f"""
        create table {target_schema}.stg_products as
        select
            cast(id as bigint) as product_id,
            cast(cost as numeric) as cost,
            coalesce(cast(category as text), 'Unknown') as category,
            coalesce(cast(name as text), 'Unknown') as product_name,
            coalesce(cast(brand as text), 'Unknown') as brand,
            cast(retail_price as numeric) as retail_price,
            coalesce(cast(department as text), 'Unknown') as department,
            coalesce(cast(sku as text), 'N/A') as sku,
            cast(distribution_center_id as bigint) as distribution_center_id,
            null::timestamp as created_at
        from {source_schema}.products
        where id is not null
          and retail_price >= 0
          and cost >= 0
        """,
        f"""
        create table {target_schema}.stg_distribution_centers as
        select
            cast(id as bigint) as distribution_center_id,
            coalesce(cast(name as text), 'Unknown') as distribution_center_name,
            cast(latitude as double precision) as latitude,
            cast(longitude as double precision) as longitude
        from {source_schema}.distribution_centers
        where id is not null
        """,
        f"""
        create table {target_schema}.stg_orders as
        with orders_base as (
            select
                cast(order_id as bigint) as order_id,
                cast(user_id as bigint) as user_id,
                coalesce(cast(status as text), 'Unknown') as status,
                coalesce(cast(gender as text), 'Unknown') as gender,
                cast(created_at as timestamp) as created_at,
                cast(shipped_at as timestamp) as shipped_at,
                cast(delivered_at as timestamp) as delivered_at,
                cast(returned_at as timestamp) as returned_at,
                cast(num_of_item as int) as num_of_item,
                row_number() over (partition by order_id order by created_at desc) as rn
            from {source_schema}.orders
            where order_id is not null
              and user_id is not null
              and num_of_item >= 0
              -- and coalesce(cdc_op, 'c') != 'd'
        )
        select
            order_id,
            user_id,
            status,
            gender,
            created_at,
            shipped_at,
            delivered_at,
            returned_at,
            num_of_item
        from orders_base
        where rn = 1
        """,
        f"""
        create table {target_schema}.stg_order_items as
        with order_items_base as (
            select
                cast(id as bigint) as order_item_id,
                cast(order_id as bigint) as order_id,
                cast(user_id as bigint) as user_id,
                cast(product_id as bigint) as product_id,
                coalesce(cast(inventory_item_id as bigint), -1) as inventory_item_id,
                coalesce(cast(status as text), 'Unknown') as status,
                cast(created_at as timestamp) as created_at,
                cast(shipped_at as timestamp) as shipped_at,
                cast(delivered_at as timestamp) as delivered_at,
                cast(returned_at as timestamp) as returned_at,
                cast(sale_price as numeric) as sale_price,
                row_number() over (partition by id order by created_at desc) as rn
            from {source_schema}.order_items
            where id is not null
              and order_id is not null
              and user_id is not null
              and product_id is not null
              and sale_price >= 0
              -- and coalesce(cdc_op, 'c') != 'd'
        )
        select
            order_item_id,
            order_id,
            user_id,
            product_id,
            inventory_item_id,
            status,
            created_at,
            shipped_at,
            delivered_at,
            returned_at,
            sale_price
        from order_items_base
        where rn = 1
        """,
        f"""
        create table {target_schema}.stg_events as
        with events_base as (
            select
                cast(id as bigint) as event_id,
                cast(user_id as bigint) as user_id,
                cast(sequence_number as int) as sequence_number,
                coalesce(cast(session_id as text), 'N/A') as session_id,
                coalesce(cast(ip_address as text), 'N/A') as ip_address,
                coalesce(cast(city as text), 'Unknown') as city,
                coalesce(cast(state as text), 'Unknown') as state,
                coalesce(cast(postal_code as text), 'N/A') as postal_code,
                coalesce(cast(browser as text), 'Unknown') as browser,
                coalesce(cast(traffic_source as text), 'Unknown') as traffic_source,
                coalesce(cast(uri as text), 'N/A') as uri,
                coalesce(cast(event_type as text), 'Unknown') as event_type,
                cast(created_at as timestamp) as created_at,
                row_number() over (partition by id order by created_at desc) as rn
            from {source_schema}.events
            where id is not null
              and user_id is not null
              and sequence_number >= 0
              -- and coalesce(cdc_op, 'c') != 'd'
        )
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
        from events_base
        where rn = 1
        """,
    ]
    execute_statements(cur, statements)


def create_marts(cur, target_schema: str) -> None:
    statements = [
        f"""
        create table {target_schema}.dim_users as
        select * from {target_schema}.stg_users
        """,
        f"""
        create table {target_schema}.dim_products as
        select
            product_id,
            product_name,
            category,
            brand,
            department,
            sku,
            retail_price,
            distribution_center_id,
            created_at
        from {target_schema}.stg_products
        """,
        f"""
        create table {target_schema}.dim_distribution_centers as
        select * from {target_schema}.stg_distribution_centers
        """,
        f"""
        create table {target_schema}.fact_orders as
        select * from {target_schema}.stg_orders
        """,
        f"""
        create table {target_schema}.fact_order_items as
        select
            oi.order_item_id,
            oi.order_id,
            oi.user_id,
            oi.product_id,
            coalesce(oi.inventory_item_id, -1) as inventory_item_id,
            oi.status,
            oi.created_at,
            oi.shipped_at,
            oi.delivered_at,
            oi.returned_at,
            oi.sale_price,
            p.cost,
            oi.sale_price - p.cost as profit
        from {target_schema}.stg_order_items oi
        left join {target_schema}.stg_products p
          on oi.product_id = p.product_id
        """,
        f"""
        create table {target_schema}.fact_events as
        select * from {target_schema}.stg_events
        """,
    ]
    execute_statements(cur, statements)


def create_indexes(cur, target_schema: str) -> None:
    statements = [
        f"create index idx_{target_schema}_fact_orders_created_at on {target_schema}.fact_orders (created_at)",
        f"create index idx_{target_schema}_fact_order_items_created_at on {target_schema}.fact_order_items (created_at)",
        f"create index idx_{target_schema}_fact_events_created_at on {target_schema}.fact_events (created_at)",
        f"create index idx_{target_schema}_fact_order_items_user_id on {target_schema}.fact_order_items (user_id)",
        f"create index idx_{target_schema}_fact_events_user_id on {target_schema}.fact_events (user_id)",
    ]
    execute_statements(cur, statements)


def print_counts(cur, target_schema: str) -> None:
    print("Build completed. Row counts:")
    for table_name in TABLES_TO_REPORT:
        cur.execute(
            sql.SQL("select count(*) from {}.{}")
            .format(sql.Identifier(target_schema), sql.Identifier(table_name))
        )
        count_value = cur.fetchone()[0]
        print(f"- {target_schema}.{table_name}: {count_value}")


def build_dwh(args: argparse.Namespace) -> None:
    source_schema = validate_schema_name(args.source_schema)
    target_schema = validate_schema_name(args.target_schema)

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=args.password,
    )
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            if args.drop_only:
                cur.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(target_schema)))
                conn.commit()
                print(f"Dropped schema {target_schema}")
                return

            if args.reset:
                cur.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(target_schema)))

            cur.execute(sql.SQL("create schema if not exists {} ").format(sql.Identifier(target_schema)))
            cur.execute(sql.SQL("set search_path to {} ").format(sql.Identifier(target_schema)))

            # Rebuild every table for deterministic local test runs.
            for table_name in TABLES_TO_REPORT:
                cur.execute(sql.SQL("drop table if exists {}.{} cascade")
                            .format(sql.Identifier(target_schema), sql.Identifier(table_name)))

            create_staging(cur, source_schema, target_schema)
            create_marts(cur, target_schema)
            create_indexes(cur, target_schema)
            print_counts(cur, target_schema)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local PostgreSQL DWH schema from demo source tables")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5433)
    parser.add_argument("--database", default="thelook_db")
    parser.add_argument("--user", default="db_user")
    parser.add_argument("--password", default="db_password")
    parser.add_argument("--source-schema", default="demo")
    parser.add_argument("--target-schema", default="dwh_local")
    parser.add_argument("--reset", action="store_true", help="Drop target schema before build")
    parser.add_argument("--drop-only", action="store_true", help="Drop target schema and exit")
    return parser.parse_args()


if __name__ == "__main__":
    build_dwh(parse_args())
