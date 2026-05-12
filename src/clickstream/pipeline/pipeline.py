from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions, StandardOptions, GoogleCloudOptions, WorkerOptions
from apache_beam.transforms import trigger
import apache_beam as beam
import logging
import os

from src.clickstream.pipeline.schemas import AGGREGATE_SCHEMA, DEADLETTER_SCHEMA, RAW_EVENTS_SCHEMA, SESSION_SCHEMA
from src.clickstream.pipeline.sinks import write_bq
from src.clickstream.pipeline.transforms import (
    DeduplicateEventsDoFn,
    EnrichEventDoFn,
    LogCountDoFn,
    ParseValidateDoFn,
    build_session_metric,
    create_aggregate_record,
    to_aggregate_key,
)
from src.clickstream.pipeline.utils import load_product_dimension


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
    
    # Standard Options
    options.view_as(StandardOptions).streaming = True
    
    # Google Cloud Options
    google_cloud_options = options.view_as(GoogleCloudOptions)
    google_cloud_options.job_name = args.job_name
    google_cloud_options.staging_location = args.staging_location
    google_cloud_options.temp_location = args.temp_location
    
    # Worker Options
    worker_options = options.view_as(WorkerOptions)
    worker_options.max_num_workers = args.max_workers
    worker_options.machine_type = args.worker_machine_type
    worker_options.autoscaling_algorithm = args.autoscaling_algorithm
    worker_options.use_public_ips = args.use_public_ips
    
    # Performance & Setup
    setup_opts = options.view_as(SetupOptions)
    setup_opts.save_main_session = True
    # Ship the local 'src' package to Dataflow workers via setup.py.
    # Without this, workers raise: ModuleNotFoundError: No module named 'src'
    setup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "setup.py")
    setup_opts.setup_file = os.path.normpath(setup_file)
    # Enable Dataflow Streaming Engine (Best Practice for streaming)
    # This reduces worker CPU usage by offloading windowing/shuffling to GCP backend.
    options.view_as(GoogleCloudOptions).enable_streaming_engine = True
    
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

        # Product dimension is intentionally a startup snapshot for deterministic enrichment.
        # Restart the job when the product lookup table needs to be refreshed.
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
            | "LogEnriched" >> beam.ParDo(LogCountDoFn("EnrichedEvents", interval=100))
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
