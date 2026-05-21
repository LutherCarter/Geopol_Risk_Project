# Geopolitical Risk Engine

A modular, containerized Geopolitical Risk Assessment Engine designed to ingest real-world data, perform spatial and time-decay risk modeling, and visualize supply chain vulnerabilities in a high-performance interactive dashboard.

## Overview

The engine integrates disparate global data sources—such as live currency fluctuations and conflict event timelines—to assess risk factors affecting global supply chain networks. By using Monte Carlo simulations alongside DBSCAN clustering and spatial bounding filters, it calculates probabilistic failure rates across critical logistical nodes. 

### Recent Major Updates
The application recently underwent a massive structural and mathematical overhaul:
1. **"Command Center" UI Rebuild**: Completely stripped out the legacy Plotly Dash frontend, replacing it with a lightning-fast, highly customizable Vanilla HTML/JS/CSS web application powered by **Vis-Network**. It features deep dark-mode aesthetics, glassmorphism, high-contrast dynamic node coloring, and responsive UI controls.
2. **FastAPI Backend Migration**: The python backend has been upgraded from a rigid Dash application to a lightweight, async-ready **FastAPI** interface that natively serves the static frontend assets and provides a pure REST API for simulation runs.
3. **Rigorous Probability Math**: The Monte Carlo risk cascading calculations were rebuilt to utilize mathematically rigorous independent probability aggregation (via vectorized logarithmic dot products) instead of flawed linear additions.
4. **Geography-Accurate Spatial Queries**: PostGIS `ST_DWithin` queries have been upgraded to utilize accurate `::geography` mapping, ensuring buffer calculations strictly adhere to meter-level distances factoring in the curvature of the earth.
5. **Dynamic Bounding Box Tracking**: The DBSCAN anomaly detection models now actively utilize the UI-provided `ST_MakeEnvelope` coordinates, scanning for conflict clusters precisely within your selected viewport.

## System Architecture

The project is structured into three main microservices running via Docker Compose:

1. **Spatial Database (`postgres-postgis`)**
   - A PostgreSQL instance extended with PostGIS.
   - Handles spatial calculations, geometry/geography types, and exponential risk decay formulas directly via specialized SQL functions.
   - Enforces coordinate bounds and serves as the single source of truth.

2. **Orchestration & ETL (`prefect-agent`)**
   - Powered by Prefect for robust workflow execution.
   - **Daily FX Ingestion**: Integrates with [Polygon.io](https://polygon.io/) to pull and persist currency volatility indicators.
   - **Hourly ACLED Ingestion**: Simulates API polling from ACLED to map out global conflict zones, weighted by normalized intensity indexes.
   
3. **Interactive Web UI & API (`dashboard`)**
   - **FastAPI**: Serves the REST interface (`/api/run_simulation`).
   - **Frontend**: A gorgeous "Command Center" static HTML/JS/CSS site serving dynamic Vis-Network graphs.
   - **Vectorized Monte Carlo**: Matrix-based cascading network failure calculations.

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
   From the root of the project directory, bring up the full stack. This will build the Python microservices and initialize the PostGIS database.
   ```bash
   docker compose down
   docker compose build
   docker compose up -d
   ```
   *Note: On the first launch, PostGIS will initialize its schemas using the `/db/init_postgis.sql` configurations.*

4. **Access the Command Center**
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

To view the logs for the FastAPI backend:
```bash
docker compose logs -f dash-app
```
