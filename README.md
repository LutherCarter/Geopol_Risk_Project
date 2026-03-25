# Quantitative Geopolitical Risk Assessment Engine

## Overview
The **Quantitative Geopolitical Risk Assessment Engine** is a data-driven framework designed to quantify regional geopolitical instability and model its cascading effects on global supply chain networks. By integrating multi-source macro indicators—such as conflict intensity, trade volatility, and currency fluctuations—this engine provides a probabilistic view of supply chain vulnerabilities.

## Core Features
* **Multi-Source Data Ingestion:** A robust SQL schema for ingesting, cleaning, and normalizing complex international datasets.
* **Composite Risk Scoring:** A Python-based assessment module that calculates weighted geopolitical instability scores for specific geographic regions.
* **Cascading Failure Modeling:** Monte Carlo simulations (using `networkx`) to model how regional disruptions propagate through interconnected supply chain nodes (e.g., factories, ports, distributors).
* **Vulnerability Identification:** Quantitative output highlighting the probability of node disruption across thousands of simulated scenarios.

## Technology Stack
* **Database:** SQL (PostgreSQL recommended)
* **Core Logic:** Python 3.x
* **Data Manipulation:** `pandas`, `numpy`
* **Network Simulation:** `networkx`

## Architecture
1.  **Data Layer (`database.sql`):** Tables for raw indicator data (conflict, currency, trade) and supply chain topology. Includes views for rolling averages and leading indicators.
2.  **Risk Engine (`Risk.py`):** Fetches cleaned data and applies a weighted algorithmic framework to generate a normalized 0-1 risk score per region.
3.  **Simulation Engine (`Monte_Carlo.py`):** Maps the supply chain as a directed graph. Uses the regional risk scores to trigger initial node failures, then calculates downstream propagation based on dependency weights.

## Usage (Prototype)
To run the prototype simulation locally:
1. Ensure Python 3.x is installed along with the required libraries (`pip install pandas numpy networkx`).
2. Execute the main Python script to generate simulated risk scores and run the Monte Carlo simulation.
```bash
python monte_carlo_sim.py
