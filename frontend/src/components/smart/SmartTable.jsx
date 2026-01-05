import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import {
  Check,
  X,
  Pencil,
  Loader2,
  AlertCircle,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  MoreHorizontal,
  Eye,
  Trash2,
  Copy,
  ExternalLink,
} from 'lucide-react';
import useDebounce from '@/hooks/useDebounce';

// ============================================================================
// SMART TABLE - Table avec édition inline et actions contextuelles
// ============================================================================

/**
 * SmartTable - Table intelligente avec édition inline
 *
 * @param {Array} data - Données à afficher
 * @param {Array} columns - Configuration des colonnes
 * @param {Function} onUpdate - Callback de mise à jour (row, field, value) => Promise
 * @param {Function} onRowClick - Callback clic sur ligne
 * @param {Function} onRowAction - Callback action sur ligne
 * @param {boolean} loading - État de chargement
 * @param {string} emptyMessage - Message si aucune donnée
 */
export default function SmartTable({
  data = [],
  columns = [],
  onUpdate,
  onRowClick,
  onRowAction,
  loading = false,
  emptyMessage = 'Aucune donnée',
  getRowId = (row, index) => row.id ?? index,
  // Tri
  sortable = true,
  defaultSort = null,
  // Pagination
  pagination = true,
  pageSize: initialPageSize = 15,
  // Style
  compact = false,
  striped = true,
  highlightOnHover = true,
  // Sélection
  selectable = false,
  selectedRows = [],
  onSelectionChange,
  // Drawer
  showDrawer = false,
  drawerContent,
  selectedRow,
  onDrawerClose,
  className,
}) {
  // États
  const [editingCell, setEditingCell] = useState(null); // { rowId, columnKey }
  const [editValue, setEditValue] = useState('');
  const [savingCell, setSavingCell] = useState(null);
  const [errorCell, setErrorCell] = useState(null);
  const [sortConfig, setSortConfig] = useState(defaultSort);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [internalSelected, setInternalSelected] = useState(selectedRows);

  const inputRef = useRef(null);

  // Focus input when editing starts
  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingCell]);

  // Sync selection
  useEffect(() => {
    setInternalSelected(selectedRows);
  }, [selectedRows]);

  // Tri des données
  const sortedData = useMemo(() => {
    if (!sortConfig?.key) return data;

    return [...data].sort((a, b) => {
      const column = columns.find((c) => c.key === sortConfig.key);
      const aVal = column?.getValue ? column.getValue(a) : a[sortConfig.key];
      const bVal = column?.getValue ? column.getValue(b) : b[sortConfig.key];

      if (aVal === bVal) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      const comparison = typeof aVal === 'string'
        ? aVal.localeCompare(bVal, 'fr', { sensitivity: 'base' })
        : aVal < bVal ? -1 : 1;

      return sortConfig.direction === 'desc' ? -comparison : comparison;
    });
  }, [data, sortConfig, columns]);

  // Pagination
  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = useMemo(() => {
    if (!pagination) return sortedData;
    const start = (currentPage - 1) * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, currentPage, pageSize, pagination]);

  // Reset page when data changes
  useEffect(() => {
    setCurrentPage(1);
  }, [data.length, pageSize]);

  // Handlers
  const handleSort = useCallback((key) => {
    if (!sortable) return;
    setSortConfig((prev) => {
      if (prev?.key !== key) return { key, direction: 'asc' };
      if (prev.direction === 'asc') return { key, direction: 'desc' };
      return null;
    });
  }, [sortable]);

  const handleStartEdit = useCallback((rowId, columnKey, currentValue) => {
    setEditingCell({ rowId, columnKey });
    setEditValue(currentValue ?? '');
    setErrorCell(null);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingCell(null);
    setEditValue('');
    setErrorCell(null);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!editingCell || !onUpdate) return;

    const { rowId, columnKey } = editingCell;
    const row = data.find((r, i) => getRowId(r, i) === rowId);

    if (!row) {
      handleCancelEdit();
      return;
    }

    const column = columns.find((c) => c.key === columnKey);
    const oldValue = column?.getValue ? column.getValue(row) : row[columnKey];

    // Si la valeur n'a pas changé, annuler
    if (String(editValue) === String(oldValue ?? '')) {
      handleCancelEdit();
      return;
    }

    setSavingCell({ rowId, columnKey });
    setErrorCell(null);

    try {
      await onUpdate(row, columnKey, editValue);
      setEditingCell(null);
      setEditValue('');
    } catch (error) {
      setErrorCell({ rowId, columnKey, message: error.message || 'Erreur de sauvegarde' });
    } finally {
      setSavingCell(null);
    }
  }, [editingCell, editValue, onUpdate, data, columns, getRowId, handleCancelEdit]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      handleCancelEdit();
    }
  }, [handleSaveEdit, handleCancelEdit]);

  const handleSelectRow = useCallback((rowId) => {
    const newSelection = internalSelected.includes(rowId)
      ? internalSelected.filter((id) => id !== rowId)
      : [...internalSelected, rowId];
    setInternalSelected(newSelection);
    onSelectionChange?.(newSelection);
  }, [internalSelected, onSelectionChange]);

  const handleSelectAll = useCallback(() => {
    const currentIds = paginatedData.map((row, i) => getRowId(row, i));
    const allSelected = currentIds.every((id) => internalSelected.includes(id));

    const newSelection = allSelected
      ? internalSelected.filter((id) => !currentIds.includes(id))
      : [...new Set([...internalSelected, ...currentIds])];

    setInternalSelected(newSelection);
    onSelectionChange?.(newSelection);
  }, [paginatedData, internalSelected, getRowId, onSelectionChange]);

  // Render cell content
  const renderCell = useCallback((row, column, rowIndex) => {
    const rowId = getRowId(row, rowIndex);
    const value = column.getValue ? column.getValue(row) : row[column.key];
    const isEditing = editingCell?.rowId === rowId && editingCell?.columnKey === column.key;
    const isSaving = savingCell?.rowId === rowId && savingCell?.columnKey === column.key;
    const hasError = errorCell?.rowId === rowId && errorCell?.columnKey === column.key;
    const isEditable = column.editable !== false && onUpdate;

    // Mode édition
    if (isEditing) {
      return (
        <div className="flex items-center gap-1">
          <EditInput
            ref={inputRef}
            type={column.inputType || 'text'}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleSaveEdit}
            disabled={isSaving}
            error={hasError}
            className="flex-1"
          />
          {isSaving ? (
            <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
          ) : (
            <>
              <button
                type="button"
                onClick={handleSaveEdit}
                className="p-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/20 rounded"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={handleCancelEdit}
                className="p-1 text-slate-400 hover:text-slate-300 hover:bg-white/10 rounded"
              >
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      );
    }

    // Rendu personnalisé
    if (column.render) {
      return column.render(value, row, rowIndex);
    }

    // Rendu avec indicateur d'édition
    const content = value ?? <span className="text-slate-500">—</span>;

    if (isEditable) {
      return (
        <div
          className={clsx(
            'group flex items-center gap-2 cursor-pointer rounded px-1 -mx-1',
            'hover:bg-white/5 transition-colors',
            hasError && 'bg-rose-500/10'
          )}
          onClick={(e) => {
            e.stopPropagation();
            handleStartEdit(rowId, column.key, value);
          }}
        >
          <span className="flex-1">{content}</span>
          <Pencil className="h-3 w-3 text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />
          {hasError && (
            <span className="text-rose-400 text-xs">{errorCell.message}</span>
          )}
        </div>
      );
    }

    return content;
  }, [
    editingCell, editValue, savingCell, errorCell, getRowId,
    handleStartEdit, handleSaveEdit, handleCancelEdit, handleKeyDown, onUpdate
  ]);

  // Loading state
  if (loading && data.length === 0) {
    return <SmartTableSkeleton columns={columns.length} rows={5} />;
  }

  const allSelected = paginatedData.length > 0 &&
    paginatedData.every((row, i) => internalSelected.includes(getRowId(row, i)));

  return (
    <div className={clsx('relative', className)}>
      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-white/10 bg-white/5">
        <table className="w-full text-sm">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              {selectable && (
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={handleSelectAll}
                    className="h-4 w-4 rounded border-slate-500 text-blue-500 focus:ring-blue-500"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={clsx(
                    'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-300',
                    column.sortable !== false && sortable && 'cursor-pointer select-none hover:text-white',
                    column.align === 'right' && 'text-right',
                    column.align === 'center' && 'text-center',
                    column.width && `w-[${column.width}]`
                  )}
                  onClick={() => column.sortable !== false && handleSort(column.key)}
                >
                  <div className={clsx(
                    'flex items-center gap-1.5',
                    column.align === 'right' && 'justify-end',
                    column.align === 'center' && 'justify-center'
                  )}>
                    {column.header || column.key}
                    {column.sortable !== false && sortable && (
                      <SortIndicator
                        direction={sortConfig?.key === column.key ? sortConfig.direction : null}
                      />
                    )}
                  </div>
                </th>
              ))}
              {onRowAction && (
                <th className="w-10 px-3 py-3">
                  <span className="sr-only">Actions</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            <AnimatePresence mode="popLayout">
              {paginatedData.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length + (selectable ? 1 : 0) + (onRowAction ? 1 : 0)}
                    className="px-4 py-12 text-center text-slate-400"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                paginatedData.map((row, rowIndex) => {
                  const rowId = getRowId(row, rowIndex);
                  const isSelected = internalSelected.includes(rowId);
                  const isHighlighted = selectedRow && getRowId(selectedRow, 0) === rowId;

                  return (
                    <motion.tr
                      key={rowId}
                      layout
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 10 }}
                      transition={{ duration: 0.15 }}
                      className={clsx(
                        'transition-colors',
                        striped && rowIndex % 2 === 1 && 'bg-white/[0.02]',
                        isSelected && 'bg-blue-500/10',
                        isHighlighted && 'bg-purple-500/10 ring-1 ring-purple-500/30',
                        highlightOnHover && 'hover:bg-white/5',
                        onRowClick && 'cursor-pointer'
                      )}
                      onClick={() => onRowClick?.(row, rowIndex)}
                    >
                      {selectable && (
                        <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => handleSelectRow(rowId)}
                            className="h-4 w-4 rounded border-slate-500 text-blue-500 focus:ring-blue-500"
                          />
                        </td>
                      )}
                      {columns.map((column) => (
                        <td
                          key={column.key}
                          className={clsx(
                            compact ? 'px-4 py-2' : 'px-4 py-3',
                            'text-slate-200',
                            column.align === 'right' && 'text-right',
                            column.align === 'center' && 'text-center',
                            column.className
                          )}
                        >
                          {renderCell(row, column, rowIndex)}
                        </td>
                      ))}
                      {onRowAction && (
                        <td className="px-3 py-3" onClick={(e) => e.stopPropagation()}>
                          <RowActions row={row} rowIndex={rowIndex} onAction={onRowAction} />
                        </td>
                      )}
                    </motion.tr>
                  );
                })
              )}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pagination && totalPages > 1 && (
        <SmartPagination
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={sortedData.length}
          onPageChange={setCurrentPage}
          onPageSizeChange={setPageSize}
        />
      )}

      {/* Loading overlay */}
      {loading && data.length > 0 && (
        <div className="absolute inset-0 bg-slate-900/50 flex items-center justify-center rounded-xl">
          <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg">
            <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
            <span className="text-sm text-slate-300">Chargement...</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// COMPOSANTS AUXILIAIRES
// ============================================================================

function SortIndicator({ direction }) {
  if (!direction) {
    return <ChevronsUpDown className="h-3.5 w-3.5 text-slate-500" />;
  }
  return direction === 'asc'
    ? <ChevronUp className="h-3.5 w-3.5 text-blue-400" />
    : <ChevronDown className="h-3.5 w-3.5 text-blue-400" />;
}

function EditInput({ type, value, onChange, onKeyDown, onBlur, disabled, error, className, ...props }) {
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const baseClasses = clsx(
    'w-full px-2 py-1 text-sm rounded border bg-slate-800 text-white',
    'focus:outline-none focus:ring-2',
    error
      ? 'border-rose-500 focus:ring-rose-500'
      : 'border-blue-500 focus:ring-blue-500',
    disabled && 'opacity-50 cursor-not-allowed',
    className
  );

  if (type === 'number') {
    return (
      <input
        ref={inputRef}
        type="number"
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        disabled={disabled}
        className={baseClasses}
        {...props}
      />
    );
  }

  if (type === 'select' && props.options) {
    return (
      <select
        ref={inputRef}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        disabled={disabled}
        className={baseClasses}
        {...props}
      >
        {props.options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    );
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      disabled={disabled}
      className={baseClasses}
      {...props}
    />
  );
}

function RowActions({ row, rowIndex, onAction }) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const defaultActions = [
    { id: 'view', label: 'Voir détails', icon: Eye },
    { id: 'edit', label: 'Modifier', icon: Pencil },
    { id: 'duplicate', label: 'Dupliquer', icon: Copy },
    { id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true },
  ];

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-1.5 rounded hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -5 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -5 }}
            transition={{ duration: 0.1 }}
            className="absolute right-0 mt-1 w-44 bg-slate-800 rounded-lg shadow-xl border border-white/10 py-1 z-30"
          >
            {defaultActions.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => {
                  onAction(action.id, row, rowIndex);
                  setIsOpen(false);
                }}
                className={clsx(
                  'w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors',
                  action.destructive
                    ? 'text-rose-400 hover:bg-rose-500/20'
                    : 'text-slate-300 hover:bg-white/10 hover:text-white'
                )}
              >
                <action.icon className="h-4 w-4" />
                {action.label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SmartPagination({ currentPage, totalPages, pageSize, totalItems, onPageChange, onPageSizeChange }) {
  const start = (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, totalItems);

  return (
    <div className="flex items-center justify-between mt-4 px-2 text-sm">
      <div className="text-slate-400">
        {start}-{end} sur {totalItems}
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className={clsx(
            'px-3 py-1.5 rounded-lg transition-colors',
            currentPage === 1
              ? 'text-slate-600 cursor-not-allowed'
              : 'text-slate-300 hover:bg-white/10'
          )}
        >
          Précédent
        </button>

        <div className="flex items-center gap-1 mx-2">
          {[...Array(Math.min(5, totalPages))].map((_, i) => {
            let page;
            if (totalPages <= 5) {
              page = i + 1;
            } else if (currentPage <= 3) {
              page = i + 1;
            } else if (currentPage >= totalPages - 2) {
              page = totalPages - 4 + i;
            } else {
              page = currentPage - 2 + i;
            }

            return (
              <button
                key={page}
                type="button"
                onClick={() => onPageChange(page)}
                className={clsx(
                  'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                  page === currentPage
                    ? 'bg-blue-500 text-white'
                    : 'text-slate-300 hover:bg-white/10'
                )}
              >
                {page}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className={clsx(
            'px-3 py-1.5 rounded-lg transition-colors',
            currentPage === totalPages
              ? 'text-slate-600 cursor-not-allowed'
              : 'text-slate-300 hover:bg-white/10'
          )}
        >
          Suivant
        </button>
      </div>
    </div>
  );
}

function SmartTableSkeleton({ columns = 5, rows = 5 }) {
  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-white/5">
      <div className="bg-white/5 border-b border-white/10 px-4 py-3">
        <div className="flex gap-4">
          {[...Array(columns)].map((_, i) => (
            <div key={i} className="h-4 bg-white/10 rounded flex-1 animate-pulse" />
          ))}
        </div>
      </div>
      <div className="divide-y divide-white/5">
        {[...Array(rows)].map((_, rowIndex) => (
          <div key={rowIndex} className="px-4 py-3">
            <div className="flex gap-4">
              {[...Array(columns)].map((_, colIndex) => (
                <div
                  key={colIndex}
                  className="h-4 bg-white/10 rounded flex-1 animate-pulse"
                  style={{ animationDelay: `${(rowIndex * columns + colIndex) * 50}ms` }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export { SmartTableSkeleton };
