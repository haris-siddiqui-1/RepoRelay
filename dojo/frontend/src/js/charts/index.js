/**
 * Chart.js Initialization and Utilities
 *
 * Centralized chart configuration and initialization for DefectDojo
 */

import { Chart, registerables } from 'chart.js';

// Register Chart.js components
Chart.register(...registerables);

// Default Chart.js configuration for DefectDojo
const defaultConfig = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        usePointStyle: true,
        padding: 15,
        font: {
          family: 'Inter, sans-serif',
          size: 12,
        },
      },
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      titleFont: {
        family: 'Inter, sans-serif',
        size: 13,
      },
      bodyFont: {
        family: 'Inter, sans-serif',
        size: 12,
      },
      padding: 12,
      borderColor: 'rgba(255, 255, 255, 0.1)',
      borderWidth: 1,
    },
  },
};

/**
 * DefectDojo color palette for charts
 */
export const colors = {
  critical: '#DC2626',
  high: '#EA580C',
  medium: '#D97706',
  low: '#2563EB',
  info: '#64748B',
  success: '#16A34A',
  warning: '#CA8A04',
  primary: '#3B82F6',
};

/**
 * Initialize all charts on the page
 */
export function initializeCharts() {
  const chartElements = document.querySelectorAll('[data-chart]');

  chartElements.forEach((element) => {
    const type = element.dataset.chart;
    const dataAttr = element.dataset.chartData;

    if (!dataAttr) {
      console.warn('Chart element missing data-chart-data attribute', element);
      return;
    }

    try {
      const data = JSON.parse(dataAttr);
      createChart(element, type, data);
    } catch (error) {
      console.error('Failed to parse chart data', error, element);
    }
  });
}

/**
 * Create a chart instance
 */
export function createChart(element, type, data, customConfig = {}) {
  const ctx = element.getContext('2d');
  const config = mergeConfig(defaultConfig, customConfig);

  return new Chart(ctx, {
    type,
    data,
    options: config,
  });
}

/**
 * Create a severity pie chart
 */
export function createSeverityPieChart(element, severityData) {
  const data = {
    labels: ['Critical', 'High', 'Medium', 'Low', 'Info'],
    datasets: [{
      data: [
        severityData.critical || 0,
        severityData.high || 0,
        severityData.medium || 0,
        severityData.low || 0,
        severityData.info || 0,
      ],
      backgroundColor: [
        colors.critical,
        colors.high,
        colors.medium,
        colors.low,
        colors.info,
      ],
      borderWidth: 0,
    }],
  };

  return createChart(element, 'pie', data);
}

/**
 * Create a severity trend line chart
 */
export function createSeverityTrendChart(element, trendData) {
  const data = {
    labels: trendData.labels || [],
    datasets: [
      {
        label: 'Critical',
        data: trendData.critical || [],
        borderColor: colors.critical,
        backgroundColor: `${colors.critical}20`,
        tension: 0.4,
      },
      {
        label: 'High',
        data: trendData.high || [],
        borderColor: colors.high,
        backgroundColor: `${colors.high}20`,
        tension: 0.4,
      },
      {
        label: 'Medium',
        data: trendData.medium || [],
        borderColor: colors.medium,
        backgroundColor: `${colors.medium}20`,
        tension: 0.4,
      },
      {
        label: 'Low',
        data: trendData.low || [],
        borderColor: colors.low,
        backgroundColor: `${colors.low}20`,
        tension: 0.4,
      },
    ],
  };

  return createChart(element, 'line', data, {
    scales: {
      y: {
        beginAtZero: true,
        ticks: {
          precision: 0,
        },
      },
    },
  });
}

/**
 * Create a bar chart
 */
export function createBarChart(element, data, options = {}) {
  return createChart(element, 'bar', data, options);
}

/**
 * Merge configuration objects
 */
function mergeConfig(...configs) {
  return configs.reduce((merged, config) => {
    return { ...merged, ...config };
  }, {});
}

/**
 * Destroy chart instance
 */
export function destroyChart(chart) {
  if (chart && typeof chart.destroy === 'function') {
    chart.destroy();
  }
}

// Export Chart.js for external use
export { Chart };
