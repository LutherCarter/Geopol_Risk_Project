document.addEventListener('DOMContentLoaded', () => {
    const viewSelector = document.getElementById('view-selector');
    const dynamicContent = document.getElementById('dynamic-content');
    
    let currentMap = null;
    let currentNetwork = null;
    let currentChart = null;

    // Viewport definitions for map centering
    const VIEWPORTS = {
        "Global": { center: [20, 0], zoom: 2 },
        "Americas": { center: [15, -90], zoom: 3 },
        "EMEA": { center: [45, 15], zoom: 3 },
        "APAC": { center: [15, 120], zoom: 3 }
    };

    function destroyInstances() {
        if (currentMap) { currentMap.remove(); currentMap = null; }
        if (currentNetwork) { currentNetwork.destroy(); currentNetwork = null; }
        if (currentChart) { currentChart.destroy(); currentChart = null; }
    }

    function initMode() {
        destroyInstances();
        const mode = viewSelector.value;
        const template = document.getElementById(`tpl-${mode}`);
        dynamicContent.innerHTML = template.innerHTML;

        if (mode === 'mode1') initMode1();
        if (mode === 'mode2') initMode2();
        if (mode === 'mode3') initMode3();
        if (mode === 'mode4') initMode4();
    }

    viewSelector.addEventListener('change', initMode);

    // Initial load
    initMode();

    async function fetchSimulation(payload) {
        try {
            const response = await fetch('/api/run_simulation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error('API Error');
            return await response.json();
        } catch (e) {
            console.error(e);
            return null;
        }
    }

    function getColor(prob) {
        if (prob > 0.6) return { bg: '#FF003C', border: '#FF003C', text: '#FFFFFF', name: 'Critical' };
        if (prob > 0.3) return { bg: '#ffc107', border: '#ffc107', text: '#000000', name: 'Warning' };
        return { bg: '#39FF14', border: '#39FF14', text: '#000000', name: 'Stable' };
    }

    function renderVisNetwork(container, nodesData, edgesData) {
        const nodes = new vis.DataSet(nodesData.map(n => {
            const c = getColor(n.fail_prob);
            return {
                id: n.id, label: n.label, shape: 'box',
                color: { background: c.bg, border: c.border, highlight: { background: c.bg, border: '#FFF' } },
                font: { color: c.text, face: 'Rajdhani', size: 16, bold: true },
                borderWidth: 2, shadow: { enabled: true, color: c.bg, size: 15 }
            };
        }));
        const edges = new vis.DataSet(edgesData.map(e => ({
            from: e.from, to: e.to, color: { color: 'rgba(255,255,255,0.2)' },
            width: 2, arrows: 'to', smooth: { type: 'cubicBezier', forceDirection: 'vertical', roundness: 0.4 }
        })));
        currentNetwork = new vis.Network(container, {nodes, edges}, {
            layout: { hierarchical: { direction: 'UD', sortMethod: 'directed' } },
            physics: false
        });
    }

    function initLeaflet(containerId, center, zoom) {
        const map = L.map(containerId).setView(center, zoom);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd', maxZoom: 20
        }).addTo(map);
        return map;
    }

    // --- Mode 1: Geospatial Overlay ---
    function initMode1() {
        currentMap = initLeaflet('m1-map', VIEWPORTS['Global'].center, VIEWPORTS['Global'].zoom);
        
        const shockSlider = document.getElementById('m1-shock');
        const shockDisplay = document.getElementById('m1-shock-display');
        const vpSelect = document.getElementById('m1-viewport');
        const runBtn = document.getElementById('m1-run-btn');
        const alertsDiv = document.getElementById('m1-alerts');
        const detailsPanel = document.getElementById('m1-details');
        const nodeInfo = document.getElementById('m1-node-info');

        let markers = [];

        shockSlider.addEventListener('input', e => shockDisplay.textContent = `${e.target.value}%`);
        
        runBtn.addEventListener('click', async () => {
            runBtn.textContent = 'Simulating...';
            const data = await fetchSimulation({ viewport_key: vpSelect.value, shock_val: parseFloat(shockSlider.value) });
            runBtn.textContent = 'Run Global Analysis';
            
            if (!data) return;

            // Update Map
            const vp = VIEWPORTS[vpSelect.value];
            currentMap.flyTo(vp.center, vp.zoom);
            
            markers.forEach(m => currentMap.removeLayer(m));
            markers = [];

            // Draw edges as polylines first
            data.edges.forEach(edge => {
                const source = data.nodes.find(n => n.id === edge.from);
                const target = data.nodes.find(n => n.id === edge.to);
                if(source && target && source.lat !== 0 && target.lat !== 0) {
                    const line = L.polyline([[source.lat, source.lon], [target.lat, target.lon]], {color: 'rgba(255,255,255,0.3)', weight: 2}).addTo(currentMap);
                    markers.push(line);
                }
            });

            // Draw nodes
            data.nodes.forEach(n => {
                if(n.lat === 0 && n.lon === 0) return;
                const c = getColor(n.fail_prob);
                const circle = L.circleMarker([n.lat, n.lon], {
                    radius: 12, fillColor: c.bg, color: '#FFF', weight: 2, fillOpacity: 0.8
                }).addTo(currentMap);
                
                circle.on('click', () => {
                    detailsPanel.style.display = 'flex';
                    nodeInfo.innerHTML = `<strong>ID:</strong> ${n.id}<br><strong>Failure Probability:</strong> ${(n.fail_prob*100).toFixed(1)}%<br><strong>Status:</strong> <span style="color:${c.bg}">${c.name}</span><br><br><em>Driven by local ACLED events and fx exposure.</em>`;
                });
                markers.push(circle);
            });

            // Alerts
            alertsDiv.innerHTML = data.alerts.map(a => `<div class="alert-box">${a}</div>`).join('') || `<div class="alert-info">No active clusters.</div>`;
        });
        
        runBtn.click();
    }

    // --- Mode 2: Dual-Pane Analysis ---
    function initMode2() {
        currentMap = initLeaflet('m2-map', VIEWPORTS['Global'].center, VIEWPORTS['Global'].zoom);
        const runBtn = document.getElementById('m2-run-btn');

        runBtn.addEventListener('click', async () => {
            runBtn.textContent = 'Syncing...';
            const data = await fetchSimulation({ viewport_key: 'Global', shock_val: 10 });
            runBtn.textContent = 'Sync Data';
            if (!data) return;

            renderVisNetwork(document.getElementById('m2-network'), data.nodes, data.edges);

            data.nodes.forEach(n => {
                if(n.lat === 0 && n.lon === 0) return;
                const c = getColor(n.fail_prob);
                const marker = L.circleMarker([n.lat, n.lon], { radius: 10, fillColor: c.bg, color: '#FFF', weight: 2, fillOpacity: 0.8 }).addTo(currentMap);
                marker.bindPopup(`<b>${n.id}</b><br>Fail: ${(n.fail_prob*100).toFixed(1)}%`);
                
                // Highlight corresponding node in network on click
                marker.on('click', () => {
                    if(currentNetwork) {
                        currentNetwork.selectNodes([n.id]);
                        currentNetwork.focus(n.id, {scale: 1.2, animation: true});
                    }
                });
            });
        });

        runBtn.click();
    }

    // --- Mode 3: Metrics Dashboard ---
    function initMode3() {
        currentMap = initLeaflet('m3-map', VIEWPORTS['Global'].center, 1);
        const runBtn = document.getElementById('m3-run-btn');
        const briefing = document.getElementById('m3-briefing');

        runBtn.addEventListener('click', async () => {
            runBtn.textContent = 'Generating...';
            const data = await fetchSimulation({ viewport_key: 'Global', shock_val: 25 });
            runBtn.textContent = 'Regenerate Report';
            if (!data) return;

            renderVisNetwork(document.getElementById('m3-network'), data.nodes, data.edges);

            data.nodes.forEach(n => {
                if(n.lat === 0 && n.lon === 0) return;
                L.circleMarker([n.lat, n.lon], { radius: 8, fillColor: getColor(n.fail_prob).bg, color: '#FFF', weight: 1, fillOpacity: 0.8 }).addTo(currentMap);
            });

            // Chart.js
            const ctx = document.getElementById('m3-chart').getContext('2d');
            const sortedNodes = [...data.nodes].sort((a,b) => b.fail_prob - a.fail_prob);
            if(currentChart) currentChart.destroy();
            currentChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: sortedNodes.map(n => n.id),
                    datasets: [{
                        label: 'Failure Risk',
                        data: sortedNodes.map(n => n.fail_prob * 100),
                        backgroundColor: sortedNodes.map(n => getColor(n.fail_prob).bg)
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    scales: { y: { beginAtZero: true, max: 100, ticks: { color: '#E5E7EB' } }, x: { ticks: { color: '#E5E7EB' } } },
                    plugins: { legend: { display: false } }
                }
            });

            // Briefing
            const highest = sortedNodes[0];
            briefing.innerHTML = `<p><strong>CRITICAL UPDATE:</strong></p>
            <p>The global supply chain network is experiencing stress due to a simulated 25% volatility shock.</p>
            <p>Node <strong>${highest.id}</strong> is currently the most vulnerable with a <strong>${(highest.fail_prob*100).toFixed(1)}%</strong> probability of failure.</p>
            <p><strong>Geospatial Clusters:</strong> ${data.alerts.length} active DBSCAN alerts detected affecting shipping lanes.</p>`;
        });
        
        runBtn.click();
    }

    // --- Mode 4: Scenario Simulator ---
    function initMode4() {
        currentMap = initLeaflet('m4-map', VIEWPORTS['Global'].center, 2);
        const scenarioSelect = document.getElementById('m4-scenario');
        const runBtn = document.getElementById('m4-run-btn');
        const report = document.getElementById('m4-report');

        const SCENARIOS = {
            'base': { vp: 'Global', shock: 10, title: 'Baseline' },
            'fx_spike': { vp: 'Global', shock: 50, title: 'Global Currency Crisis' },
            'conflict_emea': { vp: 'EMEA', shock: 80, title: 'EMEA Escalation' },
            'apac_blockade': { vp: 'APAC', shock: 100, title: 'APAC Blockade' }
        };

        let markers = [];

        runBtn.addEventListener('click', async () => {
            const sc = SCENARIOS[scenarioSelect.value];
            runBtn.textContent = 'Executing...';
            const data = await fetchSimulation({ viewport_key: sc.vp, shock_val: sc.shock });
            runBtn.textContent = 'Execute Scenario';
            if (!data) return;

            const vp = VIEWPORTS[sc.vp];
            currentMap.flyTo(vp.center, vp.zoom);

            markers.forEach(m => currentMap.removeLayer(m));
            markers = [];

            data.nodes.forEach(n => {
                if(n.lat === 0 && n.lon === 0) return;
                const c = getColor(n.fail_prob);
                markers.push(L.circleMarker([n.lat, n.lon], { radius: sc.shock > 50 ? 20 : 10, fillColor: c.bg, color: '#FFF', weight: 2, fillOpacity: 0.8 }).addTo(currentMap));
            });

            const maxFail = Math.max(...data.nodes.map(n => n.fail_prob));
            const criticalNodes = data.nodes.filter(n => n.fail_prob > 0.6).map(n => n.id);

            report.innerHTML = `
                <h3 style="color:var(--accent-pink);">${sc.title} Simulation Complete</h3>
                <p>Applied Volatility Shock: <strong>${sc.shock}%</strong></p>
                <p>Maximum Network Failure Probability: <strong>${(maxFail*100).toFixed(1)}%</strong></p>
                <hr style="border-color:var(--panel-border);">
                <h4>Impact Analysis:</h4>
                <p>The applied stress test demonstrates immediate cascading failures across the network. ${criticalNodes.length > 0 ? `The following nodes have reached critical failure thresholds (>60%): <strong>${criticalNodes.join(', ')}</strong>.` : 'The network remains resilient to this scenario.'}</p>
                <p>${data.alerts.length > 0 ? `Spatial clusters identified: ${data.alerts.join('<br>')}` : 'No spatial anomalies detected in target region.'}</p>
            `;
        });
    }
});
