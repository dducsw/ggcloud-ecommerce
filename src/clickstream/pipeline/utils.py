import logging
from datetime import datetime, timezone
from urllib.parse import unquote

from google.cloud import bigquery


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def to_timestamp_string(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def load_product_dimension_from_csv(csv_path: str) -> dict:
    import csv

    product_map = {}
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            product_map[int(row["id"])] = {
                "category": row.get("category"),
                "department": row.get("department"),
                "name": row.get("name"),
            }
    return product_map


def load_product_dimension_from_bigquery(project_id: str, dataset: str, table: str) -> dict:
    client = bigquery.Client(project=project_id)
    query = f"""
    SELECT
      id,
      category,
      department,
      name
    FROM `{project_id}.{dataset}.{table}`
    WHERE id IS NOT NULL
    """
    result = client.query(query).result()

    product_map = {}
    for row in result:
        product_map[int(row["id"])] = {
            "category": row.get("category"),
            "department": row.get("department"),
            "name": row.get("name"),
        }
    return product_map


def load_product_dimension(project_id: str, dataset: str, table: str, fallback_csv_path: str | None = None) -> dict:
    try:
        return load_product_dimension_from_bigquery(project_id, dataset, table)
    except Exception as exc:
        if fallback_csv_path:
            logging.warning(
                "Failed to load product dimension from BigQuery %s.%s.%s: %s. Falling back to CSV: %s",
                project_id,
                dataset,
                table,
                exc,
                fallback_csv_path,
            )
            return load_product_dimension_from_csv(fallback_csv_path)
        raise


def parse_uri(uri: str) -> dict:
    if not uri:
        return {"page_type": "unknown", "product_id": None}

    parts = [unquote(part) for part in uri.strip("/").split("/") if part]
    if not parts:
        return {"page_type": "home", "product_id": None}

    page_type = parts[0]
    product_id = None
    if page_type == "product" and len(parts) > 1 and parts[1].isdigit():
        product_id = int(parts[1])
    elif page_type in {"cancel", "return"}:
        page_type = "post_purchase"

    return {"page_type": page_type, "product_id": product_id}
