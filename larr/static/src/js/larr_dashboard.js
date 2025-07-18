odoo.define('larr.dashboard', function (require) {
    "use strict";

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var QWeb = core.qweb;

    var LARRDashboard = AbstractAction.extend({
        template: 'larr_dashboard_template',
        
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.dashboardData = {};
        },
        
        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._loadDashboardData();
            });
        },
        
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._renderDashboard();
                self._setupEventListeners();
            });
        },
        
        _loadDashboardData: function () {
            var self = this;
            return rpc.query({
                route: '/larr/api/dashboard',
                params: {}
            }).then(function (result) {
                if (result.success) {
                    self.dashboardData = result.data;
                } else {
                    console.error('Failed to load dashboard data:', result.error);
                }
            }).catch(function (error) {
                console.error('Error loading dashboard data:', error);
            });
        },
        
        _renderDashboard: function () {
            var self = this;
            
            // Render project statistics
            this.$('.larr-project-stats').html(QWeb.render('larr_project_stats', {
                data: self.dashboardData
            }));
            
            // Render acquisition statistics
            this.$('.larr-acquisition-stats').html(QWeb.render('larr_acquisition_stats', {
                data: self.dashboardData
            }));
            
            // Render rehabilitation statistics
            this.$('.larr-rehabilitation-stats').html(QWeb.render('larr_rehabilitation_stats', {
                data: self.dashboardData
            }));
            
            // Render compensation statistics
            this.$('.larr-compensation-stats').html(QWeb.render('larr_compensation_stats', {
                data: self.dashboardData
            }));
            
            // Render stakeholder statistics
            this.$('.larr-stakeholder-stats').html(QWeb.render('larr_stakeholder_stats', {
                data: self.dashboardData
            }));
            
            // Render financial summary
            this.$('.larr-financial-summary').html(QWeb.render('larr_financial_summary', {
                data: self.dashboardData
            }));
        },
        
        _setupEventListeners: function () {
            var self = this;
            
            // Refresh button
            this.$('.larr-refresh-btn').on('click', function () {
                self._loadDashboardData().then(function () {
                    self._renderDashboard();
                });
            });
            
            // Project cards click
            this.$('.larr-project-card').on('click', function () {
                var projectId = $(this).data('project-id');
                self._openProject(projectId);
            });
            
            // Acquisition cards click
            this.$('.larr-acquisition-card').on('click', function () {
                var acquisitionId = $(this).data('acquisition-id');
                self._openAcquisition(acquisitionId);
            });
        },
        
        _openProject: function (projectId) {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'larr.project',
                res_id: projectId,
                view_mode: 'form',
                target: 'current'
            });
        },
        
        _openAcquisition: function (acquisitionId) {
            this.do_action({
                type: 'ir.actions.act_window',
                res_model: 'larr.land.acquisition',
                res_id: acquisitionId,
                view_mode: 'form',
                target: 'current'
            });
        }
    });

    core.action_registry.add('larr_dashboard', LARRDashboard);

    return LARRDashboard;
}); 