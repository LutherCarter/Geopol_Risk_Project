from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from math_engine import RiskMathEngine

app = FastAPI()

engine = RiskMathEngine()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

class RunMCRequest(BaseModel):
    viewport_key: str
    shock_val: float

VIEWPORTS = {
    "Global": (-180, -90, 180, 90),
    "Americas": (-180, -60, -30, 90),
    "EMEA": (-30, -60, 60, 90),
    "APAC": (60, -60, 180, 90)
}

@app.post("/api/run_simulation")
def run_simulation(req: RunMCRequest):
    # 1. Fetch risk for nodes
    node_risks = engine.supply_chain_buffer_risk(radius_km=200)
    
    # Apply synthetic shock
    node_risks['local_risk_score'] *= (1 + (req.shock_val / 100.0))
    
    # Run Vectorized MC
    mc_results = engine.run_vectorized_monte_carlo(node_risks, n_simulations=5000)
    
    # Build Network Data (Nodes and Edges)
    try:
        query = "SELECT source_node, target_node, dependency_weight FROM supply_chain_edges"
        import pandas as pd
        from sqlalchemy import text
        with engine.engine.connect() as conn:
            edges_df = pd.read_sql(text(query), conn)
    except Exception:
        import pandas as pd
        edges_df = pd.DataFrame([
            {'source_node': 'Factory_A', 'target_node': 'Port_B'},
            {'source_node': 'Port_B', 'target_node': 'Assembly_C'},
            {'source_node': 'Assembly_C', 'target_node': 'Distributor_D'}
        ])
        
    edges = [{"from": row['source_node'], "to": row['target_node']} for _, row in edges_df.iterrows()]
    
    mock_coords = {
        'Factory_A': {'lat': 31.23, 'lon': 121.47},
        'Port_B': {'lat': 1.35, 'lon': 103.81},
        'Assembly_C': {'lat': 48.85, 'lon': 2.35},
        'Distributor_D': {'lat': 40.71, 'lon': -74.00}
    }
    
    nodes = []
    for node, prob in mc_results.items():
        coords = mock_coords.get(node, {'lat': 0, 'lon': 0})
        nodes.append({
            "id": node, 
            "label": f"{node}\nFail: {prob:.1%}", 
            "fail_prob": prob,
            "lat": coords['lat'],
            "lon": coords['lon']
        })
    
    # 2. Viewport
    min_lon, min_lat, max_lon, max_lat = VIEWPORTS.get(req.viewport_key, VIEWPORTS['Global'])
    
    # 3. DBSCAN Alerts
    clusters = engine.run_dbscan(min_lon, max_lon, min_lat, max_lat, eps_km=100, min_samples=2)
    
    alerts = []
    if not clusters.empty:
        grouped = clusters.groupby('global_cluster_id')
        for cid, group in grouped:
            alerts.append(f"ALERT: Emerging Pattern Detected! Cluster {cid} contains {len(group)} high-intensity points.")
            
    return {
        "nodes": nodes,
        "edges": edges,
        "alerts": alerts,
        "viewport": {"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat}
    }
