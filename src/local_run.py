import sys
import os

# Append the current directory to sys.path to allow absolute imports of the etl package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from etl.extractors.local_extractor import LocalExtractor
from etl.loaders.local_loader import LocalLoader
from etl.pipelines.dimensions_pipeline import DimensionsPipeline
from etl.pipelines.facts_pipeline import FactsPipeline

def run_local_etl():
    """
    Main entry point for the local ETL flow.
    Reads from local CSV files in 'data/' and saves results to 'dwh/' folder.
    """
    try:
        print("🚀 Starting Local ETL Pipeline...")
        
        # 1. Initialize extractor and loader
        extractor = LocalExtractor()
        loader = LocalLoader()
        
        # 2. Run Dimensions Pipeline
        # Extracts from data/ (CSV), Transforms in memory, Loads to dwh/ (CSV)
        print("\n--- Step 1: Running Dimensions Pipeline ---")
        dim_pipeline = DimensionsPipeline()
        dim_pipeline.run(extractor, loader)
        
        # 3. Run Facts Pipeline
        # Extracts from data/ (CSV), Transforms in memory, Loads to dwh/ (CSV)
        # Note: Large tables like 'events' are processed in chunks.
        print("\n--- Step 2: Running Facts Pipeline ---")
        fact_pipeline = FactsPipeline()
        fact_pipeline.run(extractor, loader)
        
        print("\n✅ Local ETL Pipeline completed successfully!")
        print(f"Results are available in: {os.path.abspath('dwh/')}")
        
    except Exception as e:
        print(f"❌ Local ETL Pipeline failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_local_etl()
