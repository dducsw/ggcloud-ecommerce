import pandas as pd
from etl.transformers.utils import generate_surrogate_key, to_date_key

class FactOrderItemsTransformer:
    def transform(
        self,
        order_items: pd.DataFrame,
        inventory_items: pd.DataFrame,
        dim_users: pd.DataFrame,
        dim_products: pd.DataFrame,
        dim_distribution_centers: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Transforms raw order items and enriches with profit/discount metrics, surrogate keys, and DC context.
        """
        df = order_items.copy()

        # --- Layer 1: Data Cleaning ---
        df["status"] = df["status"].str.strip().fillna("Unknown")
        df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True).dt.tz_localize(None)
        
        # Enrich with actual item cost and DC info from inventory
        inventory_subset = inventory_items[[
            "id", "cost", "product_retail_price", "product_distribution_center_id"
        ]].copy()
        
        df = df.merge(
            inventory_subset,
            left_on="inventory_item_id",
            right_on="id",
            how="left"
        )
        
        # Cleanup join artifacts
        if "id_y" in df.columns:
            df = df.drop(columns="id_y")
        df = df.rename(columns={"id_x": "id"})

        # --- Layer 2: Transformation ---
        # Calculate Item-level Margin and Profit
        df["gross_margin"] = df["sale_price"] - df["cost"]
        df["margin_percentage"] = (df["gross_margin"] / df["sale_price"]).fillna(0)
        
        # Link to dimensions via keys
        df["created_date_key"] = to_date_key(df["created_at"])
        df["shipped_date_key"] = to_date_key(df["shipped_at"])
        df["delivered_date_key"] = to_date_key(df["delivered_at"])
        df["returned_date_key"] = to_date_key(df["returned_at"])
        
        df = df.merge(dim_users[["user_key", "user_id"]], on="user_id", how="left")
        df = df.merge(dim_products[["product_key", "product_id"]], on="product_id", how="left")
        
        # Link to DC surrogate key
        df = df.merge(
            dim_distribution_centers[["dc_key", "id"]],
            left_on="product_distribution_center_id",
            right_on="id",
            how="left",
            suffixes=("", "_dc")
        )

        # Track Returns/Cancellations
        df["is_returned"] = df["status"].isin(["Returned", "Cancelled"])

        # Generate Surrogate Key (Deterministic)
        df["order_item_fact_id"] = df["id"].apply(generate_surrogate_key)

        return df[[
            "order_item_fact_id", "id", "order_id", "user_key", "product_key", "dc_key",
            "sale_price", "cost", "gross_margin", "margin_percentage",
            "status", "is_returned",
            "created_date_key", "shipped_date_key", "delivered_date_key", "returned_date_key"
        ]]
