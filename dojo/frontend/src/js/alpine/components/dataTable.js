/**
 * Enterprise Data Table Component for DefectDojo
 *
 * This is DefectDojo's first Alpine.js component, establishing patterns for:
 * - How Alpine components are registered
 * - How Django data is passed to Alpine
 * - How Alpine components interact with Django forms/CSRF
 *
 * Usage in Django templates:
 * <div x-data="dataTable({
 *   data: {{ findings_json|safe }},
 *   columns: {{ columns_json|safe }},
 *   csrfToken: '{{ csrf_token }}',
 *   bulkActionUrl: '{% url "finding_bulk_update_all" %}'
 * })">
 *   <!-- Table markup -->
 * </div>
 */

export default (config = {}) => ({
        // ============================================
        // STATE
        // ============================================

        // Data
        data: config.data || [],
        columns: config.columns || [],
        filteredData: [],

        // Selection
        selected: [],
        selectAll: false,

        // Sorting
        sortColumn: config.defaultSort || null,
        sortDirection: config.defaultSortDir || 'asc',

        // Expansion
        expandedRows: [],

        // Virtual Scrolling
        rowHeight: config.rowHeight || 48,
        visibleRows: 20,
        scrollTop: 0,
        containerHeight: 0,

        // Configuration
        csrfToken: config.csrfToken || '',
        bulkActionUrl: config.bulkActionUrl || '',
        idField: config.idField || 'id',

        // UI State
        showBulkActions: false,
        isLoading: false,

        // Column Customization
        columnWidths: {},
        hiddenColumns: [],
        columnOrder: [],
        showColumnCustomizer: false,

        // Column Resizing
        resizingColumn: null,
        resizeStartX: 0,
        resizeStartWidth: 0,

        // ============================================
        // INITIALIZATION
        // ============================================

        init() {
            this.filteredData = [...this.data];

            // Load user preferences from localStorage
            this.loadColumnPreferences();

            // Initialize column order if not set
            if (this.columnOrder.length === 0) {
                this.columnOrder = this.columns.map(col => col.key);
            }

            // Apply initial sort if specified
            if (this.sortColumn) {
                this.sortData();
            }

            // Calculate visible rows based on container
            this.$nextTick(() => {
                this.calculateVisibleRows();
                // Sync column widths after initial render
                setTimeout(() => this.syncColumnWidths(), 100);
            });

            // Set up scroll listener for virtual scrolling
            this.$watch('scrollTop', () => {
                this.calculateVisibleRows();
            });

            // Watch selection changes
            this.$watch('selected', (value) => {
                this.showBulkActions = value.length > 0;
                this.selectAll = value.length === this.filteredData.length && value.length > 0;
            });

            // Sync column widths on window resize
            window.addEventListener('resize', () => {
                this.syncColumnWidths();
            });

            // Watch for changes to column preferences and auto-save
            this.$watch('columnWidths', () => {
                this.saveColumnPreferences();
            });

            this.$watch('hiddenColumns', () => {
                this.saveColumnPreferences();
            });

            this.$watch('columnOrder', () => {
                this.saveColumnPreferences();
            });
        },

        // ============================================
        // COLUMN CUSTOMIZATION - LOCALSTORAGE
        // ============================================

        getStorageKey() {
            // Generate unique key per table type
            // Try to detect table type from columns or context
            const tableType = this.columns.find(col => col.key === 'severity') ? 'findings'
                            : this.columns.find(col => col.key === 'product_type') ? 'products'
                            : this.columns.find(col => col.key === 'target_start') ? 'engagements'
                            : 'default';
            return `dataTable_${tableType}_columns`;
        },

        loadColumnPreferences() {
            const key = this.getStorageKey();
            const stored = localStorage.getItem(key);

            if (stored) {
                try {
                    const preferences = JSON.parse(stored);
                    this.columnWidths = preferences.widths || {};
                    this.hiddenColumns = preferences.hidden || [];
                    this.columnOrder = preferences.order || [];
                } catch (e) {
                    console.error('Failed to load column preferences:', e);
                }
            }
        },

        saveColumnPreferences() {
            const key = this.getStorageKey();
            const preferences = {
                widths: this.columnWidths,
                hidden: this.hiddenColumns,
                order: this.columnOrder
            };

            try {
                localStorage.setItem(key, JSON.stringify(preferences));
            } catch (e) {
                console.error('Failed to save column preferences:', e);
            }
        },

        resetColumnPreferences() {
            const key = this.getStorageKey();
            localStorage.removeItem(key);
            this.columnWidths = {};
            this.hiddenColumns = [];
            this.columnOrder = this.columns.map(col => col.key);
        },

        // ============================================
        // COLUMN RESIZING
        // ============================================

        startResize(columnKey, event) {
            // Prevent text selection during drag
            event.preventDefault();

            this.resizingColumn = columnKey;
            this.resizeStartX = event.clientX;

            // Get current width of the column
            const th = event.target.closest('th');
            if (th) {
                this.resizeStartWidth = th.offsetWidth;
            }

            // Add global mouse event listeners
            document.addEventListener('mousemove', this.doResize.bind(this));
            document.addEventListener('mouseup', this.stopResize.bind(this));

            // Add resizing class to body for cursor
            document.body.classList.add('col-resizing');
        },

        doResize(event) {
            if (!this.resizingColumn) return;

            // Calculate new width based on mouse movement
            const deltaX = event.clientX - this.resizeStartX;
            const newWidth = Math.max(80, Math.min(800, this.resizeStartWidth + deltaX));

            // Update column width in state (will trigger auto-save)
            this.columnWidths[this.resizingColumn] = newWidth;

            // Apply width to header cells immediately
            const headerTable = this.$refs.headerTable;
            if (headerTable) {
                const headerCells = headerTable.querySelectorAll('thead th');
                const columnIndex = this.getOrderedColumns().findIndex(col => col.key === this.resizingColumn);

                if (headerCells[columnIndex + 2]) { // +2 for checkbox and expand columns
                    headerCells[columnIndex + 2].style.width = newWidth + 'px';
                    headerCells[columnIndex + 2].style.minWidth = newWidth + 'px';
                    headerCells[columnIndex + 2].style.maxWidth = newWidth + 'px';
                }
            }

            // Apply width to body cells immediately
            const bodyTable = this.$refs.bodyTable;
            if (bodyTable) {
                const bodyCells = bodyTable.querySelectorAll(`tbody td:nth-child(${this.getOrderedColumns().findIndex(col => col.key === this.resizingColumn) + 3})`);
                bodyCells.forEach(cell => {
                    cell.style.width = newWidth + 'px';
                    cell.style.minWidth = newWidth + 'px';
                    cell.style.maxWidth = newWidth + 'px';
                });
            }
        },

        stopResize() {
            if (!this.resizingColumn) return;

            // Remove global mouse event listeners
            document.removeEventListener('mousemove', this.doResize);
            document.removeEventListener('mouseup', this.stopResize);

            // Remove resizing class from body
            document.body.classList.remove('col-resizing');

            // Clear resizing state
            this.resizingColumn = null;
            this.resizeStartX = 0;
            this.resizeStartWidth = 0;
        },

        getColumnWidth(columnKey) {
            return this.columnWidths[columnKey] || null;
        },

        syncColumnWidths() {
            // Get header and body tables
            const headerTable = this.$refs.headerTable;
            const bodyTable = this.$refs.bodyTable;

            if (!headerTable || !bodyTable) return;

            // Get all cells from first body row
            const bodyRow = bodyTable.querySelector('tbody tr');
            if (!bodyRow) return;

            const bodyCells = bodyRow.querySelectorAll('td');
            const headerCells = headerTable.querySelectorAll('thead th');

            // Apply body cell widths to header cells
            bodyCells.forEach((bodyCell, index) => {
                if (headerCells[index]) {
                    const width = bodyCell.offsetWidth;
                    headerCells[index].style.width = width + 'px';
                    headerCells[index].style.minWidth = width + 'px';
                    headerCells[index].style.maxWidth = width + 'px';
                }
            });
        },

        // ============================================
        // VIRTUAL SCROLLING
        // ============================================

        get totalHeight() {
            return this.filteredData.length * this.rowHeight;
        },

        get startIndex() {
            return Math.floor(this.scrollTop / this.rowHeight);
        },

        get endIndex() {
            return Math.min(
                this.startIndex + this.visibleRows + 2, // Buffer rows
                this.filteredData.length
            );
        },

        get visibleData() {
            return this.filteredData.slice(this.startIndex, this.endIndex);
        },

        get offsetY() {
            return this.startIndex * this.rowHeight;
        },

        calculateVisibleRows() {
            if (this.$refs.tableContainer) {
                this.containerHeight = this.$refs.tableContainer.clientHeight;
                this.visibleRows = Math.ceil(this.containerHeight / this.rowHeight) + 1;
            }
        },

        handleScroll(event) {
            this.scrollTop = event.target.scrollTop;
        },

        // ============================================
        // SORTING
        // ============================================

        sort(column) {
            if (this.sortColumn === column) {
                this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortColumn = column;
                this.sortDirection = 'asc';
            }
            this.sortData();
        },

        sortData() {
            if (!this.sortColumn) return;

            const col = this.columns.find(c => c.key === this.sortColumn);
            const sortType = col?.sortType || 'string';

            this.filteredData.sort((a, b) => {
                let valA = a[this.sortColumn];
                let valB = b[this.sortColumn];

                // Handle null/undefined
                if (valA == null) valA = '';
                if (valB == null) valB = '';

                let comparison = 0;

                switch (sortType) {
                    case 'number':
                        comparison = Number(valA) - Number(valB);
                        break;

                    case 'date':
                        comparison = new Date(valA) - new Date(valB);
                        break;

                    case 'severity':
                        comparison = this.getSeverityWeight(valA) - this.getSeverityWeight(valB);
                        break;

                    default: // string
                        comparison = String(valA).localeCompare(String(valB));
                }

                return this.sortDirection === 'asc' ? comparison : -comparison;
            });
        },

        getSeverityWeight(severity) {
            const weights = {
                'Critical': 5,
                'High': 4,
                'Medium': 3,
                'Low': 2,
                'Info': 1
            };
            return weights[severity] || 0;
        },

        getSortIcon(column) {
            if (this.sortColumn !== column) return 'sort';
            return this.sortDirection === 'asc' ? 'sort-asc' : 'sort-desc';
        },

        // ============================================
        // SELECTION
        // ============================================

        toggleSelect(id) {
            const index = this.selected.indexOf(id);
            if (index === -1) {
                this.selected.push(id);
            } else {
                this.selected.splice(index, 1);
            }
        },

        toggleSelectAll() {
            if (this.selectAll) {
                this.selected = [];
            } else {
                this.selected = this.filteredData.map(row => row[this.idField]);
            }
        },

        isSelected(id) {
            return this.selected.includes(id);
        },

        clearSelection() {
            this.selected = [];
        },

        // Select by severity (matches current DefectDojo pattern)
        selectBySeverity(severity) {
            const ids = this.filteredData
                .filter(row => row.severity === severity)
                .map(row => row[this.idField]);

            // Add to selection (don't replace)
            ids.forEach(id => {
                if (!this.selected.includes(id)) {
                    this.selected.push(id);
                }
            });
        },

        // ============================================
        // ROW EXPANSION
        // ============================================

        toggleExpand(id) {
            const index = this.expandedRows.indexOf(id);
            if (index === -1) {
                this.expandedRows.push(id);
            } else {
                this.expandedRows.splice(index, 1);
            }
        },

        isExpanded(id) {
            return this.expandedRows.includes(id);
        },

        collapseAll() {
            this.expandedRows = [];
        },

        // ============================================
        // FILTERING
        // ============================================

        filter(filters) {
            this.filteredData = this.data.filter(row => {
                return Object.entries(filters).every(([key, value]) => {
                    if (!value) return true;

                    const rowValue = row[key];
                    if (Array.isArray(value)) {
                        return value.includes(rowValue);
                    }
                    return String(rowValue).toLowerCase().includes(String(value).toLowerCase());
                });
            });

            // Re-apply sort after filtering
            this.sortData();

            // Clear selection when filtering
            this.selected = [];
        },

        search(query) {
            if (!query) {
                this.filteredData = [...this.data];
            } else {
                const lowerQuery = query.toLowerCase();
                this.filteredData = this.data.filter(row => {
                    return Object.values(row).some(value =>
                        String(value).toLowerCase().includes(lowerQuery)
                    );
                });
            }
            this.sortData();
        },

        resetFilters() {
            this.filteredData = [...this.data];
            this.sortData();
        },

        // ============================================
        // BULK ACTIONS
        // ============================================

        submitBulkAction(action) {
            if (this.selected.length === 0) return;

            // Create form dynamically (matches Django pattern)
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = this.bulkActionUrl;

            // Add CSRF token
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrfmiddlewaretoken';
            csrfInput.value = this.csrfToken;
            form.appendChild(csrfInput);

            // Add action
            const actionInput = document.createElement('input');
            actionInput.type = 'hidden';
            actionInput.name = 'bulk_action';
            actionInput.value = action;
            form.appendChild(actionInput);

            // Add selected IDs (matches Django's expected format)
            this.selected.forEach(id => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'finding_to_update';
                input.value = id;
                form.appendChild(input);
            });

            document.body.appendChild(form);
            form.submit();
        },

        // ============================================
        // KEYBOARD NAVIGATION
        // ============================================

        focusedRowIndex: -1,

        handleKeydown(event) {
            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    this.focusNextRow();
                    break;

                case 'ArrowUp':
                    event.preventDefault();
                    this.focusPreviousRow();
                    break;

                case 'Enter':
                case ' ':
                    event.preventDefault();
                    if (this.focusedRowIndex >= 0) {
                        const row = this.visibleData[this.focusedRowIndex - this.startIndex];
                        if (row) {
                            this.toggleExpand(row[this.idField]);
                        }
                    }
                    break;

                case 'Escape':
                    this.collapseAll();
                    this.clearSelection();
                    break;
            }
        },

        focusNextRow() {
            if (this.focusedRowIndex < this.filteredData.length - 1) {
                this.focusedRowIndex++;
                this.scrollToRow(this.focusedRowIndex);
            }
        },

        focusPreviousRow() {
            if (this.focusedRowIndex > 0) {
                this.focusedRowIndex--;
                this.scrollToRow(this.focusedRowIndex);
            }
        },

        scrollToRow(index) {
            const rowTop = index * this.rowHeight;
            const rowBottom = rowTop + this.rowHeight;

            if (this.$refs.tableContainer) {
                const container = this.$refs.tableContainer;

                if (rowTop < this.scrollTop) {
                    container.scrollTop = rowTop;
                } else if (rowBottom > this.scrollTop + this.containerHeight) {
                    container.scrollTop = rowBottom - this.containerHeight;
                }
            }
        },

        // ============================================
        // UTILITY METHODS
        // ============================================

        getRowId(row) {
            return row[this.idField];
        },

        getCellValue(row, column) {
            return row[column.key];
        },

        // Column customization utilities
        getOrderedColumns() {
            // Return columns in the order specified by columnOrder
            if (this.columnOrder.length === 0) {
                return this.columns;
            }

            const orderedCols = [];
            this.columnOrder.forEach(key => {
                const col = this.columns.find(c => c.key === key);
                if (col) {
                    orderedCols.push(col);
                }
            });

            // Add any columns not in columnOrder (newly added columns)
            this.columns.forEach(col => {
                if (!this.columnOrder.includes(col.key)) {
                    orderedCols.push(col);
                }
            });

            return orderedCols;
        },

        getVisibleColumns() {
            return this.getOrderedColumns().filter(col => !this.hiddenColumns.includes(col.key));
        },

        isColumnVisible(columnKey) {
            return !this.hiddenColumns.includes(columnKey);
        },

        toggleColumnVisibility(columnKey) {
            const index = this.hiddenColumns.indexOf(columnKey);
            if (index > -1) {
                // Show column
                this.hiddenColumns.splice(index, 1);
            } else {
                // Hide column - but ensure at least one column remains visible
                const visibleCount = this.columns.length - this.hiddenColumns.length;
                if (visibleCount > 1) {
                    this.hiddenColumns.push(columnKey);
                } else {
                    console.warn('Cannot hide all columns - at least one must remain visible');
                }
            }
        },

        moveColumn(fromIndex, toIndex) {
            const newOrder = [...this.columnOrder];
            const [movedColumn] = newOrder.splice(fromIndex, 1);
            newOrder.splice(toIndex, 0, movedColumn);
            this.columnOrder = newOrder;
        },

        startColumnDrag(columnKey, event) {
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', columnKey);
            event.target.classList.add('dragging');
        },

        onColumnDragOver(event) {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
        },

        dropColumn(targetColumnKey, event) {
            event.preventDefault();

            const draggedColumnKey = event.dataTransfer.getData('text/plain');
            if (draggedColumnKey === targetColumnKey) return;

            const fromIndex = this.columnOrder.indexOf(draggedColumnKey);
            const toIndex = this.columnOrder.indexOf(targetColumnKey);

            if (fromIndex !== -1 && toIndex !== -1) {
                this.moveColumn(fromIndex, toIndex);
            }

            // Remove dragging class from all headers
            document.querySelectorAll('th.dragging').forEach(th => {
                th.classList.remove('dragging');
            });
        },

        onColumnDragEnd(event) {
            event.target.classList.remove('dragging');
        },

        formatCell(value, column) {
            if (column.formatter) {
                return column.formatter(value);
            }
            return value;
        },

        // Export data (for copy/download functionality)
        exportData(format = 'json') {
            const exportData = this.filteredData.map(row => {
                const exportRow = {};
                this.columns.forEach(col => {
                    if (!col.excludeFromExport) {
                        exportRow[col.label || col.key] = row[col.key];
                    }
                });
                return exportRow;
            });

            if (format === 'json') {
                return JSON.stringify(exportData, null, 2);
            } else if (format === 'csv') {
                return this.toCSV(exportData);
            }

            return exportData;
        },

        toCSV(data) {
            if (data.length === 0) return '';

            const headers = Object.keys(data[0]);
            const rows = data.map(row =>
                headers.map(header => {
                    let cell = row[header];
                    if (cell == null) cell = '';
                    cell = String(cell).replace(/"/g, '""');
                    return `"${cell}"`;
                }).join(',')
            );

            return [headers.join(','), ...rows].join('\n');
        },

        // Get summary statistics
        get stats() {
            return {
                total: this.data.length,
                filtered: this.filteredData.length,
                selected: this.selected.length
            };
        }
});
