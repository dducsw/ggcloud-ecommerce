"""
Check all Parquet files in GCS for schema mismatches on timestamp columns.
"""
import pyarrow.parquet as pq
import pyarrow.fs as pafs
import sys

gcs = pafs.GcsFileSystem()

PARTITIONS = [
    "etl-staging-0/raw/order_items/date=2026-05-03",
    "etl-staging-0/raw/orders/date=2026-05-03",
    "etl-staging-0/raw/users/date=2026-05-03",
    "etl-staging-0/raw/products/date=2026-05-03",
    "etl-staging-0/raw/inventory_items/date=2026-05-03",
]

bad_files = []

for partition in PARTITIONS:
    try:
        fs_info = gcs.get_file_info(pafs.FileSelector(partition, recursive=True))
        parquet_files = [f.path for f in fs_info if f.path.endswith(".parquet")]
    except Exception as e:
        print(f"Cannot list {partition}: {e}")
        continue

    for path in parquet_files:
        try:
            schema = pq.read_schema(path, filesystem=gcs)
            ts_cols = [f for f in schema if f.name.endswith("_at")]
            issues = [f"{f.name}={f.type}" for f in ts_cols
                      if str(f.type) not in ("int64", "null", "timestamp[us]", "timestamp[us, tz=UTC]")]
            fname = path.split("/")[-1]
            if issues:
                print(f"  BAD  gs://{path}: {', '.join(issues)}")
                bad_files.append(f"gs://{path}")
            else:
                ts_summary = ", ".join(f"{f.name}={f.type}" for f in ts_cols)
                print(f"  OK   gs://{path}: [{ts_summary}]")
        except Exception as e:
            print(f"  ERR  gs://{path}: {e}")
            bad_files.append(f"gs://{path}")

print()
if bad_files:
    print(f"\n=== {len(bad_files)} BAD FILE(S) FOUND ===")
    for f in bad_files:
        print(f"  {f}")
    print("\nTo delete them, run:")
    print(f'  gcloud storage rm {" ".join(bad_files)}')
else:
    print("=== All files OK ===")
