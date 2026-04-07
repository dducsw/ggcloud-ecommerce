from etl.transformers.dim_date import DimDateTransformer
from etl.transformers.dim_distribution_centers import DimDistributionCentersTransformer
from etl.transformers.dim_users import DimUsersTransformer
from etl.transformers.dim_products import DimProductsTransformer

class DimensionsPipeline:
    def run(self, extractor, loader):
        """
        Orchestrates the dimension layer.
        Execution order reflects dependencies (products need DCs).
        """
        print("--- Starting Dimensions Pipeline ---")
        
        # 1. Extract raw data once
        raw_users = extractor.get_users()
        raw_orders = extractor.get_orders()
        raw_products = extractor.get_products()
        raw_dcs = extractor.get_distribution_centers()

        # 2. Transform and Load In-Memory (No dependencies)
        print("Transforming dim_date...")
        loader.load(DimDateTransformer().transform(), "dim_date")
        
        print("Transforming dim_distribution_centers...")
        dim_dcs_df = DimDistributionCentersTransformer().transform(raw_dcs)
        loader.load(dim_dcs_df, "dim_distribution_centers")
        
        print("Transforming dim_users...")
        loader.load(DimUsersTransformer().transform(raw_users, raw_orders), "dim_users")

        # 3. Transform and Load with Dependencies
        print("Transforming dim_products (depends on DCs)...")
        # Reuse dim_dcs_df for lookup instead of re-reading from BQ (more efficient)
        loader.load(DimProductsTransformer().transform(raw_products, dim_dcs_df), "dim_products")
        
        print("--- Dimensions Pipeline Completed ---")
