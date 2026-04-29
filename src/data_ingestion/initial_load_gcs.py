import os
import sys
import time
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import create_engine, text
from google.cloud import storage
from dotenv import load_dotenv

# Force UTF-8 output để tránh lỗi UnicodeEncodeError trên Windows (terminal cp1252)
sys.stdout.reconfigure(encoding='utf-8')

# Tải biến môi trường từ file .env ở thư mục gốc
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
dotenv_path = os.path.join(root_dir, '.env')
load_dotenv(dotenv_path)

# Cấu hình kết nối PostgreSQL
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5433")
PG_USER = os.getenv("PG_USER", "db_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "db_password")
PG_DB_NAME = os.getenv("PG_DB_NAME", "thelook_db")
PG_SCHEMA = os.getenv("PG_SCHEMA", "demo")

# Cấu hình GCS
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCS_BRONZE_BUCKET = os.getenv("GCS_BRONZE_BUCKET")
GCS_BRONZE_PREFIX = os.getenv("GCS_BRONZE_PREFIX", "bronze/cdc").rstrip("/")

# Thư mục tạm để lưu file parquet trước khi upload
TMP_DIR = os.path.join(root_dir, "scratch", "initial_load")

# Danh sách các bảng thuộc Cold Path (CDC lên GCS)
TABLES = [
    "users",
    "products",
    "distribution_centers",
    "inventory_items",
    "orders",
    "order_items"
]

def get_pg_engine():
    # Sử dụng psycopg2 driver
    connection_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
    return create_engine(connection_url)

def upload_to_gcs(bucket_name, source_file_path, destination_blob_name):
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path)
    print(f" Đã upload thành công lên: gs://{bucket_name}/{destination_blob_name}")

def purge_gcs_prefix(bucket_name, prefix):
    """Xóa tất cả các file trong một prefix để dọn dẹp dữ liệu cũ lỗi."""
    try:
        client = storage.Client(project=GCP_PROJECT_ID)
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=prefix))
        if blobs:
            bucket.delete_blobs(blobs)
            print(f" 🔥 Đã dọn dẹp {len(blobs)} file cũ tại: gs://{bucket_name}/{prefix}")
    except Exception as e:
        print(f" ⚠️ Cảnh báo khi dọn dẹp GCS: {e}")

def main():
    print(f"Bắt đầu quy trình Initial Full Load tới GCS bucket: {GCS_BRONZE_BUCKET}")
    if not GCS_BRONZE_BUCKET:
        raise ValueError("Lỗi: GCS_BRONZE_BUCKET chưa được cấu hình trong file .env")

    engine = get_pg_engine()
    now_utc = datetime.now(timezone.utc)
    cdc_timestamp_ms = int(now_utc.timestamp() * 1000)
    
    date_str = now_utc.strftime("%Y-%m-%d")
    hour_str = now_utc.strftime("%H")
    processing_time = now_utc.strftime("%Y%m%d%H%M%S")

    os.makedirs(TMP_DIR, exist_ok=True)

    for table in TABLES:
        print(f"\n--- Đang xử lý bảng: {table} ---")
        
        # dbt source khai báo bảng distribution_centers với identifier là dist_centers
        target_table_name = table
        if table == "distribution_centers":
            target_table_name = "dist_centers"

        # 1. Đọc dữ liệu từ PostgreSQL
        try:
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT * FROM {PG_SCHEMA}.{table}"))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
        except Exception as e:
            print(f"❌ Lỗi khi đọc bảng {table}: {e}")
            continue

        # Đảm bảo các cột thời gian được định dạng đúng để tránh lỗi dải TIMESTAMP trên BigQuery
        date_cols = [col for col in df.columns if any(suffix in col for suffix in ["_at", "_date", "timestamp"])]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        if df.empty:
            print(f"Bảng {table} không có dữ liệu. Bỏ qua.")
            continue

        # 1.5 Xử lý missing created_at để tránh lỗi dbt test
        if 'created_at' in df.columns:
            df['created_at'] = df['created_at'].fillna(now_utc)

        print(f" Đã load {len(df)} dòng từ PostgreSQL.")

        # 2. Bổ sung CDC Metadata để tương thích với dbt stg models
        df['cdc_operation'] = 'c'
        df['cdc_timestamp'] = cdc_timestamp_ms

        # 3. Chuyển sang định dạng Parquet (Apache Arrow)
        arrow_table = pa.Table.from_pandas(df)
        local_filename = os.path.join(TMP_DIR, f"part-{processing_time}_{target_table_name}.parquet")
        pq.write_table(arrow_table, local_filename, coerce_timestamps='us', allow_truncated_timestamps=True)

        # 4. Định tuyến đường dẫn chuẩn Hive Partition trên GCS
        # Sử dụng tên file chuẩn (part-00000...) và cố định để ghi đè khi chạy lại
        gcs_blob_name = f"{GCS_BRONZE_PREFIX}/{target_table_name}/date={date_str}/hour={hour_str}/part-00000-initial-load.parquet"

        # 5. Dọn dẹp dữ liệu cũ trên GCS của bảng này để tránh BigQuery đọc nhầm file lỗi
        table_path_prefix = f"{GCS_BRONZE_PREFIX}/{target_table_name}/"
        purge_gcs_prefix(GCS_BRONZE_BUCKET, table_path_prefix)

        # 6. Upload lên GCS
        print(f" Đang upload file Parquet...")
        upload_to_gcs(GCS_BRONZE_BUCKET, local_filename, gcs_blob_name)
        
        # Dọn dẹp file tạm
        os.remove(local_filename)

    print("\n Khởi tạo dữ liệu (Initial Full Load) hoàn tất!")

if __name__ == "__main__":
    main()
