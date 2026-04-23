import pandas as pd
from etl.transformers.utils import generate_surrogate_key, to_date_key

class FactEventsTransformer:
    def transform(
        self,
        events: pd.DataFrame,
        dim_users: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw digital event logs and links them to user surrogate keys.
        """
        df = events.copy()

        # --- Layer 1: Data Cleaning ---
        df["event_type"] = df["event_type"].str.strip().str.lower()
        df["browser"] = df["browser"].str.strip().fillna("Other")
        df["traffic_source"] = df["traffic_source"].str.strip().fillna("Other")
        df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", utc=True).dt.tz_localize(None)
        
        # Standardize date key for partitioning/joins
        df["created_date_key"] = to_date_key(df["created_at"])

        # Lookup user surrogate key from dimensions
        df = df.merge(dim_users[["user_key", "user_id"]], on="user_id", how="left")
        
        # --- Layer 3: Business Logic ---
        # Flag conversion/purchase events
        df["is_checkout_event"] = df["event_type"] == "purchase"
        
        # Generate Surrogate Key (Deterministic)
        df["event_fact_id"] = df["id"].apply(generate_surrogate_key)
        
        # Rename raw ID for clarity in DWH
        df = df.rename(columns={"id": "event_id"})

        return df[[
            "event_fact_id", "event_id", "user_key", "sequence_number",
            "session_id", "created_date_key", "ip_address", "city",
            "state", "postal_code", "browser", "traffic_source",
            "uri", "event_type", "is_checkout_event"
        ]]
