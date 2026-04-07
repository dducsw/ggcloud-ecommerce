# TheLook eCommerce: End-to-End Data Warehouse & BI Suite

This project implements a professional, modular **Data Warehouse (DWH)** and **Business Intelligence (BI)** solution for the "TheLook" eCommerce dataset. It features a robust Python ETL pipeline, a Star Schema architecture, and a domain-driven Streamlit dashboard, optimized for both local development and **Google Cloud Run** deployment.

---

## 🏗️ Architecture & Data Model

### Data Warehouse (Star Schema)
The project organizes data into a clean Star Schema for optimized analytical performance:
- **Fact Tables**: `fact_orders`, `fact_order_items`, `fact_events`, `fact_inventory`.
- **Dimension Tables**: `dim_users`, `dim_products`, `dim_distribution_centers`, `dim_date`.

### Hybrid Execution Model
- **Local Dev Mode**: Extracts from `data/*.csv`, transforms, and saves to `dwh/*.csv`. No GCP required.
- **Cloud Prod Mode**: Extracts from GCS (Parquet), transforms in-memory, and loads to BigQuery.

---

## 📁 Project Structure

```text
BTL-DWH/
├── src/
│   ├── etl/                # Modular ETL Pipeline
│   │   ├── extractors/     # Local & GCS extractors
│   │   ├── transformers/   # Domain-specific transformation logic
│   │   ├── loaders/        # Local & BigQuery loaders
│   │   ├── pipelines/      # Dimensions and Facts orchestration
│   │   └── config/         # Centralized settings
│   ├── dashboard/          # Domain-Driven BI Suite (Streamlit)
│   │   ├── app.py          # Main Landing Page
│   │   ├── pages/          # Multipage modules (Overview, Logistics)
│   │   ├── components/     # Domain components (Commerce, Events, AI)
│   │   ├── utils/          # Data providers (BQ + Local fallback)
│   │   └── Dockerfile      # Optimized for Cloud Run
│   ├── local_run.py        # Local ETL Execution script
│   └── main.py             # Cloud Run ETL API (Flask)
├── data/                   # Source CSV files (Kaggle)
├── dwh/                    # Local processed Data Warehouse (CSV)
├── docker-compose.yaml      # Full-stack local orchestration
├── .env                    # Environment variables & GCP config
└── requirements.txt        # Full project dependencies
```

---

## ⚙️ Setup & Configuration

1. **Environment Variables**: Create a `.env` file based on [.env.examle](file:///.env.examle):
   ```env
   GCP_PROJECT_ID=your-project-id
   DATASET_ID=thelook_dwh
   GCS_BUCKET_NAME=your-staging-bucket
   USE_LOCAL_DWH=false  # Set to true for Local CSV mode
   ```

2. **GCP Credentials**:
   Ensure you have a service account key or run `gcloud auth application-default login` for BigQuery access.

---

## 🚀 Execution Guide

### 1. Local Data Preparation (Quick Start)
To generate the local Data Warehouse files from raw CSVs:
```bash
python src/local_run.py
```
This will populate the `dwh/` folder with processed Fact and Dimension tables.

### 2. Running the Dashboard
The dashboard supports **Multipage** navigation and domain-driven components.

**Option A: Using Docker Compose (Recommended)**
This ignores local dependency conflicts and sets up everything automatically:
```bash
docker-compose up --build
```
Access at: [http://localhost:8501](http://localhost:8501)

**Option B: Manual Streamlit Run**
```bash
$env:USE_LOCAL_DWH="true"; streamlit run src/dashboard/app.py
```

### 3. ETL via Cloud Run / API
The project includes a Flask wrapper to trigger the ETL via HTTP (Postman/Cloud Scheduler):
```bash
python src/main.py
```

---

## ☁️ Deployment

### Google Cloud Run
Each service is containerized for easy deployment:
- **ETL**: Build root `Dockerfile` and deploy to Cloud Run.
- **Dashboard**: Build `src/dashboard/Dockerfile` and deploy to Cloud Run (Internal Port 8080).

```bash
# Example Dashboard Deployment
cd src/dashboard
docker build -t gcr.io/[PROJECT-ID]/dashboard .
docker push gcr.io/[PROJECT-ID]/dashboard
gcloud run deploy thelook-bi --image gcr.io/[PROJECT-ID]/dashboard --port 8080
```

---

## 🛠️ Tech Stack
- **Languages**: Python (Pandas, Plotly, Flask, Streamlit)
- **Infrastructure**: Google Cloud Platform (BigQuery, GCS, Cloud Run)
- **DevOps**: Docker, Docker Compose
