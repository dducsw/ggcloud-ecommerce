import pandas as pd
import os

dwh_path = "dwh"

def validate_data():
    print("--- Data Validation Results ---")
    
    # 1. Fact Orders vs Dim Users
    users = pd.read_csv(os.path.join(dwh_path, "dim_users.csv"))
    orders = pd.read_csv(os.path.join(dwh_path, "fact_orders.csv"))
    
    print(f"Total Users: {len(users):,}")
    print(f"Total Orders: {len(orders):,}")
    
    # Check Joins
    unmatched_users = orders[~orders["user_key"].isin(users["user_key"])]
    print(f"1. Join Integrity: {len(unmatched_users)} orders have no matching user in dim_users.")
    
    # Check Duplicates
    dup_users = users["user_key"].duplicated().sum()
    print(f"2. User Keys: Found {dup_users} duplicate keys in dim_users.")
    
    # Check Value Ranges
    neg_rev = len(orders[orders["total_revenue"] < 0])
    print(f"3. Revenue: Found {neg_rev} orders with negative revenue.")
    
    # Check Nulls in Keys
    null_user_keys = orders["user_key"].isnull().sum()
    print(f"4. Null Keys: {null_user_keys} orders have null user_key.")
    
    # Check Dates
    dates = pd.read_csv(os.path.join(dwh_path, "dim_date.csv"))
    print(f"5. Date Range: {dates['date'].min()} to {dates['date'].max()}")

    # Check Fact Inventory
    inventory = pd.read_csv(os.path.join(dwh_path, "fact_inventory.csv"))
    products = pd.read_csv(os.path.join(dwh_path, "dim_products.csv"))
    unmatched_inv_products = inventory[~inventory["product_key"].isin(products["product_key"])]
    print(f"6. Inventory Integrity: {len(unmatched_inv_products)} inventory items have no matching product in dim_products.")

    # Check Fact Order Items
    order_items = pd.read_csv(os.path.join(dwh_path, "fact_order_items.csv"))
    unmatched_oi_products = order_items[~order_items["product_key"].isin(products["product_key"])]
    print(f"7. Order Items Integrity: {len(unmatched_oi_products)} order items have no matching product in dim_products.")

if __name__ == "__main__":
    validate_data()
