$PROJECT_ID = "cloud-data-project-492514"
$BUCKET = "gs://etl-staging-0"
$DATASET = "staging"

Write-Host " Khởi động Apache Beam Dataflow Router (DirectRunner)..." -ForegroundColor Cyan

python src/dataflow/beam_router.py `
  --project $PROJECT_ID `
  --runner DirectRunner `
  --temp_location $BUCKET/tmp `
  --staging_location $BUCKET/staging `
  --pubsub_subscription projects/$PROJECT_ID/subscriptions/thelook-cdc-events-sub `
  --events_subscription projects/$PROJECT_ID/subscriptions/thelook_clickstream_events-sub `
  --bronze_dataset $DATASET `
  --gcs_output_prefix $BUCKET/raw

Write-Host " Đã đóng Dataflow Router." -ForegroundColor Green
