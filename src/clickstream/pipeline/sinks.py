import apache_beam as beam
from apache_beam.io.gcp.bigquery import WriteToBigQuery


def write_bq(collection, table: str, schema: dict, extra_parameters=None):
    label = "Write_" + table.replace(":", "_").replace(".", "_")
    return collection | label >> WriteToBigQuery(
        table=table,
        schema=schema,
        write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
        create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
        additional_bq_parameters=extra_parameters or {},
        method=WriteToBigQuery.Method.STREAMING_INSERTS,
    )
