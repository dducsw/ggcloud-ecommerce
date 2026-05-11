FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8080 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire dashboard source
COPY . .

# Expose port (Cloud Run sets PORT env var)
EXPOSE 8080

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health

# Run Streamlit
CMD ["streamlit", "run", "app.py"]
