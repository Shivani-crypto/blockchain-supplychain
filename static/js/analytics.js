/* Chart.js Analytics Module for Admin Audit Dashboard */

function initAdminCharts(analyticsData) {
    if (typeof Chart === 'undefined') return;

    // Chart 1: Supply Chain Metrics Doughnut Chart
    const ctxOverview = document.getElementById('chartOverview');
    if (ctxOverview) {
        new Chart(ctxOverview, {
            type: 'doughnut',
            data: {
                labels: ['Active Orders', 'Shipment Legs', 'Recorded Disruptions', 'Role Switches'],
                datasets: [{
                    data: [
                        analyticsData.orders || 0,
                        analyticsData.legs || 0,
                        analyticsData.disruptions || 0,
                        analyticsData.switches || 0
                    ],
                    backgroundColor: [
                        '#38bdf8',
                        '#6366f1',
                        '#f43f5e',
                        '#f59e0b'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#475569', font: { family: 'Inter', weight: '600' } }
                    }
                }
            }
        });
    }

    // Chart 2: Leg Status Distribution Bar Chart
    const ctxLegs = document.getElementById('chartLegs');
    if (ctxLegs) {
        new Chart(ctxLegs, {
            type: 'bar',
            data: {
                labels: ['Leg 1 (Sup->Mfg)', 'Leg 2 (Mfg->Dist)', 'Leg 3 (Dist->Ret)', 'Leg 4 (Ret->Con)'],
                datasets: [{
                    label: 'Active Shipments',
                    data: analyticsData.leg_counts || [0, 0, 0, 0],
                    backgroundColor: 'rgba(37, 99, 235, 0.75)',
                    borderColor: '#2563eb',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { ticks: { color: '#475569', font: { family: 'Inter', weight: '500' } }, grid: { display: false } },
                    y: { ticks: { color: '#475569', font: { family: 'Inter', weight: '500' } }, grid: { color: 'rgba(226, 232, 240, 0.8)' } }
                },
                plugins: {
                    legend: { labels: { color: '#475569', font: { family: 'Inter', weight: '600' } } }
                }
            }
        });
    }
}
