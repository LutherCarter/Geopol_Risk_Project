import networkx as nx

class SupplyChainSimulator:
    def __init__(self, risk_scores):
        self.risk_scores = risk_scores # Dictionary of {region: composite_risk_score}
        self.network = nx.DiGraph()
        self._build_network()

    def _build_network(self):
        """Simulates building the network from supply_chain_edges SQL table."""
        # Nodes: (Node ID, Region)
        nodes = [
            ('Factory_A', 'East Asia'), 
            ('Port_B', 'East Asia'),
            ('Assembly_C', 'Eastern Europe'), 
            ('Distributor_D', 'Western Europe')
        ]
        for node_id, region in nodes:
            self.network.add_node(node_id, region=region, status='operational')

        # Edges (Source, Target, Dependency Weight)
        edges = [
            ('Factory_A', 'Port_B', 0.9),
            ('Port_B', 'Assembly_C', 0.8),
            ('Assembly_C', 'Distributor_D', 0.95)
        ]
        for src, tgt, weight in edges:
            self.network.add_edge(src, tgt, weight=weight)

    def _single_simulation_run(self):
        """Runs one iteration of the cascading failure model."""
        failed_nodes = set()
        
        # Step 1: Direct impacts based on regional risk (Probability of failure = Risk Score)
        for node, data in self.network.nodes(data=True):
            region = data['region']
            risk = self.risk_scores.get(region, 0.05) # Default low risk
            
            # Random event: does the node fail due to regional instability?
            if np.random.random() < risk:
                failed_nodes.add(node)
                
        # Step 2: Cascading impacts through the network
        cascade_active = True
        while cascade_active:
            initial_fail_count = len(failed_nodes)
            
            for u, v, data in self.network.edges(data=True):
                if u in failed_nodes and v not in failed_nodes:
                    # If upstream fails, downstream fails based on dependency weight
                    if np.random.random() < data['weight']:
                        failed_nodes.add(v)
            
            # Stop if no new nodes failed in this cascade step
            if len(failed_nodes) == initial_fail_count:
                cascade_active = False
                
        return failed_nodes

    def run_monte_carlo(self, n_simulations=1000):
        """Executes Monte Carlo simulations to find most vulnerable nodes."""
        node_failure_counts = {node: 0 for node in self.network.nodes()}
        
        for _ in range(n_simulations):
            failures = self._single_simulation_run()
            for node in failures:
                node_failure_counts[node] += 1
                
        # Convert to probabilities
        vulnerability_probs = {node: count / n_simulations for node, count in node_failure_counts.items()}
        return pd.Series(vulnerability_probs).sort_values(ascending=False)

# --- Execution Example ---
if __name__ == "__main__":
    # 1. Assess Risk
    engine = RiskAssessmentEngine()
    data = engine.fetch_regional_data()
    risk_data = engine.calculate_composite_risk(data)
    
    # Extract risk scores into a dictionary
    regional_risk = risk_data['composite_risk_score'].to_dict()
    print("Regional Risk Scores:")
    print(risk_data[['composite_risk_score']], "\n")

    # 2. Simulate Supply Chain Impacts
    simulator = SupplyChainSimulator(risk_scores=regional_risk)
    vulnerabilities = simulator.run_monte_carlo(n_simulations=10000)
    
    print("Probability of Node Disruption (10,000 Simulations):")
    print(vulnerabilities)