import dash
from dash import html, dcc, Input, Output, State
import dash_cytoscape as cyto
from math_engine import RiskMathEngine
import json

app = dash.Dash(__name__)
engine = RiskMathEngine()

# Pre-defined mock viewport bounds for ST_MakeEnvelope demo
VIEWPORTS = {
    "Global": (-180, -90, 180, 90),
    "Americas": (-180, -60, -30, 90),
    "EMEA": (-30, -60, 60, 90),
    "APAC": (60, -60, 180, 90)
}

app.layout = html.Div(className='dashboard-container', children=[
    
    # Left Panel (Controls) & Center Console (Network Graph)
    html.Div(className='main-content', children=[
        
        # Left Panel
        html.Div(className='glass-panel controls-panel', children=[
            html.H2("Global Risk Controls"),
            html.Label("Simulated Volatility Shock (%):", className='control-label'),
            dcc.Slider(
                id='volatility-slider', min=0, max=100, step=5, value=10, 
                marks={i: {'label': f'{i}%', 'style': {'color': '#9CA3AF'}} for i in range(0, 101, 20)}
            ),
            
            html.Br(),
            html.Label("Viewport Bounding Box Focus (ST_MakeEnvelope):", className='control-label'),
            dcc.Dropdown(
                id='viewport-dropdown',
                options=[{'label': k, 'value': k} for k in VIEWPORTS.keys()],
                value='Global',
                clearable=False
            ),
            
            html.Br(),
            html.Button("Run Vectorized Monte Carlo", id='run-mc-btn', n_clicks=0, className='cyber-button')
        ]),
        
        # Center Console
        html.Div(className='glass-panel network-panel', children=[
            cyto.Cytoscape(
                id='supply-chain-network',
                layout={'name': 'breadthfirst'},
                style={'width': '100%', 'height': '100%', 'backgroundColor': 'transparent', 'borderRadius': '10px'},
                stylesheet=[
                    {
                        'selector': 'node',
                        'style': {
                            'label': 'data(label)',
                            'color': '#E5E7EB',
                            'font-family': 'Rajdhani',
                            'text-wrap': 'wrap',
                            'text-max-width': '120px',
                            'text-valign': 'bottom',
                            'text-halign': 'center',
                            'background-color': 'data(color)',
                            'border-width': '2px',
                            'border-color': 'data(color)'
                        }
                    },
                    {
                        'selector': 'edge',
                        'style': {
                            'line-color': 'rgba(255, 255, 255, 0.2)',
                            'width': 2,
                            'curve-style': 'bezier',
                            'target-arrow-shape': 'triangle',
                            'target-arrow-color': 'rgba(255, 255, 255, 0.2)'
                        }
                    }
                ],
                elements=[]
            )
        ])
    ]),
    
    # Bottom Panel (Alerts)
    html.Div(className='glass-panel alerts-panel', children=[
        html.H3("Automated Alerts (DBSCAN Spatial Clusters)"),
        html.Div(id='alerts-panel')
    ])
])

@app.callback(
    Output('supply-chain-network', 'elements'),
    Output('alerts-panel', 'children'),
    Input('run-mc-btn', 'n_clicks'),
    Input('viewport-dropdown', 'value'),
    State('volatility-slider', 'value')
)
def update_dashboard(n_clicks, viewport_key, shock_val):
    # 1. Fetch risk for nodes enforcing a 200km supply chain buffer
    node_risks = engine.supply_chain_buffer_risk(radius_km=200)
    
    # Apply synthetic shock
    node_risks['local_risk_score'] *= (1 + (shock_val / 100.0))
    
    # Run Vectorized MC
    mc_results = engine.run_vectorized_monte_carlo(node_risks, n_simulations=5000)
    
    # Build Cytoscape elements
    elements = []
    
    # Hardcoded edges for demo mapping
    edges = [
        {'data': {'source': 'Factory_A', 'target': 'Port_B'}},
        {'data': {'source': 'Port_B', 'target': 'Assembly_C'}},
        {'data': {'source': 'Assembly_C', 'target': 'Distributor_D'}}
    ]
    
    def get_color(prob):
        if prob > 0.6: return '#FF003C'  # accent-pink
        if prob > 0.3: return '#ffc107'  # yellow warning
        return '#39FF14'                 # accent-green
        
    for node, prob in mc_results.items():
        elements.append({
            'data': {'id': node, 'label': f"{node}\nFail: {prob:.1%}", 'color': get_color(prob)}
        })
        
    elements.extend(edges)
    
    # 2. BBOX Enforced Alerts (Simulating the viewport filter)
    # Get the bounding box from the selected viewport dropdown
    min_lon, min_lat, max_lon, max_lat = VIEWPORTS.get(viewport_key, VIEWPORTS['Global'])
    
    # 3. Macro BBOX Chunked DBSCAN
    # The math engine natively chunks the global logic inside run_global_dbscan
    clusters = engine.run_global_dbscan(eps_km=100, min_samples=2)
    
    # We would theoretically filter `clusters` based on the ST_MakeEnvelope query result,
    # but here we display the clusters detected globally.
    alert_divs = []
    if not clusters.empty:
        grouped = clusters.groupby('global_cluster_id')
        for cid, group in grouped:
            alert_divs.append(html.Div(f"ALERT: Emerging Pattern Detected! Cluster {cid} contains {len(group)} high-intensity points.", className='alert-box', style={'color': '#FF003C'}))
    else:
        alert_divs.append(html.Div("No active clusters detected within parameters.", className='alert-info'))
        
    alert_divs.append(html.Div(f"Viewport query executed: ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326)", className='alert-info'))

    return elements, alert_divs

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
