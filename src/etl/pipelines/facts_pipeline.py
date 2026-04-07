from etl.transformers.fact_orders import FactOrdersTransformer
from etl.transformers.fact_order_items import FactOrderItemsTransformer
from etl.transformers.fact_events import FactEventsTransformer
from etl.transformers.fact_inventory import FactInventoryTransformer

class FactsPipeline:
    def run(self, extractor, loader):
        """
        Orchestrates the fact layer. 
        Note: Special chunked handling for the large events table.
        """
        print("--- Starting Facts Pipeline ---")
        
        # 1. Load DIM data needed for lookups
        print("Loading dimensions from BQ for lookups...")
        dim_users = loader.read("dim_users")
        dim_products = loader.read("dim_products")
        dim_dcs = loader.read("dim_distribution_centers")

        # 2. Extract Raw Data
        print("Extracting raw data from source...")
        raw_orders = extractor.get_orders()
        raw_order_items = extractor.get_order_items()
        raw_inventory = extractor.get_inventory_items()

        # 3. Transform and Load (Standard Tables)
        print("Processing standard fact tables...")
        
        # fact_orders now calculates financials using order_items and inventory_items
        loader.load(FactOrdersTransformer().transform(
            raw_orders, raw_order_items, raw_inventory, dim_users
        ), "fact_orders")

        loader.load(FactInventoryTransformer().transform(
            raw_inventory, dim_products, dim_dcs
        ), "fact_inventory")

        loader.load(FactOrderItemsTransformer().transform(
            raw_order_items, raw_inventory, dim_users, dim_products, dim_dcs
        ), "fact_order_items")

        # 4. Chunked Processing for fact_events
        print("Processing large events table with chunking...")
        transformer_events = FactEventsTransformer()
        first_chunk = True
        
        for chunk_df in extractor.get_events_chunks(chunk_size=100000):
            transformed_chunk = transformer_events.transform(chunk_df, dim_users)
            write_mode = "WRITE_TRUNCATE" if first_chunk else "WRITE_APPEND"
            loader.load(transformed_chunk, "fact_events", write_mode=write_mode)
            first_chunk = False

        print("--- Facts Pipeline Completed ---")
