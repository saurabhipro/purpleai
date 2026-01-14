// /** @odoo-module **/

import { Component, onMounted } from "@odoo/owl";

export class GraphComponent extends Component {
    setup() {
        this.chartInstance = null;
        onMounted(() => this.renderChart());
    }

    async renderChart() {
        
    const chartType = (this.props.chart_type || 'pie').toLowerCase();
    const chartData = this.props.chart_data || [];

    const labels = chartData.map(d => d.label);
    const values = chartData.map(d => d.value);

    const baseColors = [
        '#70cac1', '#659d4e', '#6050DC', '#D52DB7',
        '#FF2E7E', '#aeff45ff', '#f39c12', '#8e44ad'
    ];
    const bgColor = baseColors.slice(0, values.length);
    const borderColor = bgColor.map(c => c.replace('ff', 'cc'));

    const canvasElement = document.getElementById(this.props.canvas_id);
    if (!canvasElement) {
        console.error("❌ Canvas element not found for", this.props.canvas_id);
        return;
    }

    // Destroy existing chart instance if it exists
    if (this.chartInstance) {
        this.chartInstance.destroy();
        this.chartInstance = null;
    }

    // Also check for any existing chart on this canvas using Chart.js registry
    const existingChart = Chart.getChart(canvasElement);
    if (existingChart) {
        existingChart.destroy();
    }

    const ctx = canvasElement.getContext('2d');
    if (!ctx) {
        console.error("❌ Canvas context not found for", this.props.canvas_id);
        return;
    }

    if (!labels.length || !values.length) {
        console.warn("⚠️ Empty chart data for:", this.props.canvas_id);
        return;
    }

    // Chart.js expects special structure for some charts like bubble/scatter
    const datasetConfig = (() => {
        switch (chartType) {
            case 'line':
                return {
                    label: "Chart Data",
                    data: values,
                    backgroundColor: 'rgba(96, 80, 220, 0.3)',
                    borderColor: 'rgba(96, 80, 220, 1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                };
            case 'bar':
            case 'radar':
            case 'polararea':
                return {
                    label: "Chart Data",
                    data: values,
                    backgroundColor: bgColor,
                    borderColor: borderColor,
                    borderWidth: 1
                };
            case 'bubble':
                return {
                    label: "Chart Data",
                    data: chartData.map(d => ({
                        x: d.x || 0,
                        y: d.y || 0,
                        r: d.r || 5
                    })),
                    backgroundColor: bgColor,
                };
            case 'scatter':
                return {
                    label: "Chart Data",
                    data: chartData.map(d => ({
                        x: d.x || 0,
                        y: d.y || 0
                    })),
                    backgroundColor: bgColor,
                };
            case 'doughnut':
            case 'pie':
            default:
                return {
                    label: "Chart Data",
                    data: values,
                    backgroundColor: bgColor,
                };
        }
    })();

    this.chartInstance = new Chart(ctx, {
    type: chartType,
    data: {
        labels,
        datasets: [datasetConfig]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,  // Optional: Helps remove extra bottom space
        layout: {
            padding: {
                top: 10,
                bottom: 0  // Reduces extra empty space below chart
            }
        },
        plugins: {
            legend: {
                display: true,
                position: chartType === 'pie' || chartType === 'doughnut' ? 'right' : 'top',
                labels: {
                    color: 'black',
                    usePointStyle: true,
                }
            },
            tooltip: {
                callbacks: {
                    label: function (context) {
                        const label = context.label || '';
                        const value = context.raw || 0;

                        if (chartType === 'pie' || chartType === 'doughnut') {
                            const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(2);
                            return `${label}: ${value} (${percentage}%)`;
                        } else if (chartType === 'bubble') {
                            const { x, y, r } = context.raw;
                            return `x: ${x}, y: ${y}, r: ${r}`;
                        } else if (chartType === 'scatter') {
                            const { x, y } = context.raw;
                            return `x: ${x}, y: ${y}`;
                        }

                        return `${label}: ${value}`;
                    }
                }
            }
        },
    }
    });
}
}
GraphComponent.props = ["canvas_id", "chart_data", "chart_type"];
GraphComponent.template = "bharat_ddn.GraphComponent";
