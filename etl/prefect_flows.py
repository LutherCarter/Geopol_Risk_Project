from prefect import flow, task
import time
import requests
import pandas as pd
import os
import random
from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
db_user = os.getenv("POSTGRES_USER", "admin")
db_password = os.getenv("POSTGRES_PASSWORD", "password")
db_host = os.getenv("DB_HOST", "postgres-postgis")
db_port = "5432"
db_name = os.getenv("POSTGRES_DB", "risk_db")

db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

@task(retries=3, retry_delay_seconds=10)
def fetch_currency_pair(pair_symbol, api_key):
    """
    Simulates fetching currency pair data from Polygon.io
    In a real scenario, this would use requests to hitting the API.
    """
    # Simulated API call for polygon
    print(f"Fetching {pair_symbol} data from Polygon...")
    return {
        "currency_code": pair_symbol.replace("USD/", ""),
        "record_date": datetime.today().date(),
        "exchange_rate_to_usd": random.uniform(1.0, 150.0),
        "daily_volatility": random.uniform(0.01, 0.05),
        "latitude": random.uniform(-90, 90), # Simulated central coord of currency region
        "longitude": random.uniform(-180, 180)
    }

@task
def store_currency_data(data_batch, engine):
    """Stores the downloaded data, enforcing coordinate limits."""
    if not data_batch:
        return
        
    df = pd.DataFrame(data_batch)
    
    # 1. Hard Coordinate Limits (ETL Data Integrity)
    # Filter out any invalid coordinates before PostGIS injection
    valid_data = df[
        (df['latitude'] >= -90) & (df['latitude'] <= 90) &
        (df['longitude'] >= -180) & (df['longitude'] <= 180)
    ]
    
    if valid_data.empty:
        print("All fetched currency coordinates were invalid. Skipping insertion.")
        return
        
    print(f"Inserting {len(valid_data)} valid currency records.")
    
    # Convert lat/long to WKT for PostGIS GEOMETRY(Point, 4326)
    valid_data['location'] = valid_data.apply(
        lambda row: f"POINT({row['longitude']} {row['latitude']})", axis=1
    )
    
    # Insert via SQL
    with engine.connect() as conn:
        for _, row in valid_data.iterrows():
            query = f"""
                INSERT INTO currency_fluctuations 
                (currency_code, location, record_date, exchange_rate_to_usd, daily_volatility, cleaned)
                VALUES 
                ('{row['currency_code']}', ST_GeomFromText('{row['location']}', 4326), 
                '{row['record_date']}', {row['exchange_rate_to_usd']}, {row['daily_volatility']}, TRUE)
            """
            conn.execute(text(query))
        conn.commit()

@flow(name="Daily_FX_Ingestion")
def ingest_currencies():
    """Fetches currency data, respecting Polygon's 5 calls/min limit"""
    pair_list = ["USD/CNY", "EUR/USD", "USD/TWD", "USD/BRL", "USD/INR", "USD/JPY", "USD/GBP"]
    api_key = os.getenv("POLYGON_API_KEY", "demo")
    engine = create_engine(db_url)
    
    all_data = []
    
    for i in range(0, len(pair_list), 5):
        batch_symbols = pair_list[i:i+5]
        batch_data = []
        for pair in batch_symbols:
            # Prefect handles the execution and retries
            data = fetch_currency_pair(pair, api_key)
            batch_data.append(data)
            
        store_currency_data(batch_data, engine)
        
        # Strict 65-second buffer to respect the 5/min limit if there are more pairs to process
        if i + 5 < len(pair_list):
            print("Batch of 5 complete. Waiting 65 seconds for Polygon rate limits...")
            time.sleep(65) 

@task(retries=2)
def fetch_acled_events():
    """Simulates pulling hourly ACLED data"""
    print("Fetching ACLED data for the past hour...")
    # Simulated data, some intentional out of bounds to trigger the filter
    events = []
    for _ in range(10):
        lat = random.uniform(-100, 100) # Could be invalid (<-90 or >90)
        lon = random.uniform(-200, 200) # Could be invalid
        events.append({
            "event_date": datetime.today().date(),
            "fatalities": random.randint(0, 50),
            "event_type": random.choice(["Riots", "Battles", "Protests", "Explosions"]),
            "latitude": lat,
            "longitude": lon
        })
    return events
    
@task
def process_and_store_acled(events, engine):
    """Processes ACLED events, validates BBOX, scales R0 based on fatalities."""
    if not events: return
    
    df = pd.DataFrame(events)
    
    # 1. Hard Coordinate Limits (ETL Data Integrity)
    # Validates and cleans erroneous locations like 99.999
    valid_data = df[
        (df['latitude'] >= -90) & (df['latitude'] <= 90) &
        (df['longitude'] >= -180) & (df['longitude'] <= 180)
    ].copy()
    
    if valid_data.empty:
        print("All ACLED events had invalid coords.")
        return
        
    print(f"Inserting {len(valid_data)} validated ACLED events.")
    
    # Calculate initial intensity (R0) based on fatalities
    # Basic logarithmic scaling to avoid massive spikes, normalized to 0-1 range roughly
    valid_data['intensity_index'] = valid_data['fatalities'].apply(lambda x: min(1.0, (x / 100.0) + 0.1))
    
    valid_data['location'] = valid_data.apply(
        lambda row: f"POINT({row['longitude']} {row['latitude']})", axis=1
    )
    
    with engine.connect() as conn:
        for _, row in valid_data.iterrows():
            query = f"""
                INSERT INTO conflict_data 
                (location, event_date, fatalities, intensity_index, event_type, cleaned)
                VALUES 
                (ST_GeomFromText('{row['location']}', 4326), '{row['event_date']}', 
                {row['fatalities']}, {row['intensity_index']}, '{row['event_type']}', TRUE)
            """
            try:
                conn.execute(text(query))
            except Exception as e:
                print(f"Error inserting: {e}")
        conn.commit()

@flow(name="Hourly_ACLED_Ingestion")
def ingest_acled():
    """Flow to bring in ACLED data"""
    engine = create_engine(db_url)
    events = fetch_acled_events()
    process_and_store_acled(events, engine)


if __name__ == "__main__":
    # Wait for DB to be ready before starting Prefect flows
    from sqlalchemy.exc import OperationalError
    engine = create_engine(db_url)
    max_retries = 30
    for i in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is ready! Starting ingestion flows...")
            break
        except OperationalError:
            print(f"Waiting for database to become ready... ({i+1}/{max_retries})")
            time.sleep(2)
    else:
        print("Failed to connect to database after maximum retries. Exiting.")
        pd.sys.exit(1)

    # In a full deployment, these would be scheduled via Prefect Cloud/Server
    # For demo purposes, we can trigger one run.
    ingest_currencies()
    ingest_acled()
