import pandas as pd
from etl.transformers.utils import generate_surrogate_key, to_date_key

class FactOrdersTransformer:
    def transform(
        self,
        orders: pd.DataFrame,
        order_items: pd.DataFrame,
        inventory_items: pd.DataFrame,
        dim_users: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw order data and aggregates financial metrics to the order level.
        """
        df = orders.copy()

        # --- Layer 1: Data Cleaning ---
        df["status"] = df["status"].str.strip().fillna("Unknown")
        df["gender"] = df["gender"].str.upper().fillna("U")
        
        # Safely convert date columns to datetime only if they aren't already
        # This prevents turning valid datetimes into NaT during redundant parsing
        date_cols = ["created_at", "shipped_at", "delivered_at", "returned_at"]
        for col in date_cols:
            if not pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = pd.to_datetime(df[col], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
            else:
                if df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)

        # --- Auxiliary Stage: Financial Aggregation ---
        # Join order_items with inventory to calculate actual cost
        items_with_cost = order_items.merge(
            inventory_items[["id", "cost"]],
            left_on="inventory_item_id",
            right_on="id",
            how="left",
            suffixes=("", "_inv")
        )
        if "id_inv" in items_with_cost.columns:
            items_with_cost = items_with_cost.drop(columns="id_inv")

        # Aggregate revenue and cost by order_id
        order_stats = items_with_cost.groupby("order_id").agg(
            total_revenue=("sale_price", "sum"),
            total_cost=("cost", "sum")
        ).reset_index()

        # Calculate Margin Metrics
        order_stats["gross_margin"] = order_stats["total_revenue"] - order_stats["total_cost"]
        order_stats["margin_percentage"] = (order_stats["gross_margin"] / order_stats["total_revenue"]).fillna(0)

        # Merge statistics back to the orders DataFrame
        df = df.merge(order_stats, on="order_id", how="left")

        # --- Layer 2: Transformation ---
        # Calculate logistics and operational durations
        df["shipping_duration_days"] = (df["shipped_at"] - df["created_at"]).dt.days
        df["delivery_duration_days"] = (df["delivered_at"] - df["shipped_at"]).dt.days
        df["order_duration_days"] = (df["delivered_at"] - df["created_at"]).dt.days
        
        # Link to date dimension via keys
        df["created_date_key"] = to_date_key(df["created_at"])
        df["shipped_date_key"] = to_date_key(df["shipped_at"])
        df["delivered_date_key"] = to_date_key(df["delivered_at"])
        df["returned_date_key"] = to_date_key(df["returned_at"])

        # Lookup user surrogate keys (avoiding duplicate info columns)
        cols_to_use = dim_users.columns.difference(df.columns).tolist() + ["user_id"]
        df = df.merge(dim_users[cols_to_use], on="user_id", how="left")

        # --- Layer 3: Business Logic ---
        # Classify order complexity and logistics status
        df["order_type"] = df["num_of_item"].apply(lambda x: "Single" if x == 1 else "Multi")
        df["is_delayed"] = df["delivery_duration_days"] > 5
        
        # Generate Surrogate Key (Deterministic)
        df["order_fact_id"] = df["order_id"].apply(generate_surrogate_key)

        return df[[
            "order_fact_id", "order_id", "user_key", "status",
            "gender", "created_date_key", "shipped_date_key",
            "delivered_date_key", "returned_date_key",
            "num_of_item", "order_type",
            "total_revenue", "total_cost", "gross_margin", "margin_percentage",
            "shipping_duration_days", "delivery_duration_days", "order_duration_days",
            "is_delayed"
        ]]
