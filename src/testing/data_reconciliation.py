import os
import psycopg2
from google.cloud import bigquery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        database=os.getenv("POSTGRES_DB", "thelook_db"),
        user=os.getenv("POSTGRES_USER", "db_user"),
        password=os.getenv("POSTGRES_PASSWORD", "db_password")
    )

def get_bq_client():
    project_id = os.getenv("GCP_PROJECT_ID", "cloud-data-project-492514")
    return bigquery.Client(project=project_id)

def main():
    print("=== BẮT ĐẦU ĐỐI SOÁT DỮ LIỆU (RECONCILIATION) ===")
    
    # 1. Query PostgreSQL
    try:
        pg_conn = get_pg_connection()
        pg_cursor = pg_conn.cursor()
        
        # Count Orders
        pg_cursor.execute("SELECT COUNT(*) FROM demo.orders;")
        pg_orders_count = pg_cursor.fetchone()[0]
        
        # Count Order Items
        pg_cursor.execute("SELECT COUNT(*) FROM demo.order_items;")
        pg_order_items_count = pg_cursor.fetchone()[0]
        
        # Total Revenue (sum of sale_price in order_items)
        pg_cursor.execute("SELECT COALESCE(SUM(sale_price), 0) FROM demo.order_items;")
        pg_total_revenue = pg_cursor.fetchone()[0]
        
        print(f"[Source PostgreSQL] Orders Count: {pg_orders_count}")
        print(f"[Source PostgreSQL] Order Items Count: {pg_order_items_count}")
        print(f"[Source PostgreSQL] Total Revenue: ${pg_total_revenue:,.2f}")
        
    except Exception as e:
        print(f"Lỗi kết nối/truy vấn PostgreSQL: {e}")
        return
    finally:
        if 'pg_conn' in locals():
            pg_conn.close()

    # 2. Query BigQuery
    try:
        bq_client = get_bq_client()
        dataset_id = os.getenv("GOLD_DATASET_ID", "thelook_datawarehouse")
        project_id = bq_client.project
        
        bq_orders_query = f"SELECT COUNT(*) FROM `{project_id}.{dataset_id}.fact_orders`"
        bq_orders_count = list(bq_client.query(bq_orders_query).result())[0][0]
        
        bq_order_items_query = f"SELECT COUNT(*) FROM `{project_id}.{dataset_id}.fact_order_items`"
        bq_order_items_count = list(bq_client.query(bq_order_items_query).result())[0][0]
        
        bq_revenue_query = f"""
            SELECT COALESCE(SUM(revenue), 0) 
            FROM `{project_id}.{dataset_id}.fact_orders`
        """
        bq_total_revenue = list(bq_client.query(bq_revenue_query).result())[0][0]
        
        print(f"[Target BigQuery] fact_orders Count: {bq_orders_count}")
        print(f"[Target BigQuery] fact_order_items Count: {bq_order_items_count}")
        print(f"[Target BigQuery] Total Revenue: ${bq_total_revenue:,.2f}")
        
    except Exception as e:
        print(f"Lỗi kết nối/truy vấn BigQuery: {e}")
        return

    # 3. So sánh (Reconciliation)
    print("\n=== KẾT QUẢ ĐỐI SOÁT ===")
    
    # So sánh Orders
    order_diff = pg_orders_count - bq_orders_count
    if order_diff == 0:
        print("✅ Orders Count: KHỚP 100%")
    else:
        print(f"❌ Orders Count: LỆCH {order_diff} bản ghi (Source: {pg_orders_count}, Target: {bq_orders_count})")
        print("   -> Nguyên nhân có thể: CDC lag, data bị soft-delete, hoặc có duplicate chưa được xử lý triệt để.")

    # So sánh Order Items
    item_diff = pg_order_items_count - bq_order_items_count
    if item_diff == 0:
        print("✅ Order Items Count: KHỚP 100%")
    else:
        print(f"❌ Order Items Count: LỆCH {item_diff} bản ghi")

    # So sánh Doanh thu (có thể lệch nhỏ do rounding, cho phép sai số $0.01)
    revenue_diff = float(pg_total_revenue) - float(bq_total_revenue)
    if abs(revenue_diff) < 0.02:
        print("✅ Total Revenue: KHỚP 100%")
    else:
        print(f"❌ Total Revenue: LỆCH ${abs(revenue_diff):,.2f}")

if __name__ == "__main__":
    main()
