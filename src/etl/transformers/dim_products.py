import pandas as pd
from etl.transformers.utils import generate_surrogate_key

class DimProductsTransformer:
    def transform(
        self,
        products: pd.DataFrame,
        dim_distribution_centers: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw product data and links to distribution center keys.
        """
        df = products.copy()

        # --- Layer 1: Data Cleaning ---
        df["name"] = df["name"].str.strip()
        df["category"] = df["category"].str.strip().fillna("Unknown")
        df["brand"] = df["brand"].str.strip().fillna("Unknown")
        df["department"] = df["department"].str.strip()

        # --- Layer 2: Transformation ---
        # Calculate Margin Value
        df["margin_value"] = df["retail_price"] - df["cost"]
        
        # Link to distribution centers for the surrogate key lookup
        df = df.merge(
            dim_distribution_centers[["dc_key", "id"]],
            left_on="distribution_center_id",
            right_on="id",
            how="left"
        )
        
        # Cleanup join artifacts and standardize IDs
        if "id_y" in df.columns:
            df = df.drop(columns="id_y")
        df = df.rename(columns={"id_x": "product_id"})

        # --- Layer 3: Business Logic ---
        # Generate Surrogate Key (Deterministic)
        df["product_key"] = df["product_id"].apply(generate_surrogate_key)

        return df[[
            "product_key", "product_id", "name", "category",
            "brand", "department", "sku", "retail_price",
            "cost", "margin_value", "dc_key"
        ]]
