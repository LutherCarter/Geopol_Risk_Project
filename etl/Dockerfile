FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for psycopg2 and geospatial libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prefect_flows.py .

CMD ["python", "prefect_flows.py"]
