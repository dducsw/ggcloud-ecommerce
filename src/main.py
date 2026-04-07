import os
from flask import Flask, jsonify, request
from etl.extractors.thelook_extractor import TheLookExtractor
from etl.loaders.bigquery_loader import BigQueryLoader
from etl.pipelines.dimensions_pipeline import DimensionsPipeline
from etl.pipelines.facts_pipeline import FactsPipeline

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def run_full_etl():
    """
    HTTP entry point for Cloud Run. Triggers the full ETL pipeline.
    Use ?skip_upload=true to skip the local-to-GCS upload step.
    """
    try:
        skip_upload = request.args.get("skip_upload", "false").lower() == "true"
        print(f"Starting ETL Pipeline (skip_upload={skip_upload})...")
        
        extractor = TheLookExtractor()
        loader = BigQueryLoader()

        # 0. Initial Upload (Local to GCS)
        if not skip_upload:
            print("Step 0: Converting and uploading local data/ to GCS bucket as Parquet...")
            extractor.upload_local_to_gcs()
        else:
            print("Step 0: Skipped (Using existing files on GCS).")

        # 1. Dimensions Pipeline
        # Extracts from GCS (Parquet), Transforms in memory, Loads to BigQuery
        print("Step 1: Running Dimensions Pipeline (Staging: Parquet)...")
        dim_pipeline = DimensionsPipeline()
        dim_pipeline.run(extractor, loader)

        # 2. Facts Pipeline
        # Extracts from GCS (Parquet), Transforms in memory, Loads to BigQuery
        # Note: fact_events uses batched Parquet reading to save RAM.
        print("Step 2: Running Facts Pipeline (Staging: Parquet)...")
        fact_pipeline = FactsPipeline()
        fact_pipeline.run(extractor, loader)

        return jsonify({
            "status": "success",
            "message": "Full ETL Pipeline (Local -> GCS Parquet -> BigQuery) completed successfully."
        }), 200
    except Exception as e:
        print(f"Full ETL Pipeline failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    # Local Testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
