import pandas as pd
import hashlib

def generate_surrogate_key(value):
    """
    Generates a deterministic MD5 hex string for a given value.
    Used for creating surrogate keys from natural IDs.
    """
    return hashlib.md5(str(value).encode()).hexdigest()

def to_date_key(series):
    """
    Converts a datetime series to a YYYYMMDD integer.
    Handles NaT by returning 0.
    """
    if not pd.api.types.is_datetime64_any_dtype(series):
        dt_series = pd.to_datetime(series, format="mixed", utc=True, errors="coerce")
    else:
        dt_series = series
        
    date_str = dt_series.dt.strftime("%Y%m%d")
    return pd.to_numeric(date_str, errors="coerce").fillna(0).astype(int)
