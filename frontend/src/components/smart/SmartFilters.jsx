import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import {
  Search,
  Filter,
  X,
  ChevronDown,
  Check,
  Calendar,
  Sparkles,
  Clock,
  Tag,
  RotateCcw,
} from 'lucide-react';
import useDebounce from '@/hooks/useDebounce';

// ============================================================================
// SMART FILTERS - Filtres intelligents avec suggestions et presets
// ============================================================================

/**
 * SmartFilters - Barre de filtres intelligente
 *
 * @param {Array} filters - Configuration des filtres
 * @param {Object} values - Valeurs actuelles des filtres
 * @param {Function} onChange - Callback de changement (key, value)
 * @param {Function} onReset - Callback de réinitialisation
 * @param {Array} suggestions - Suggestions de filtres rapides
 * @param {Array} presets - Presets de filtres sauvegardés
 * @param {boolean} searchable - Activer la recherche globale
 * @param {string} searchValue - Valeur de recherche
 * @param {Function} onSearchChange - Callback changement recherche
 * @param {string} searchPlaceholder - Placeholder de recherche
 */
export default function SmartFilters({
  filters = [],
  values = {},
  onChange,
  onReset,
  suggestions = [],
  presets = [],
  searchable = true,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Rechercher...',
  className,
}) {
  const [expandedFilter, setExpandedFilter] = useState(null);
  const [showPresets, setShowPresets] = useState(false);
  const debouncedSearch = useDebounce(searchValue, 300);

  // Compter les filtres actifs
  const activeCount = useMemo(() => {
    return Object.entries(values).filter(([key, value]) => {
      if (value === null || value === undefined || value === '') return false;
      if (Array.isArray(value) && value.length === 0) return false;
      return true;
    }).length;
  }, [values]);

  // Appliquer une suggestion
  const applySuggestion = useCallback((suggestion) => {
    Object.entries(suggestion.filters).forEach(([key, value]) => {
      onChange?.(key, value);
    });
  }, [onChange]);

  // Appliquer un preset
  const applyPreset = useCallback((preset) => {
    // Reset d'abord
    filters.forEach((f) => onChange?.(f.key, null));
    // Puis appliquer
    Object.entries(preset.filters).forEach(([key, value]) => {
      onChange?.(key, value);
    });
    setShowPresets(false);
  }, [filters, onChange]);

  return (
    <div className={clsx('space-y-3', className)}>
      {/* Barre principale */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Recherche */}
        {searchable && (
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchValue}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder={searchPlaceholder}
              className={clsx(
                'w-full pl-10 pr-10 py-2.5 text-sm rounded-xl',
                'bg-white/5 border border-white/10 text-white placeholder-slate-400',
                'focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50',
                'transition-all'
              )}
            />
            {searchValue && (
              <button
                type="button"
                onClick={() => onSearchChange?.('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        )}

        {/* Filtres rapides */}
        <div className="flex items-center gap-2">
          {filters.slice(0, 3).map((filter) => (
            <FilterDropdown
              key={filter.key}
              filter={filter}
              value={values[filter.key]}
              onChange={(value) => onChange?.(filter.key, value)}
              expanded={expandedFilter === filter.key}
              onToggle={() => setExpandedFilter(
                expandedFilter === filter.key ? null : filter.key
              )}
            />
          ))}

          {/* Plus de filtres */}
          {filters.length > 3 && (
            <MoreFiltersDropdown
              filters={filters.slice(3)}
              values={values}
              onChange={onChange}
            />
          )}
        </div>

        <div className="flex-1" />

        {/* Presets */}
        {presets.length > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowPresets(!showPresets)}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors',
                'border border-white/10 hover:bg-white/5 text-slate-300'
              )}
            >
              <Sparkles className="h-4 w-4" />
              Filtres rapides
              <ChevronDown className={clsx('h-4 w-4 transition-transform', showPresets && 'rotate-180')} />
            </button>

            <AnimatePresence>
              {showPresets && (
                <PresetsDropdown
                  presets={presets}
                  onSelect={applyPreset}
                  onClose={() => setShowPresets(false)}
                />
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Reset */}
        {activeCount > 0 && (
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            Réinitialiser ({activeCount})
          </button>
        )}
      </div>

      {/* Suggestions IA */}
      {suggestions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500 flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            Suggestions:
          </span>
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              type="button"
              onClick={() => applySuggestion(suggestion)}
              className={clsx(
                'px-2.5 py-1 text-xs rounded-full transition-colors',
                'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 border border-blue-500/20'
              )}
            >
              {suggestion.label}
            </button>
          ))}
        </div>
      )}

      {/* Tags des filtres actifs */}
      {activeCount > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(values).map(([key, value]) => {
            if (value === null || value === undefined || value === '') return null;
            if (Array.isArray(value) && value.length === 0) return null;

            const filter = filters.find((f) => f.key === key);
            if (!filter) return null;

            const displayValue = Array.isArray(value)
              ? value.length > 1 ? `${value.length} sélectionnés` : value[0]
              : filter.options?.find((o) => o.value === value)?.label || value;

            return (
              <motion.span
                key={key}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className={clsx(
                  'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full',
                  'bg-white/10 text-slate-200'
                )}
              >
                <span className="text-slate-400">{filter.label}:</span>
                <span className="font-medium">{displayValue}</span>
                <button
                  type="button"
                  onClick={() => onChange?.(key, null)}
                  className="p-0.5 hover:bg-white/20 rounded-full"
                >
                  <X className="h-3 w-3" />
                </button>
              </motion.span>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// FILTER DROPDOWN - Dropdown individuel pour un filtre
// ============================================================================

function FilterDropdown({ filter, value, onChange, expanded, onToggle }) {
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        onToggle();
      }
    };
    if (expanded) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [expanded, onToggle]);

  const hasValue = value !== null && value !== undefined && value !== '' &&
    !(Array.isArray(value) && value.length === 0);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={onToggle}
        className={clsx(
          'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all',
          'border',
          hasValue
            ? 'border-blue-500/50 bg-blue-500/10 text-blue-300'
            : 'border-white/10 hover:bg-white/5 text-slate-300'
        )}
      >
        {filter.icon && <filter.icon className="h-4 w-4" />}
        {filter.label}
        <ChevronDown className={clsx('h-4 w-4 transition-transform', expanded && 'rotate-180')} />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, y: -5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 mt-2 min-w-[200px] bg-slate-800 rounded-xl shadow-xl border border-white/10 py-2 z-30"
          >
            {filter.type === 'select' && (
              <SelectFilterContent
                options={filter.options || []}
                value={value}
                onChange={onChange}
                multiple={filter.multiple}
              />
            )}

            {filter.type === 'date' && (
              <DateFilterContent
                value={value}
                onChange={onChange}
                presets={filter.presets}
              />
            )}

            {filter.type === 'range' && (
              <RangeFilterContent
                value={value}
                onChange={onChange}
                min={filter.min}
                max={filter.max}
                step={filter.step}
                unit={filter.unit}
              />
            )}

            {filter.type === 'text' && (
              <TextFilterContent
                value={value}
                onChange={onChange}
                placeholder={filter.placeholder}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================================================
// FILTER CONTENTS
// ============================================================================

function SelectFilterContent({ options, value, onChange, multiple = false }) {
  const selectedValues = multiple ? (Array.isArray(value) ? value : []) : [value];

  const toggleValue = (optValue) => {
    if (multiple) {
      const newValues = selectedValues.includes(optValue)
        ? selectedValues.filter((v) => v !== optValue)
        : [...selectedValues, optValue];
      onChange(newValues.length > 0 ? newValues : null);
    } else {
      onChange(value === optValue ? null : optValue);
    }
  };

  return (
    <div className="max-h-64 overflow-y-auto">
      {options.map((option) => {
        const isSelected = selectedValues.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => toggleValue(option.value)}
            className={clsx(
              'w-full flex items-center gap-3 px-4 py-2 text-sm text-left transition-colors',
              isSelected ? 'bg-blue-500/20 text-blue-300' : 'text-slate-300 hover:bg-white/5'
            )}
          >
            <div className={clsx(
              'w-4 h-4 rounded flex items-center justify-center border transition-colors',
              isSelected ? 'bg-blue-500 border-blue-500' : 'border-slate-500'
            )}>
              {isSelected && <Check className="h-3 w-3 text-white" />}
            </div>
            {option.icon && <option.icon className="h-4 w-4 text-slate-400" />}
            <span className="flex-1">{option.label}</span>
            {option.count !== undefined && (
              <span className="text-xs text-slate-500">{option.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function DateFilterContent({ value, onChange, presets = [] }) {
  const defaultPresets = [
    { label: "Aujourd'hui", value: 'today' },
    { label: 'Hier', value: 'yesterday' },
    { label: '7 derniers jours', value: 'last7days' },
    { label: '30 derniers jours', value: 'last30days' },
    { label: 'Ce mois', value: 'thisMonth' },
    { label: 'Mois dernier', value: 'lastMonth' },
  ];

  const allPresets = presets.length > 0 ? presets : defaultPresets;

  return (
    <div className="p-2">
      <div className="space-y-1">
        {allPresets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => onChange(preset.value)}
            className={clsx(
              'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors text-left',
              value === preset.value
                ? 'bg-blue-500/20 text-blue-300'
                : 'text-slate-300 hover:bg-white/5'
            )}
          >
            <Clock className="h-4 w-4 text-slate-400" />
            {preset.label}
          </button>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-white/10">
        <label className="block text-xs text-slate-400 mb-2">Date personnalisée</label>
        <input
          type="date"
          value={typeof value === 'string' && !['today', 'yesterday', 'last7days', 'last30days', 'thisMonth', 'lastMonth'].includes(value) ? value : ''}
          onChange={(e) => onChange(e.target.value || null)}
          className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        />
      </div>
    </div>
  );
}

function RangeFilterContent({ value, onChange, min = 0, max = 100, step = 1, unit = '' }) {
  const [localValue, setLocalValue] = useState(value || { min, max });

  useEffect(() => {
    if (value) setLocalValue(value);
  }, [value]);

  const handleApply = () => {
    onChange(localValue);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label className="block text-xs text-slate-400 mb-1">Min</label>
          <input
            type="number"
            value={localValue.min}
            onChange={(e) => setLocalValue({ ...localValue, min: Number(e.target.value) })}
            min={min}
            max={max}
            step={step}
            className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
        </div>
        <span className="text-slate-500 mt-5">—</span>
        <div className="flex-1">
          <label className="block text-xs text-slate-400 mb-1">Max</label>
          <input
            type="number"
            value={localValue.max}
            onChange={(e) => setLocalValue({ ...localValue, max: Number(e.target.value) })}
            min={min}
            max={max}
            step={step}
            className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          />
        </div>
      </div>
      {unit && (
        <p className="text-xs text-slate-500 text-center">{unit}</p>
      )}
      <button
        type="button"
        onClick={handleApply}
        className="w-full py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
      >
        Appliquer
      </button>
    </div>
  );
}

function TextFilterContent({ value, onChange, placeholder }) {
  const [localValue, setLocalValue] = useState(value || '');

  return (
    <div className="p-3">
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onChange(localValue || null);
          }
        }}
        onBlur={() => onChange(localValue || null)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        autoFocus
      />
    </div>
  );
}

// ============================================================================
// MORE FILTERS DROPDOWN
// ============================================================================

function MoreFiltersDropdown({ filters, values, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const activeInMore = filters.filter((f) => {
    const v = values[f.key];
    return v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);
  }).length;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors border',
          activeInMore > 0
            ? 'border-blue-500/50 bg-blue-500/10 text-blue-300'
            : 'border-white/10 hover:bg-white/5 text-slate-300'
        )}
      >
        <Filter className="h-4 w-4" />
        Plus
        {activeInMore > 0 && (
          <span className="w-5 h-5 flex items-center justify-center text-xs bg-blue-500 text-white rounded-full">
            {activeInMore}
          </span>
        )}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -5, scale: 0.95 }}
            className="absolute top-full right-0 mt-2 w-72 bg-slate-800 rounded-xl shadow-xl border border-white/10 p-4 z-30"
          >
            <div className="space-y-4">
              {filters.map((filter) => (
                <div key={filter.key}>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
                    {filter.label}
                  </label>
                  {filter.type === 'select' && (
                    <select
                      value={values[filter.key] || ''}
                      onChange={(e) => onChange?.(filter.key, e.target.value || null)}
                      className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    >
                      <option value="">Tous</option>
                      {filter.options?.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  )}
                  {filter.type === 'text' && (
                    <input
                      type="text"
                      value={values[filter.key] || ''}
                      onChange={(e) => onChange?.(filter.key, e.target.value || null)}
                      placeholder={filter.placeholder}
                      className="w-full px-3 py-2 text-sm bg-white/5 border border-white/10 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                    />
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================================================
// PRESETS DROPDOWN
// ============================================================================

function PresetsDropdown({ presets, onSelect, onClose }) {
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <motion.div
      ref={dropdownRef}
      initial={{ opacity: 0, y: -5, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -5, scale: 0.95 }}
      className="absolute top-full right-0 mt-2 w-64 bg-slate-800 rounded-xl shadow-xl border border-white/10 py-2 z-30"
    >
      <div className="px-3 py-2 border-b border-white/10">
        <span className="text-xs font-semibold uppercase text-slate-400">Filtres rapides</span>
      </div>
      <div className="py-1">
        {presets.map((preset, index) => (
          <button
            key={index}
            type="button"
            onClick={() => onSelect(preset)}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left text-slate-300 hover:bg-white/5 transition-colors"
          >
            {preset.icon ? (
              <preset.icon className="h-4 w-4 text-slate-400" />
            ) : (
              <Tag className="h-4 w-4 text-slate-400" />
            )}
            <div className="flex-1">
              <div className="font-medium text-white">{preset.label}</div>
              {preset.description && (
                <div className="text-xs text-slate-500">{preset.description}</div>
              )}
            </div>
          </button>
        ))}
      </div>
    </motion.div>
  );
}

export { FilterDropdown, SelectFilterContent, DateFilterContent, RangeFilterContent };
