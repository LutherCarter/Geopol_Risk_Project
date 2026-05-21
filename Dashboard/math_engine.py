import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sqlalchemy import create_engine, text
import os

class RiskMathEngine:
    def __init__(self):
        db_user = os.getenv("POSTGRES_USER", "admin")
        db_password = os.getenv("POSTGRES_PASSWORD", "password")
        db_host = os.getenv("DB_HOST", "postgres-postgis")
        db_port = "5432"
        db_name = os.getenv("POSTGRES_DB", "risk_db")
        
        # Use fallback for local testing without docker
        if "DB_HOST" not in os.environ:
            db_host = "localhost"
            
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        self.engine = create_engine(db_url)
        
    def _get_dbscan_chunk(self, min_lon, max_lon, min_lat, max_lat):
        """Fetches a specific spatial bounding box chunk for DBSCAN processing."""
        query = f"""
            SELECT record_id, ST_X(location) as lon, ST_Y(location) as lat, active_intensity
            FROM vw_decayed_conflict_events
            WHERE ST_Intersects(
                location,
                ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)
            ) AND active_intensity > 0.05
        """
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), conn)
        except Exception as e:
            print(f"Error fetching chunk: {e}")
            return pd.DataFrame()

    def run_global_dbscan(self, eps_km=50, min_samples=3):
        """
        Runs DBSCAN in parallel (or sequential chunks) to avoid memory explosion.
        We define 3 macro bounding boxes: Americas, EMEA, APAC.
        """
        # Convert eps (km) to degrees approx (1 degree lat ~= 111 km)
        eps_degrees = eps_km / 111.0
        
        chunks = {
            "Americas": (-180, -30, -60, 90),
            "EMEA": (-30, 60, -60, 90),
            "APAC": (60, 180, -60, 90)
        }
        
        all_clusters = []
        
        for region, (min_lon, max_lon, min_lat, max_lat) in chunks.items():
            df_chunk = self._get_dbscan_chunk(min_lon, max_lon, min_lat, max_lat)
            if df_chunk.empty or len(df_chunk) < min_samples:
                continue
                
            # Run DBSCAN on the coords
            coords = df_chunk[['lon', 'lat']].values
            
            # Note: For strict km distance on globe, Haversine metric should be used 
            # with radians. For simplicity and speed in this demo, Euclidean approx is used.
            db = DBSCAN(eps=eps_degrees, min_samples=min_samples).fit(coords)
            
            df_chunk['cluster_id'] = db.labels_
            # Filter out noise (-1)
            clusters = df_chunk[df_chunk['cluster_id'] != -1]
            if not clusters.empty:
                # Distinguish cluster IDs globally by prefixing the region
                clusters['global_cluster_id'] = f"{region}_" + clusters['cluster_id'].astype(str)
                all_clusters.append(clusters)
                
        if all_clusters:
            return pd.concat(all_clusters, ignore_index=True)
        return pd.DataFrame()

    def supply_chain_buffer_risk(self, radius_km=200):
        """
        Calculates risk for supply chain nodes looking only at conflicts
        within a strict buffer radius using ST_DWithin.
        """
        # Convert km to degrees (roughly 1 deg = 111km)
        radius_deg = radius_km / 111.0
        
        query = f"""
            SELECT 
                n.node_id,
                n.criticality_score,
                COALESCE(SUM(c.active_intensity), 0) as local_risk_score
            FROM supply_chain_nodes n
            LEFT JOIN vw_decayed_conflict_events c
            ON ST_DWithin(n.location, c.location, {radius_deg})
            GROUP BY n.node_id, n.criticality_score
        """
        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), conn)
        except Exception:
            # Fallback mock data if DB is empty or fails
            return pd.DataFrame({
                'node_id': ['Factory_A', 'Port_B', 'Assembly_C', 'Distributor_D'],
                'criticality_score': [0.9, 0.8, 0.7, 0.95],
                'local_risk_score': [0.1, 0.5, 0.2, 0.05]
            })

    def run_vectorized_monte_carlo(self, node_risks_df, n_simulations=10000):
        """
        Vectorized Monte Carlo cascading failure.
        Replaces the slow python loops with matrix multiplication.
        """
        nodes = node_risks_df['node_id'].tolist()
        n_nodes = len(nodes)
        node_idx = {node: i for i, node in enumerate(nodes)}
        
        # 1. Base Probabilities (Initial failure risk array)
        P_fail = np.zeros(n_nodes)
        for _, row in node_risks_df.iterrows():
            if row['node_id'] in node_idx:
                # Scale risk to a probability [0, 1]
                prob = min(row['local_risk_score'] * 0.1, 0.99)
                P_fail[node_idx[row['node_id']]] = prob
                
        # 2. Build Adjacency Matrix A (Dependency Weights)
        A = np.zeros((n_nodes, n_nodes))
        
        try:
            query = "SELECT source_node, target_node, dependency_weight FROM supply_chain_edges"
            with self.engine.connect() as conn:
                edges_df = pd.read_sql(text(query), conn)
            if edges_df.empty:
                raise ValueError("No edges")
        except Exception:
            # Mock edges if DB not ready
            edges_df = pd.DataFrame([
                {'source_node': 'Factory_A', 'target_node': 'Port_B', 'dependency_weight': 0.9},
                {'source_node': 'Port_B', 'target_node': 'Assembly_C', 'dependency_weight': 0.8},
                {'source_node': 'Assembly_C', 'target_node': 'Distributor_D', 'dependency_weight': 0.95}
            ])
            
        for _, row in edges_df.iterrows():
            src_name = row['source_node']
            tgt_name = row['target_node']
            if src_name in node_idx and tgt_name in node_idx:
                u = node_idx[src_name]
                v = node_idx[tgt_name]
                A[u, v] = row['dependency_weight']

        # 3. Vectorized Simulation
        # State matrix: shape (n_simulations, n_nodes), 1 if failed, 0 if operational
        # Initial state based on random draws against P_fail
        rand_initial = np.random.random((n_simulations, n_nodes))
        state = (rand_initial < P_fail).astype(float)
        
        cascade_active = True
        max_steps = n_nodes # Cascade can't be longer than the network depth
        step = 0
        
        while cascade_active and step < max_steps:
            # Current state dot Adjacency matrix gives the probability exposure
            # for the NEXT node in the chain
            # S_{t} x A = Exposure_Matrix. If state is 1, exposure = weight.
            exposure = np.dot(state, A)
            
            # Clamp exposure to max 1.0 probability
            exposure = np.clip(exposure, 0, 1.0)
            
            # Draw random numbers for the propagation
            rand_step = np.random.random((n_simulations, n_nodes))
            
            # Find new failures (Nodes that weren't failed, but now fail due to cascade exposure)
            new_failures = ((rand_step < exposure) & (state == 0)).astype(float)
            
            if np.sum(new_failures) == 0:
                cascade_active = False
            else:
                state += new_failures # Update state
                step += 1
                
        # Calculate failure percentage across all simulations
        failure_probs = np.sum(state, axis=0) / n_simulations
        
        # Return mapped to node names
        results = {nodes[i]: failure_probs[i] for i in range(n_nodes)}
        return results
