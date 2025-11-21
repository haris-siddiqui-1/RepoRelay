/**
 * GitHub Insights Dashboard
 *
 * Handles dashboard rendering, widget management, Chart.js integration,
 * and user configuration persistence.
 */

var GitHubInsightsDashboard = (function() {
    'use strict';

    var config = {
        apiBaseUrl: '/api/v2/github_insights/',
        csrfToken: '',
        charts: {},
        widgetConfig: [],
        availableInsights: [],
        filters: {
            product_type_id: null,
            days: 30
        },
        widgetCount: 10
    };

    /**
     * Initialize the dashboard
     */
    function init(options) {
        config.apiBaseUrl = options.apiBaseUrl;
        config.csrfToken = options.csrfToken;

        // Set up event handlers
        setupEventHandlers();

        // Load dashboard configuration and render
        loadDashboardConfiguration();
    }

    /**
     * Set up event handlers for dashboard controls
     */
    function setupEventHandlers() {
        // Filter controls
        $('#product-type-filter').on('change', function() {
            config.filters.product_type_id = $(this).val() || null;
            refreshDashboard();
        });

        $('#days-filter').on('change', function() {
            config.filters.days = parseInt($(this).val());
            refreshDashboard();
        });

        $('#widget-count').on('change', function() {
            config.widgetCount = parseInt($(this).val());
            refreshDashboard();
        });

        // Refresh button
        $('#refresh-dashboard').on('click', function() {
            refreshDashboard();
        });

        // Configure dashboard button
        $('#configure-dashboard').on('click', function() {
            showConfigurationModal();
        });

        // Save configuration button
        $('#save-configuration').on('click', function() {
            saveConfiguration();
        });
    }

    /**
     * Load dashboard configuration from API
     */
    function loadDashboardConfiguration() {
        $.ajax({
            url: config.apiBaseUrl + 'dashboard/',
            method: 'GET',
            headers: {
                'X-CSRFToken': config.csrfToken
            },
            success: function(response) {
                config.widgetConfig = response.widget_config || [];
                config.widgetCount = response.widget_count || 10;

                // If no widgets configured, set up default widgets
                if (config.widgetConfig.length === 0) {
                    config.widgetConfig = [
                        { insight_id: 'vuln_distribution', order: 0, size: 'medium', pinned: false },
                        { insight_id: 'most_recently_updated', order: 1, size: 'medium', pinned: false },
                        { insight_id: 'stale_repositories', order: 2, size: 'medium', pinned: false },
                        { insight_id: 'critical_vulns', order: 3, size: 'medium', pinned: false },
                        { insight_id: 'repos_missing_readme', order: 4, size: 'small', pinned: false },
                        { insight_id: 'repos_missing_ci', order: 5, size: 'small', pinned: false },
                        { insight_id: 'highest_commit_frequency', order: 6, size: 'medium', pinned: false },
                        { insight_id: 'most_active_contributors', order: 7, size: 'medium', pinned: false },
                        { insight_id: 'popular_languages', order: 8, size: 'small', pinned: false },
                        { insight_id: 'unassigned_repositories', order: 9, size: 'medium', pinned: false }
                    ];
                }

                // Update widget count selector
                $('#widget-count').val(config.widgetCount);

                // Render dashboard
                renderDashboard();
            },
            error: function(xhr, status, error) {
                console.error('Failed to load dashboard configuration:', error);
                showError('Failed to load dashboard configuration');
            }
        });
    }

    /**
     * Render the dashboard with configured widgets
     */
    function renderDashboard() {
        var $container = $('#dashboard-widgets');
        $container.empty();

        // If no widgets configured, show welcome message
        if (config.widgetConfig.length === 0) {
            $container.html(
                '<div class="placeholder-message">' +
                '<h3><i class="fa fa-info-circle"></i> No Widgets Configured</h3>' +
                '<p>Click "Configure Dashboard" to add insights to your dashboard.</p>' +
                '</div>'
            );
            return;
        }

        // Sort widgets: pinned first, then by order
        var sortedWidgets = config.widgetConfig.slice().sort(function(a, b) {
            if (a.pinned && !b.pinned) return -1;
            if (!a.pinned && b.pinned) return 1;
            return a.order - b.order;
        });

        // Determine which widgets to display
        var pinnedWidgets = sortedWidgets.filter(function(w) { return w.pinned; });
        var regularWidgets = sortedWidgets.filter(function(w) { return !w.pinned; });

        // Display all pinned widgets + top N regular widgets
        var widgetsToDisplay = pinnedWidgets.concat(
            regularWidgets.slice(0, config.widgetCount)
        );

        // Render each widget
        widgetsToDisplay.forEach(function(widget) {
            renderWidget(widget, $container);
        });
    }

    /**
     * Render a single widget
     */
    function renderWidget(widget, $container) {
        var widgetId = 'widget-' + widget.insight_id;

        // Create widget HTML structure
        var $widget = $('<div>')
            .addClass('insight-widget')
            .addClass(widget.pinned ? 'pinned-widget' : '')
            .attr('id', widgetId);

        var $header = $('<div>').addClass('widget-header');
        $header.append(
            '<div class="widget-title">' +
            '<strong>' + widget.insight_id + '</strong>' +
            (widget.pinned ? ' <span class="label label-primary">Pinned</span>' : '') +
            '</div>'
        );

        var $actions = $('<div>').addClass('widget-actions');
        $actions.append(
            '<button class="btn btn-xs btn-default" onclick="GitHubInsightsDashboard.refreshWidget(\'' + widget.insight_id + '\')">' +
            '<i class="fa fa-refresh"></i></button>'
        );

        $header.append($actions);
        $widget.append($header);

        var $body = $('<div>').addClass('widget-body');
        $body.append('<div class="loading-spinner"><i class="fa fa-spinner fa-spin"></i></div>');
        $widget.append($body);

        $container.append($widget);

        // Load widget data
        loadWidgetData(widget);
    }

    /**
     * Load data for a specific widget
     */
    function loadWidgetData(widget) {
        var widgetId = 'widget-' + widget.insight_id;
        var filters = $.extend({}, config.filters, widget.filters || {});

        // Build query string
        var queryParams = [];
        if (filters.days) queryParams.push('days=' + filters.days);
        if (filters.product_type_id) queryParams.push('product_type_id=' + filters.product_type_id);

        var url = config.apiBaseUrl + widget.insight_id + '/';
        if (queryParams.length > 0) {
            url += '?' + queryParams.join('&');
        }

        $.ajax({
            url: url,
            method: 'GET',
            headers: {
                'X-CSRFToken': config.csrfToken
            },
            success: function(response) {
                renderWidgetContent(widgetId, widget, response);
            },
            error: function(xhr, status, error) {
                console.error('Failed to load widget data:', error);
                $('#' + widgetId + ' .widget-body').html(
                    '<div class="alert alert-danger">Failed to load widget data</div>'
                );
            }
        });
    }

    /**
     * Render widget content based on insight data
     */
    function renderWidgetContent(widgetId, widget, data) {
        var $body = $('#' + widgetId + ' .widget-body');
        $body.empty();

        // Check for placeholder
        if (data.metadata && data.metadata.placeholder) {
            $body.html(
                '<div class="placeholder-message">' +
                '<p><i class="fa fa-info-circle"></i> ' + data.metadata.message + '</p>' +
                '</div>'
            );
            return;
        }

        // Render title
        if (data.title) {
            $body.append('<h4>' + data.title + '</h4>');
        }

        // Render chart or table based on chart_config
        if (data.chart_config) {
            renderChart(widgetId, data);
        } else if (Array.isArray(data.data)) {
            renderTable(widgetId, data.data);
        } else {
            $body.append('<p>No data available</p>');
        }

        // Add metadata footer
        if (data.metadata) {
            var metadataHtml = '<div class="text-muted" style="margin-top: 10px; font-size: 12px;">';
            metadataHtml += '<i class="fa fa-info-circle"></i> ';
            metadataHtml += 'Count: ' + (data.metadata.count || 0);
            if (data.metadata.timestamp) {
                var timestamp = new Date(data.metadata.timestamp);
                metadataHtml += ' | Updated: ' + timestamp.toLocaleString();
            }
            metadataHtml += '</div>';
            $body.append(metadataHtml);
        }
    }

    /**
     * Render a chart using Chart.js
     */
    function renderChart(widgetId, data) {
        var $body = $('#' + widgetId + ' .widget-body');
        var canvasId = widgetId + '-chart';

        var $chartContainer = $('<div>').addClass('widget-chart');
        var $canvas = $('<canvas>').attr('id', canvasId);
        $chartContainer.append($canvas);
        $body.append($chartContainer);

        var ctx = document.getElementById(canvasId).getContext('2d');
        var chartType = data.chart_config.type || 'bar';

        var chartData = {
            labels: data.data.labels || [],
            datasets: [{
                label: data.title || '',
                data: data.data.values || [],
                backgroundColor: data.data.colors || '#007bff',
                borderColor: data.data.colors || '#007bff',
                borderWidth: 1
            }]
        };

        var chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: chartType === 'pie' || chartType === 'doughnut'
                },
                title: {
                    display: !!data.chart_config.options.title,
                    text: data.chart_config.options.title || ''
                }
            }
        };

        // Add axis labels for bar/line charts
        if (chartType === 'bar' || chartType === 'line') {
            chartOptions.scales = {
                x: {
                    title: {
                        display: !!data.chart_config.options.xAxisLabel,
                        text: data.chart_config.options.xAxisLabel || ''
                    }
                },
                y: {
                    title: {
                        display: !!data.chart_config.options.yAxisLabel,
                        text: data.chart_config.options.yAxisLabel || ''
                    },
                    beginAtZero: true
                }
            };
        }

        // Destroy existing chart if exists
        if (config.charts[canvasId]) {
            config.charts[canvasId].destroy();
        }

        // Create new chart
        config.charts[canvasId] = new Chart(ctx, {
            type: chartType,
            data: chartData,
            options: chartOptions
        });
    }

    /**
     * Render a table with insight data
     */
    function renderTable(widgetId, data) {
        if (!data || data.length === 0) {
            $('#' + widgetId + ' .widget-body').append('<p>No data available</p>');
            return;
        }

        var $tableContainer = $('<div>').addClass('widget-table table-responsive');
        var tableId = widgetId + '-table';
        var $table = $('<table>')
            .addClass('table table-striped table-condensed')
            .attr('id', tableId);

        // Build table header from first row keys
        var keys = Object.keys(data[0]);
        var $thead = $('<thead>');
        var $headerRow = $('<tr>');
        keys.forEach(function(key) {
            $headerRow.append('<th>' + key.replace(/_/g, ' ').toUpperCase() + '</th>');
        });
        $thead.append($headerRow);
        $table.append($thead);

        // Build table body
        var $tbody = $('<tbody>');
        data.forEach(function(row) {
            var $row = $('<tr>');
            keys.forEach(function(key) {
                var value = row[key];

                // Format github_url as link
                if (key === 'github_url' && value) {
                    value = '<a href="' + value + '" target="_blank"><i class="fa-brands fa-github"></i></a>';
                }

                $row.append('<td>' + (value || '') + '</td>');
            });
            $tbody.append($row);
        });
        $table.append($tbody);

        $tableContainer.append($table);
        $('#' + widgetId + ' .widget-body').append($tableContainer);

        // Initialize DataTables for sorting, pagination, and search
        $('#' + tableId).DataTable({
            paging: true,
            pageLength: 10,
            lengthMenu: [[5, 10, 25, 50, -1], [5, 10, 25, 50, "All"]],
            searching: true,
            ordering: true,
            info: true,
            autoWidth: false,
            language: {
                search: "Filter:",
                lengthMenu: "Show _MENU_ entries",
                info: "Showing _START_ to _END_ of _TOTAL_ entries",
                infoEmpty: "Showing 0 to 0 of 0 entries",
                infoFiltered: "(filtered from _TOTAL_ total entries)",
                zeroRecords: "No matching records found",
                emptyTable: "No data available in table"
            }
        });
    }

    /**
     * Refresh entire dashboard
     */
    function refreshDashboard() {
        renderDashboard();
    }

    /**
     * Refresh a single widget
     */
    function refreshWidget(insightId) {
        var widget = config.widgetConfig.find(function(w) {
            return w.insight_id === insightId;
        });

        if (widget) {
            loadWidgetData(widget);
        }
    }

    /**
     * Show configuration modal
     */
    function showConfigurationModal() {
        // Use DOM manipulation instead of Bootstrap modal
        var modal = document.getElementById('configure-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.style.display = 'block';
            modal.setAttribute('aria-hidden', 'false');
        }
        loadAvailableInsights();
    }

    /**
     * Load available insights for configuration
     */
    function loadAvailableInsights() {
        var $container = $('#available-insights');
        $container.html('<div class="loading-spinner"><i class="fa fa-spinner fa-spin"></i></div>');

        $.ajax({
            url: config.apiBaseUrl,
            method: 'GET',
            headers: {
                'X-CSRFToken': config.csrfToken
            },
            success: function(response) {
                config.availableInsights = response.insights || [];
                renderInsightConfiguration();
            },
            error: function(xhr, status, error) {
                console.error('Failed to load insights:', error);
                $container.html('<div class="alert alert-danger">Failed to load insights</div>');
            }
        });
    }

    /**
     * Render insight configuration interface
     */
    function renderInsightConfiguration() {
        var $container = $('#available-insights');
        $container.empty();

        // Group insights by category
        var categories = {};
        config.availableInsights.forEach(function(insight) {
            if (!categories[insight.category]) {
                categories[insight.category] = [];
            }
            categories[insight.category].push(insight);
        });

        // Render each category
        Object.keys(categories).sort().forEach(function(category) {
            var $categorySection = $('<div>').addClass('panel panel-default');
            var $categoryHeader = $('<div>').addClass('panel-heading');
            $categoryHeader.append('<h5>' + category.toUpperCase() + '</h5>');
            $categorySection.append($categoryHeader);

            var $categoryBody = $('<div>').addClass('panel-body');

            categories[category].forEach(function(insight) {
                var isEnabled = config.widgetConfig.some(function(w) {
                    return w.insight_id === insight.insight_id;
                });

                var isPinned = config.widgetConfig.some(function(w) {
                    return w.insight_id === insight.insight_id && w.pinned;
                });

                var $insightRow = $('<div>').addClass('checkbox');
                var checkboxHtml = '<label>' +
                    '<input type="checkbox" class="insight-checkbox" data-insight-id="' + insight.insight_id + '" ' +
                    (isEnabled ? 'checked' : '') + '> ' +
                    '<strong>' + insight.name + '</strong> - ' + insight.description +
                    ' <span class="label label-info">' + insight.visualization_type + '</span>' +
                    '</label>';

                if (isEnabled) {
                    checkboxHtml += ' <button class="btn btn-xs btn-primary pin-insight" data-insight-id="' +
                        insight.insight_id + '">' +
                        '<i class="fa fa-thumb-tack"></i> ' + (isPinned ? 'Unpin' : 'Pin') + '</button>';
                }

                $insightRow.html(checkboxHtml);
                $categoryBody.append($insightRow);
            });

            $categorySection.append($categoryBody);
            $container.append($categorySection);
        });

        // Add event handlers for checkboxes and pin buttons
        $('.insight-checkbox').on('change', function() {
            var insightId = $(this).data('insight-id');
            var isChecked = $(this).is(':checked');

            if (isChecked) {
                addInsightToConfig(insightId);
            } else {
                removeInsightFromConfig(insightId);
            }
        });

        $('.pin-insight').on('click', function() {
            var insightId = $(this).data('insight-id');
            togglePinInsight(insightId);
        });
    }

    /**
     * Add insight to configuration
     */
    function addInsightToConfig(insightId) {
        var insight = config.availableInsights.find(function(i) {
            return i.insight_id === insightId;
        });

        if (insight && !config.widgetConfig.some(function(w) { return w.insight_id === insightId; })) {
            config.widgetConfig.push({
                insight_id: insightId,
                order: config.widgetConfig.length,
                size: 'medium',
                pinned: false,
                auto_refresh: false,
                filters: {}
            });
        }
    }

    /**
     * Remove insight from configuration
     */
    function removeInsightFromConfig(insightId) {
        config.widgetConfig = config.widgetConfig.filter(function(w) {
            return w.insight_id !== insightId;
        });
    }

    /**
     * Toggle pin status for insight
     */
    function togglePinInsight(insightId) {
        var widget = config.widgetConfig.find(function(w) {
            return w.insight_id === insightId;
        });

        if (widget) {
            widget.pinned = !widget.pinned;
            renderInsightConfiguration();  // Re-render to update button text
        }
    }

    /**
     * Save configuration to API
     */
    function saveConfiguration() {
        var configData = {
            widget_config: config.widgetConfig,
            widget_count: config.widgetCount
        };

        console.log('Saving dashboard configuration:', configData);

        $.ajax({
            url: config.apiBaseUrl + 'dashboard/',
            method: 'POST',
            headers: {
                'X-CSRFToken': config.csrfToken,
                'Content-Type': 'application/json'
            },
            data: JSON.stringify(configData),
            success: function(response) {
                console.log('Configuration saved successfully:', response);
                // Use DOM manipulation instead of Bootstrap modal
                var modal = document.getElementById('configure-modal');
                if (modal) {
                    modal.classList.add('hidden');
                    modal.style.display = 'none';
                    modal.setAttribute('aria-hidden', 'true');
                }
                showSuccess('Dashboard configuration saved');

                // Reload configuration from server to ensure consistency
                loadDashboardConfiguration();
            },
            error: function(xhr, status, error) {
                console.error('Failed to save configuration:', {
                    status: xhr.status,
                    statusText: xhr.statusText,
                    error: error,
                    responseText: xhr.responseText
                });

                var errorMessage = 'Failed to save configuration';
                if (xhr.status === 400 && xhr.responseJSON) {
                    errorMessage += ': ' + JSON.stringify(xhr.responseJSON);
                } else if (xhr.status === 403) {
                    errorMessage += ': Permission denied';
                } else if (xhr.status === 500) {
                    errorMessage += ': Server error';
                }

                showError(errorMessage);
            }
        });
    }

    /**
     * Show error message
     */
    function showError(message) {
        console.error('Dashboard error:', message);

        // Try to use Bootstrap alert if available, fallback to alert()
        var $alertContainer = $('#dashboard-alerts');
        if ($alertContainer.length === 0) {
            // Create alert container if it doesn't exist
            $alertContainer = $('<div>').attr('id', 'dashboard-alerts').css({
                'position': 'fixed',
                'top': '70px',
                'right': '20px',
                'z-index': '9999',
                'max-width': '400px'
            });
            $('body').append($alertContainer);
        }

        var $alert = $('<div>').addClass('alert alert-danger alert-dismissible fade in').attr('role', 'alert');
        $alert.html(
            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
            '<span aria-hidden="true">&times;</span></button>' +
            '<strong>Error:</strong> ' + message
        );

        $alertContainer.append($alert);

        // Auto-dismiss after 10 seconds
        setTimeout(function() {
            $alert.alert('close');
        }, 10000);
    }

    /**
     * Show success message
     */
    function showSuccess(message) {
        console.log('Dashboard success:', message);

        // Try to use Bootstrap alert if available
        var $alertContainer = $('#dashboard-alerts');
        if ($alertContainer.length === 0) {
            // Create alert container if it doesn't exist
            $alertContainer = $('<div>').attr('id', 'dashboard-alerts').css({
                'position': 'fixed',
                'top': '70px',
                'right': '20px',
                'z-index': '9999',
                'max-width': '400px'
            });
            $('body').append($alertContainer);
        }

        var $alert = $('<div>').addClass('alert alert-success alert-dismissible fade in').attr('role', 'alert');
        $alert.html(
            '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
            '<span aria-hidden="true">&times;</span></button>' +
            '<strong>Success:</strong> ' + message
        );

        $alertContainer.append($alert);

        // Auto-dismiss after 5 seconds
        setTimeout(function() {
            $alert.alert('close');
        }, 5000);
    }

    // Public API
    return {
        init: init,
        refreshWidget: refreshWidget,
        refreshDashboard: refreshDashboard
    };
})();
