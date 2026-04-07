-- Dimensional Modeling for TheLook eCommerce
-- Schema: Star Schema
-- Target: Google BigQuery
-- Note: Replace `cloud-data-project-476106` with your target project and `thelook_dwh` with your target Dataset ID.

-- ==========================================
-- 1. DIMENSION TABLES
-- ==========================================

-- User Dimension
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.dim_users` (
    user_key STRING,                     -- Surrogate Key (Use GENERATE_UUID() or FARM_FINGERPRINT() during ETL)
    user_id INT64 NOT NULL,              -- Natural Key (from source)
    first_name STRING,
    last_name STRING,
    email STRING,
    age INT64,
    gender STRING,
    state STRING,
    street_address STRING,
    postal_code STRING,
    city STRING,
    country STRING,
    latitude FLOAT64,
    longitude FLOAT64,
    traffic_source STRING,
    created_at TIMESTAMP,
    first_purchase_date TIMESTAMP,       -- First order date
    latest_purchase_date TIMESTAMP        -- Most recent order date
);

-- Distribution Center Dimension
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.dim_distribution_centers` (
    distribution_center_key STRING, 
    distribution_center_id INT64 NOT NULL, 
    name STRING,
    latitude FLOAT64,
    longitude FLOAT64
);

-- Product Dimension
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.dim_products` (
    product_key STRING,   
    product_id INT64 NOT NULL,   
    category STRING,
    name STRING,
    brand STRING,
    department STRING,
    sku STRING,
    retail_price FLOAT64,
    cost FLOAT64,                        -- Base cost to acquire
    distribution_center_key STRING       -- Default DC for this product (may differ from actual fulfillment DC in fact_order_items)
);

-- Date Dimension (Standard in DWH for Time-Series Analysis)
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.dim_date` (
    date_key INT64,                      -- Format: YYYYMMDD (e.g., 20240406)
    full_date DATE NOT NULL,
    day_name STRING,                     -- Monday, Tuesday...
    day_of_month INT64,
    month INT64,
    month_name STRING,                   -- January, February...
    quarter INT64,                       -- 1, 2, 3, 4
    year INT64,
    is_weekend BOOL
);

-- ==========================================
-- 2. FACT TABLES
-- ==========================================

-- Fact Orders: Grain = 1 row per order (Header level)
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.fact_orders` (
    order_fact_id STRING,                -- Surrogate Key cho Fact
    order_id INT64,                      -- Natural Key
    
    -- Foreign Keys
    user_key STRING,
    created_date_key INT64,
    
    -- Attributes
    status STRING,
    gender STRING,                      -- Gender at the time of order

    -- WARNING: Do not re-aggregate from fact_order_items for these measures
    num_items_distinct INT64,             -- Số lượng loại sản phẩm khác nhau
    num_of_item INT64,                   -- Tổng số lượng item (từ bảng orders gốc)
    
    -- Measures
    total_revenue FLOAT64,
    total_cost FLOAT64,
    total_gross_margin FLOAT64,
    
    created_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    returned_at TIMESTAMP,
    delivery_time_days INT64,
    is_returned BOOL
);


-- Fact Order Items: Grain = 1 row per item inside an order
-- We combine 'orders', 'order_items', and 'inventory_items' into this single fact table
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.fact_order_items` (
    order_item_fact_id STRING,           -- Surrogate Key
    order_item_id INT64,                 -- Natural Key from source
    order_id INT64,                      -- To group items by order
    
    -- Foreign Keys to Dimensions
    user_key STRING,
    product_key STRING,
    distribution_center_key STRING,
    created_date_key INT64,
    
    -- Status & Timestamps
    status STRING,                       -- Processing, Shipped, Complete, Cancelled, Returned
    created_at TIMESTAMP,
    shipped_at TIMESTAMP,
    delivered_at TIMESTAMP,
    returned_at TIMESTAMP,
    
    -- Measures (Metrics)
    sale_price FLOAT64,                  -- Revenue
    cost FLOAT64,                        -- IMPORTANT: Cost must come from inventory_items.cost (Actual cost)
    gross_margin FLOAT64                 -- Derived: (sale_price - cost)
);

-- Fact Web Events: Grain = 1 row per web activity event
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.fact_events` (
    event_fact_id STRING,
    event_id INT64,                      -- Natural Key
    
    -- Foreign Keys
    user_key STRING,                     -- Can be NULL if guest checkout
    created_date_key INT64,
    
    -- Event Attributes
    sequence_number INT64,               -- Order of event in the session
    session_id STRING,
    ip_address STRING,
    browser STRING,
    traffic_source STRING,
    uri STRING,
    event_type STRING,                   -- e.g., 'cart', 'purchase', 'product'
    
    -- Location captured at the time of the event
    city STRING,
    state STRING,
    postal_code STRING,
    country STRING,                      -- Lookup from dim_users
    
    created_at TIMESTAMP
);

-- Fact Inventory: Grain = 1 row per unique item in inventory
-- Allows tracking stock levels and how long items stay in inventory
CREATE OR REPLACE TABLE `cloud-data-project-476106.thelook_dwh.fact_inventory` (
    inventory_fact_id   STRING,          -- Surrogate Key
    inventory_item_id   INT64,           -- Natural Key from source
    product_key         STRING,          -- FK to dim_products
    distribution_center_key STRING,      -- FK to dim_distribution_centers
    created_date_key    INT64,           -- Date item entered inventory
    sold_date_key INT64,                 -- NULL if unsold; use LEFT JOIN with dim_date
    
    -- Measures
    cost                FLOAT64,         -- Actual cost of this specific item (from inventory_items.cost)
    days_in_inventory   INT64,           -- Derived: sold_at - created_at (NULL if not sold)
    is_sold             BOOL             -- Flag for current stock status
);

