import pandas as pd
from etl.transformers.utils import to_date_key

class DimDateTransformer:
    def transform(
        self,
        start_date="2019-01-01",
        end_date="2026-12-31"
    ) -> pd.DataFrame:
        """
        Generates a standardized date dimension table.
        """
        dates = pd.date_range(start=start_date, end=end_date)
        df = pd.DataFrame(dates, columns=["date"])
        
        # Surrogate key: YYYYMMDD format as integer
        df["date_key"] = to_date_key(df["date"])
        
        # Date attributes for analysis
        df["day"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["year"] = df["date"].dt.year
        df["quarter"] = df["date"].dt.quarter
        df["day_of_week"] = df["date"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([5, 6])
        df["day_name"] = df["date"].dt.day_name()
        df["month_name"] = df["date"].dt.month_name()
        
        return df
