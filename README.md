# Geopolitical Risk Engine

A modular, containerized Geopolitical Risk Assessment Engine designed to ingest real-world data, perform spatial and time-decay risk modeling, and visualize supply chain vulnerabilities in a high-performance interactive dashboard.

## Overview

The engine integrates disparate global data sources—such as live currency fluctuations and conflict event timelines—to assess risk factors affecting global supply chain networks. By using Monte Carlo simulations alongside DBSCAN clustering and spatial bounding filters, it calculates probabilistic failure rates across critical logistical nodes. 

## System Architecture

The project is structured into three main microservices running via Docker Compose:

1. **Spatial Database (`postgres-postgis`)**
   - A PostgreSQL instance extended with PostGIS.
   - Handles spatial calculations, geometry types (Points, LineStrings), and exponential risk decay formulas directly via specialized SQL functions.
   - Enforces coordinate bounds and serves as the single source of truth.

2. **Orchestration & ETL (`prefect-agent`)**
   - Powered by Prefect for robust workflow execution.
   - **Daily FX Ingestion**: Integrates with [Polygon.io](https://polygon.io/) to pull and persist currency volatility indicators.
   - **Hourly ACLED Ingestion**: Simulates API polling from ACLED to map out global conflict zones, weighted by normalized intensity indexes.
   
3. **Interactive Web UI (`dash-app`)**
   - A Plotly Dash frontend providing a dark-mode "Command Center" aesthetic.
   - **Vectorized Monte Carlo Controls**: Adjust volatility shock percentages dynamically to crash-test supply chain nodes.
   - **Viewport Bounding Focus**: Leverages `ST_MakeEnvelope` querying to filter analysis regionally (Global, Americas, EMEA, APAC).
   - **Pattern Detection**: Showcases automated alerts powered by Python's scikit-learn DBSCAN models tracking high-intensity anomaly clusters in real-time.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- A [Polygon.io](https://polygon.io/) API Key (defaults to `demo` otherwise)

## Getting Started

1. **Clone the Repository**
   ```bash
   git clone https://github.com/your-username/Geopol_Engine.git
   cd Geopol_Engine
   ```

2. **Environment Variables**
   Export your specific API keys if you wish to bypass the simulation defaults. 
   ```bash
   export POLYGON_KEY="your_api_key_here"
   ```

3. **Build & Deploy**
   From the root of the project directory, bring up the full stack:
   ```bash
   docker compose up --build -d
   ```
   *Note: On the first launch, PostGIS will initialize its schemas using the `/db/init_postgis.sql` configurations.*

4. **Access the Dashboard**
   Once the containers are healthy and Prefect finishes its initial ETL burst, open a browser and navigate to:
   ```text
   http://localhost:8050
   ```

## Local Development

Each service is containerized in its own context folder (`/db`, `/etl`, `/dashboard`), complete with individual `requirements.txt` configurations for isolated development. 

To view live debug logs of the background ETL jobs running in the Prefect agent module:
```bash
docker compose logs -f prefect-agent
```
