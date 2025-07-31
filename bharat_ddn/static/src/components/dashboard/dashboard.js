/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PropertyMapView } from "../google_map/property_map";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { GraphComponent } from "../graph/graph";
export class OwlCrmDashboard extends Component {
    // static components = {PropertyMapView, GraphComponent};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            property_info: {
                ward_data: [], // Initialize ward_data as an empty array
                // ... other property info fields
            },
            error: null,
            isLoading: true
        });

        onWillStart(async () => {
            await this.loadDashboardData();
            await this.loadGraphData();
        });
    }


    _openListView(resModel, domain = []) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Properties'),
            res_model: resModel,
            view_mode: 'list',
            views: [[false, 'list']],
            domain: domain,
        });
    }

    _onClickPropertyStatusCard(ev) {
        const anchor = ev.target.closest('a');
        if (!anchor) return;

        const status = anchor.getAttribute('status');
        const domain = status ? [['property_status', '=', status]] : [];
        this._openListView('ddn.property.info', domain);
    }

    _onClickZone(ev) {
        if (!ev.target.closest('a')) return;
        this._openListView('ddn.zone');
    }

    _onClickWard(ev) {
        if (!ev.target.closest('a')) return;
        this._openListView('ddn.ward');
    }

    _onClickColony(ev) {
        if (!ev.target.closest('a')) return;
        this._openListView('ddn.colony');
    }

    _onClickSurveyors(ev) {
        if (!ev.target.closest('a')) return;
        this._openListView('res.users', [['is_surveyor', '=', true]]);
    }

    _onClickTodaySurveyed(ev) {
        if (!ev.target.closest('a')) return;

        const today = new Date();
        const todayStart = new Date(today.setHours(0, 0, 0, 0)).toISOString();
        const todayEnd = new Date(today.setHours(23, 59, 59, 999)).toISOString();

        this._openListView('ddn.property.survey', [
            ['create_date', '>=', todayStart],
            ['create_date', '<=', todayEnd],
        ]);
    }

    async loadDashboardData() {
        try {
            // Property status wise data
            const propertyDetails = await this.orm.call(
                'ddn.property.info',
                'get_dashboard_data',
                [],
                {}
            );
            
            
            if (propertyDetails && propertyDetails.length > 0) {
                const data = propertyDetails[0];
                
                // Ensure ward_data is always an array
                this.state.property_info = {
                    ...data,
                    ward_data: Array.isArray(data.ward_data) ? data.ward_data : [],
                    total_surveyors: data.total_surveyors || 0
                };
                

                // Render surveyed per day chart if Chart.js is loaded
                setTimeout(() => {
                    if (window.Chart && document.getElementById('surveyedPerDayChart')) {
                        const ctx = document.getElementById('surveyedPerDayChart').getContext('2d');
                        const chartData = this.state.property_info.surveyed_per_day || [];
                        const labels = chartData.map(item => item.date);
                        const counts = chartData.map(item => item.count);
                        if (window.surveyedPerDayChartInstance) {
                            window.surveyedPerDayChartInstance.destroy();
                        }
                        window.surveyedPerDayChartInstance = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Surveyed',
                                    data: counts,
                                    backgroundColor: 'rgba(33, 150, 243, 0.7)',
                                    borderColor: 'rgba(21, 101, 192, 1)',
                                    borderWidth: 1
                                }]
                            },
                            options: {
                                responsive: true,
                                plugins: {
                                    legend: { display: false },
                                    title: { display: false }
                                },
                                scales: {
                                    x: { grid: { display: false } },
                                    y: { beginAtZero: true, grid: { color: '#e3f2fd' } }
                                }
                            }
                        });
                    }
                }, 0);
            } else {
                console.warn("No property details found.");
                this.state.property_info.ward_data = [];
            }
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.error = error.message || "Failed to load dashboard data";
        } finally {
            this.state.isLoading = false;
        }
    }
    async loadGraphData() {
        try {
            const result = await this.orm.call(
                'ddn.property.info',
                'get_survey_stats',  // ✅ Correct method
                [],                    // ✅ No args
                {}
            );
            console.log("\n\n result - ", result);

            // Set data to state
            this.state.survey_data = result.chart_data;

        } catch (error) {
            console.error("Error loading graph data:", error);
            this.state.error = error.message || "Failed to load survey graph data";
        } finally {
            this.state.isLoading = false;
        }
    }




    /**
     * Helper method to safely get ward data
     * @returns {Array} ward data array or empty array if not available
     */
    getWardData() {
        return this.state.property_info?.ward_data || [];
    }
}


// Register the component
registry.category("actions").add("ddn.crm_dashboard_tag", OwlCrmDashboard);
// Define the template for the component
OwlCrmDashboard.components = { PropertyMapView, GraphComponent }
OwlCrmDashboard.template = 'smkc.OwlCrmTemplate';