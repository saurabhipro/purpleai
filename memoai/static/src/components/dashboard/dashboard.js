/** @odoo-module */

import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class MemoDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.chartCanvas = useRef("chartCanvas");
        this.chartInstance = null;

        this.state = useState({
            total_requests: 0,
            passes: 0,
            in_process: 0,
            total_time: 0,
            total_cost: 0,
        });

        onWillStart(async () => {
            // Load Chart.js dynamically from CDN for reliable rendering in custom client action
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
            await this.fetchStats();
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    async fetchStats() {
        const stats = await this.orm.call("memo_ai.session", "get_dashboard_stats", [], {});
        this.state.total_requests = stats.total_requests;
        this.state.passes = stats.passes;
        this.state.in_process = stats.in_process;
        this.state.total_time = stats.total_time;
        this.state.total_cost = stats.total_cost;
        this.chartData = stats.chart;

        if (this.chartInstance) {
            this.renderChart();
        }
    }

    renderChart() {
        if (!this.chartCanvas.el) return;

        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        const ctx = this.chartCanvas.el.getContext("2d");

        this.chartInstance = new Chart(ctx, {
            type: "bar",
            data: {
                labels: this.chartData.labels,
                datasets: [
                    {
                        label: "Cost ($)",
                        data: this.chartData.cost_data,
                        backgroundColor: "rgba(54, 162, 235, 0.6)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1,
                        yAxisID: 'y',
                    },
                    {
                        label: "Time Taken (s)",
                        data: this.chartData.time_data,
                        type: "line",
                        backgroundColor: "rgba(255, 99, 132, 0.6)",
                        borderColor: "rgba(255, 99, 132, 1)",
                        borderWidth: 2,
                        yAxisID: 'y1',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Cost ($)' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Time (s)' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }
}

MemoDashboard.template = "memoai.Dashboard";
registry.category("actions").add("memoai_analytics_dashboard", MemoDashboard);
