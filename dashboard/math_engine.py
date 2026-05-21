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

    def run_dbscan(self, min_lon, max_lon, min_lat, max_lat, eps_km=50, min_samples=3):
        """
        Runs DBSCAN for a specific bounding box (viewport).
        """
        eps_degrees = eps_km / 111.0
        
        df_chunk = self._get_dbscan_chunk(min_lon, max_lon, min_lat, max_lat)
        if df_chunk.empty or len(df_chunk) < min_samples:
            return pd.DataFrame()
            
        coords = df_chunk[['lon', 'lat']].values
        
        db = DBSCAN(eps=eps_degrees, min_samples=min_samples).fit(coords)
        
        df_chunk['cluster_id'] = db.labels_
        clusters = df_chunk[df_chunk['cluster_id'] != -1].copy()
        if not clusters.empty:
            clusters['global_cluster_id'] = "Viewport_" + clusters['cluster_id'].astype(str)
            return clusters
        return pd.DataFrame()

    def supply_chain_buffer_risk(self, radius_km=200):
        """
        Calculates risk for supply chain nodes looking only at conflicts
        within a strict buffer radius using ST_DWithin.
        """
        # Convert km to meters for exact geography distance calculation
        radius_meters = radius_km * 1000.0
        
        query = f"""
            SELECT 
                n.node_id,
                n.criticality_score,
                COALESCE(SUM(c.active_intensity), 0) as local_risk_score
            FROM supply_chain_nodes n
            LEFT JOIN vw_decayed_conflict_events c
            ON ST_DWithin(n.location::geography, c.location::geography, {radius_meters})
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
        
        # Precompute log(1 - A) for rigorous probability combination
        # P_{cascade} = 1 - \prod (1 - P_i)
        log_1_minus_A = np.zeros_like(A)
        mask = A < 1.0
        log_1_minus_A[mask] = np.log(1.0 - A[mask])
        log_1_minus_A[A >= 1.0] = -np.inf
        
        cascade_active = True
        max_steps = n_nodes # Cascade can't be longer than the network depth
        step = 0
        
        while cascade_active and step < max_steps:
            # Independent probability combination using dot product of logs
            # exposure = 1 - exp( state (dot) log(1-A) )
            log_prob = np.dot(state, log_1_minus_A)
            exposure = 1.0 - np.exp(log_prob)
            
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
