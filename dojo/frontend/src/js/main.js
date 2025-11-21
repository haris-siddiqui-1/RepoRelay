/**
 * DefectDojo Modern Frontend - Main Entry Point
 *
 * This file initializes Alpine.js and loads all components.
 */

import Alpine from 'alpinejs';

// Import Alpine components
import darkMode from './alpine/components/darkMode.js';
import dropdown from './alpine/components/dropdown.js';
import modal from './alpine/components/modal.js';
import toast from './alpine/components/toast.js';
import dataTable from './alpine/components/dataTable.js';

// Import chart utilities
import { initializeCharts } from './charts/index.js';

// Import utility functions
import { debounce, throttle } from './utils/helpers.js';

// Register Alpine components
Alpine.data('darkMode', darkMode);
Alpine.data('dropdown', dropdown);
Alpine.data('modal', modal);
Alpine.data('toast', toast);
Alpine.data('dataTable', dataTable);

// Make utility functions globally available
window.dd = {
  debounce,
  throttle,
  initializeCharts,
};

// Initialize Alpine
Alpine.start();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  console.log('DefectDojo Modern UI initialized');

  // Initialize charts if present
  if (document.querySelector('[data-chart]')) {
    initializeCharts();
  }

  // Check for saved dark mode preference
  if (localStorage.getItem('darkMode') === 'true' ||
      (!localStorage.getItem('darkMode') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  }
});

// Export Alpine for external use
window.Alpine = Alpine;

export default Alpine;
