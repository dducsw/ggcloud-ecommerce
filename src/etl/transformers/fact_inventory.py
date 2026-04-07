import pandas as pd
from etl.transformers.utils import generate_surrogate_key, to_date_key

class FactInventoryTransformer:
    def transform(
        self,
        inventory_items: pd.DataFrame,
        dim_products: pd.DataFrame,
        dim_distribution_centers: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw inventory intake data and links to product/DC dimensions.
        """
        df = inventory_items.copy()
        
        # --- Layer 2: Transformation (Dimension Lookups) ---
        # Link to product surrogate keys
        df = df.merge(dim_products[["product_key", "product_id"]], on="product_id", how="left")
        
        # Link to distribution center surrogate keys
        df = df.merge(
            dim_distribution_centers[["dc_key", "id"]],
            left_on="product_distribution_center_id",
            right_on="id",
            how="left"
        )
        
        # Standardize IDs after joins
        if "id_y" in df.columns:
            df = df.drop(columns=["id_y"])
        df = df.rename(columns={"id_x": "id"})
        
        # --- Layer 3: Business Logic ---
        # Generate Surrogate Key (Deterministic)
        df["inventory_fact_id"] = df["id"].apply(generate_surrogate_key)
        
        # Standardize snapshots and event dates
        df["created_at_key"] = to_date_key(df["created_at"])
        df["sold_at_key"] = to_date_key(df["sold_at"])
        
        # Inventory Lifecycle Metrics
        df["is_sold"] = df["sold_at"].notna()
        
        # Robust duration calculation
        sold_dt = pd.to_datetime(df["sold_at"], format="mixed", utc=True)
        created_dt = pd.to_datetime(df["created_at"], format="mixed", utc=True)
        df["days_in_inventory"] = (sold_dt - created_dt).dt.days

        return df[[
            "inventory_fact_id", "id", "product_key", "dc_key",
            "created_at_key", "sold_at_key", "cost",
            "days_in_inventory", "is_sold"
        ]]
