from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions, StandardOptions
from apache_beam.transforms import trigger
import apache_beam as beam
from apache_beam.transforms.combiners import Latest
from apache_beam.transforms.periodicsequence import PeriodicImpulse

from src.clickstream.pipeline.schemas import AGGREGATE_SCHEMA, DEADLETTER_SCHEMA, RAW_EVENTS_SCHEMA, SESSION_SCHEMA
from src.clickstream.pipeline.sinks import write_bq
from src.clickstream.pipeline.transforms import (
    DeduplicateEventsDoFn,
    EnrichEventDoFn,
    ParseValidateDoFn,
    build_session_metric,
    create_aggregate_record,
    to_aggregate_key,
)
from src.clickstream.pipeline.utils import load_product_dimension, utc_now


def build_pipeline_options(args, pipeline_args):
    options = PipelineOptions(
        pipeline_args,
        project=args.project,
        region=args.region,
        runner=args.runner,
        temp_location=args.temp_location,
        staging_location=args.staging_location,
        streaming=True,
    )
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True
    return options


def build_window_kwargs(args):
    return {
        "allowed_lateness": args.allowed_lateness_seconds,
        "trigger": trigger.AfterWatermark(
            early=trigger.AfterProcessingTime(args.early_firing_delay_seconds),
            late=trigger.AfterCount(args.late_firing_count),
        ),
        "accumulation_mode": trigger.AccumulationMode.ACCUMULATING,
    }


def run_pipeline(args, pipeline_args):
    options = build_pipeline_options(args, pipeline_args)
    raw_table_spec = f"{args.project}:{args.dataset}.{args.raw_table}"
    deadletter_table_spec = f"{args.project}:{args.dataset}.{args.deadletter_table}"
    aggregate_table_spec = f"{args.project}:{args.dataset}.{args.aggregate_table}"
    session_table_spec = f"{args.project}:{args.dataset}.{args.session_table}"
    window_kwargs = build_window_kwargs(args)

    with beam.Pipeline(options=options) as pipeline:
        initial_product_map = load_product_dimension(
            project_id=args.product_lookup_project or args.project,
            dataset=args.product_lookup_dataset,
            table=args.product_lookup_table,
            fallback_csv_path=args.products_csv,
        )
        refresh_interval_seconds = args.product_refresh_minutes * 60

        # Note: PeriodicImpulse can be unstable in some DirectRunner versions for streaming.
        # For local testing, we use a single load. In production (Dataflow), we can re-enable refresh.
        product_side_input = beam.pvalue.AsSingleton(
            pipeline
            | "CreateInitialProductMap" >> beam.Create([initial_product_map])
        )

        parsed = (
            pipeline
            | "ReadClickstreamPubSub" >> beam.io.ReadFromPubSub(subscription=args.events_subscription)
            | "ParseValidate"
            >> beam.ParDo(ParseValidateDoFn()).with_outputs(ParseValidateDoFn.DEADLETTER_TAG, main="valid")
        )

        deduplicated_events = (
            parsed.valid
            | "KeyByEventId" >> beam.Map(lambda row: (str(row["event_id"]), row))
            | "DeduplicateByState" >> beam.ParDo(DeduplicateEventsDoFn(args.dedup_ttl_minutes * 60))
        )

        enriched_events = (
            deduplicated_events
            | "EnrichEvents" >> beam.ParDo(EnrichEventDoFn(), product_map=product_side_input)
        )

        write_bq(
            parsed.deadletter,
            deadletter_table_spec,
            DEADLETTER_SCHEMA,
            extra_parameters={"timePartitioning": {"type": "DAY", "field": "failed_at"}},
        )

        write_bq(
            enriched_events,
            raw_table_spec,
            RAW_EVENTS_SCHEMA,
            extra_parameters={
                "timePartitioning": {"type": "DAY", "field": "event_date"},
                "clustering": {"fields": ["event_type", "traffic_source", "browser"]},
            },
        )

        windowed_events = (
            enriched_events
            | "Window5Minutes"
            >> beam.WindowInto(beam.window.FixedWindows(300), **window_kwargs)
        )

        realtime_aggregates = (
            windowed_events
            | "AggregateKey" >> beam.Map(lambda row: (to_aggregate_key(row), row))
            | "GroupAggregateRows" >> beam.GroupByKey()
            | "BuildAggregateRows" >> beam.Map(create_aggregate_record)
        )

        write_bq(
            realtime_aggregates,
            aggregate_table_spec,
            AGGREGATE_SCHEMA,
            extra_parameters={
                "timePartitioning": {"type": "DAY", "field": "event_date"},
                "clustering": {"fields": ["traffic_source", "event_type", "page_type"]},
            },
        )

        session_events = (
            enriched_events
            | "KeyBySessionId" >> beam.Map(lambda row: (row["session_id"], row))
        )

        session_metrics = (
            session_events
            | "SessionWindow"
            >> beam.WindowInto(beam.window.Sessions(args.session_gap_minutes * 60), **window_kwargs)
            | "GroupSessionRows" >> beam.GroupByKey()
            | "BuildSessionMetrics" >> beam.Map(build_session_metric)
            | "DropNullSessions" >> beam.Filter(lambda row: row is not None)
        )

        write_bq(
            session_metrics,
            session_table_spec,
            SESSION_SCHEMA,
            extra_parameters={
                "timePartitioning": {"type": "DAY", "field": "session_date"},
                "clustering": {"fields": ["traffic_source", "browser", "purchased"]},
            },
        )
