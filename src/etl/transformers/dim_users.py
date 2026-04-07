import pandas as pd
from datetime import datetime
from etl.transformers.utils import generate_surrogate_key

class DimUsersTransformer:
    def transform(
        self,
        users: pd.DataFrame,
        orders: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw user data and merges with order stats for the user dimension.
        """
        df = users.copy()

        # --- Layer 1: Data Cleaning ---
        df["first_name"] = df["first_name"].str.strip().fillna("Unknown")
        df["last_name"] = df["last_name"].str.strip().fillna("Unknown")
        df["email"] = df["email"].str.strip().str.lower()
        df["gender"] = df["gender"].fillna("Unknown")
        df["country"] = df["country"].str.upper()
        df["city"] = df["city"].fillna("Unknown")
        
        # Ensure created_at is timestamp
        df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True).dt.tz_localize(None)

        # --- Layer 2: Transformation ---
        # Calculate purchase stats from orders
        purchase_stats = orders.groupby("user_id").agg(
            first_purchase_date=("created_at", "min"),
            latest_purchase_date=("created_at", "max"),
            total_orders=("order_id", "nunique")
        ).reset_index()

        df = df.merge(purchase_stats, left_on="id", right_on="user_id", how="left")
        df = df.drop(columns=["user_id"])

        # --- Layer 3: Business Logic ---
        # Categorize Age Groups
        def categorize_age(age):
            if pd.isna(age): return "Unknown"
            if age < 18: return "Under 18"
            if age < 60: return "Adult"
            return "Senior"

        df["age_group"] = df["age"].apply(categorize_age)
        
        # Determine Customer Status (New, Returning, or Potential)
        def get_customer_status(row):
            if pd.isna(row["first_purchase_date"]):
                return "Potential"
            if row["first_purchase_date"] == row["latest_purchase_date"]:
                return "New"
            return "Returning"

        df["customer_status"] = df.apply(get_customer_status, axis=1)

        # Generate Surrogate Key (Deterministic)
        df["user_key"] = df["id"].apply(generate_surrogate_key)
        df = df.rename(columns={"id": "user_id"})

        return df[[
            "user_key", "user_id", "first_name", "last_name",
            "email", "age", "age_group", "customer_status", "gender", "state", "city", "country",
            "postal_code", "latitude", "longitude",
            "traffic_source", "created_at",
            "first_purchase_date", "latest_purchase_date"
        ]]
