import pandas as pd
from etl.transformers.utils import generate_surrogate_key

class DimDistributionCentersTransformer:
    def transform(
        self,
        distribution_centers: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Transforms raw distribution centers data into the distribution center dimension.
        """
        df = distribution_centers.copy()
        
        # Generate Surrogate Key (Deterministic)
        df["dc_key"] = df["id"].apply(generate_surrogate_key)
        
        return df[[
            "dc_key", "id", "name", "latitude", "longitude"
        ]]
