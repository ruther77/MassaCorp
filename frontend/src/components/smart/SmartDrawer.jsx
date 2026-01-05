import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import { X, ChevronLeft, ChevronRight, ChevronDown, Maximize2, Minimize2 } from 'lucide-react';
import { createPortal } from 'react-dom';

// ============================================================================
// SMART DRAWER - Panneau latéral contextuel avec animations
// ============================================================================

/**
 * SmartDrawer - Panneau de détail coulissant
 *
 * @param {boolean} open - État ouvert/fermé
 * @param {Function} onClose - Callback de fermeture
 * @param {string} title - Titre du drawer
 * @param {string} subtitle - Sous-titre optionnel
 * @param {React.ReactNode} children - Contenu du drawer
 * @param {string} position - 'right' | 'left' | 'bottom'
 * @param {string} size - 'sm' | 'md' | 'lg' | 'xl' | 'full'
 * @param {boolean} overlay - Afficher un overlay
 * @param {boolean} closeOnOverlayClick - Fermer au clic sur overlay
 * @param {boolean} closeOnEscape - Fermer avec Escape
 * @param {React.ReactNode} footer - Contenu du footer
 * @param {React.ReactNode} headerActions - Actions dans le header
 * @param {Function} onPrevious - Navigation vers précédent
 * @param {Function} onNext - Navigation vers suivant
 */
export default function SmartDrawer({
  open = false,
  onClose,
  title,
  subtitle,
  children,
  position = 'right',
  size = 'md',
  overlay = true,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  footer,
  headerActions,
  onPrevious,
  onNext,
  className,
  expandable = false,
  expanded: controlledExpanded,
  onExpandChange,
}) {
  const drawerRef = useRef(null);
  const [internalExpanded, setInternalExpanded] = useState(false);

  const expanded = controlledExpanded !== undefined ? controlledExpanded : internalExpanded;
  const setExpanded = (value) => {
    setInternalExpanded(value);
    onExpandChange?.(value);
  };

  // Fermer avec Escape
  useEffect(() => {
    if (!open || !closeOnEscape) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, closeOnEscape, onClose]);

  // Bloquer le scroll du body
  useEffect(() => {
    if (open) {
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      document.body.style.overflow = 'hidden';
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    } else {
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    }

    return () => {
      document.body.style.overflow = '';
      document.body.style.paddingRight = '';
    };
  }, [open]);

  // Focus management
  useEffect(() => {
    if (open && drawerRef.current) {
      const focusableElements = drawerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusableElements.length > 0) {
        focusableElements[0].focus();
      }
    }
  }, [open]);

  // Taille du drawer
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
    full: 'max-w-full',
  };

  // Animation variants
  const getVariants = () => {
    switch (position) {
      case 'left':
        return {
          hidden: { x: '-100%', opacity: 0 },
          visible: { x: 0, opacity: 1 },
          exit: { x: '-100%', opacity: 0 },
        };
      case 'bottom':
        return {
          hidden: { y: '100%', opacity: 0 },
          visible: { y: 0, opacity: 1 },
          exit: { y: '100%', opacity: 0 },
        };
      default:
        return {
          hidden: { x: '100%', opacity: 0 },
          visible: { x: 0, opacity: 1 },
          exit: { x: '100%', opacity: 0 },
        };
    }
  };

  const positionClasses = {
    right: 'right-0 top-0 h-full',
    left: 'left-0 top-0 h-full',
    bottom: 'bottom-0 left-0 w-full',
  };

  const drawerContent = (
    <AnimatePresence mode="wait">
      {open && (
        <>
          {/* Overlay */}
          {overlay && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={closeOnOverlayClick ? onClose : undefined}
              aria-hidden="true"
            />
          )}

          {/* Drawer */}
          <motion.div
            ref={drawerRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
            variants={getVariants()}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            className={clsx(
              'fixed z-50 flex flex-col bg-slate-900 shadow-2xl',
              'border-l border-white/10',
              positionClasses[position],
              position !== 'bottom' && (expanded ? 'w-full' : `w-full ${sizeClasses[size]}`),
              position === 'bottom' && 'max-h-[80vh]',
              className
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/95 backdrop-blur-sm">
              <div className="flex items-center gap-3">
                {/* Navigation */}
                {(onPrevious || onNext) && (
                  <div className="flex items-center gap-1 mr-2">
                    <button
                      type="button"
                      onClick={onPrevious}
                      disabled={!onPrevious}
                      className={clsx(
                        'p-1.5 rounded-lg transition-colors',
                        onPrevious
                          ? 'text-slate-300 hover:bg-white/10 hover:text-white'
                          : 'text-slate-600 cursor-not-allowed'
                      )}
                      aria-label="Élément précédent"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={onNext}
                      disabled={!onNext}
                      className={clsx(
                        'p-1.5 rounded-lg transition-colors',
                        onNext
                          ? 'text-slate-300 hover:bg-white/10 hover:text-white'
                          : 'text-slate-600 cursor-not-allowed'
                      )}
                      aria-label="Élément suivant"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                )}

                {/* Title */}
                <div>
                  <h2 id="drawer-title" className="text-lg font-semibold text-white">
                    {title}
                  </h2>
                  {subtitle && (
                    <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {headerActions}

                {/* Expand button */}
                {expandable && (
                  <button
                    type="button"
                    onClick={() => setExpanded(!expanded)}
                    className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    aria-label={expanded ? 'Réduire' : 'Agrandir'}
                  >
                    {expanded ? (
                      <Minimize2 className="h-4 w-4" />
                    ) : (
                      <Maximize2 className="h-4 w-4" />
                    )}
                  </button>
                )}

                {/* Close button */}
                <button
                  type="button"
                  onClick={onClose}
                  className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                  aria-label="Fermer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {children}
            </div>

            {/* Footer */}
            {footer && (
              <div className="px-6 py-4 border-t border-white/10 bg-slate-900/95 backdrop-blur-sm">
                {footer}
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );

  // Portal pour le rendu en dehors du DOM parent
  if (typeof window !== 'undefined') {
    return createPortal(drawerContent, document.body);
  }

  return drawerContent;
}

// ============================================================================
// DRAWER SECTIONS - Composants pour structurer le contenu
// ============================================================================

export function DrawerSection({ title, children, collapsible = false, defaultOpen = true }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="mb-6 last:mb-0">
      {title && (
        <div
          className={clsx(
            'flex items-center justify-between mb-3',
            collapsible && 'cursor-pointer'
          )}
          onClick={collapsible ? () => setIsOpen(!isOpen) : undefined}
        >
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {title}
          </h3>
          {collapsible && (
            <motion.div
              animate={{ rotate: isOpen ? 0 : -90 }}
              transition={{ duration: 0.2 }}
            >
              <ChevronDown className="h-4 w-4 text-slate-500" />
            </motion.div>
          )}
        </div>
      )}
      <AnimatePresence>
        {(!collapsible || isOpen) && (
          <motion.div
            initial={collapsible ? { height: 0, opacity: 0 } : false}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function DrawerField({ label, value, copyable = false, icon: Icon }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!copyable || !value) return;
    try {
      await navigator.clipboard.writeText(String(value));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [copyable, value]);

  return (
    <div className="flex items-start gap-3 py-2">
      {Icon && <Icon className="h-4 w-4 text-slate-500 mt-0.5 flex-shrink-0" />}
      <div className="flex-1 min-w-0">
        <dt className="text-xs text-slate-500 uppercase tracking-wide">{label}</dt>
        <dd
          className={clsx(
            'text-sm text-slate-200 mt-0.5',
            copyable && 'cursor-pointer hover:text-white group'
          )}
          onClick={handleCopy}
        >
          {value ?? <span className="text-slate-500">—</span>}
          {copyable && value && (
            <span className="ml-2 text-xs text-slate-500 group-hover:text-slate-400">
              {copied ? '✓ Copié' : '⌘ Copier'}
            </span>
          )}
        </dd>
      </div>
    </div>
  );
}

export function DrawerActions({ children, align = 'right' }) {
  return (
    <div
      className={clsx(
        'flex gap-3',
        align === 'right' && 'justify-end',
        align === 'center' && 'justify-center',
        align === 'left' && 'justify-start',
        align === 'between' && 'justify-between'
      )}
    >
      {children}
    </div>
  );
}

export function DrawerTabs({ tabs, activeTab, onTabChange }) {
  return (
    <div className="flex gap-1 p-1 bg-white/5 rounded-lg mb-4">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onTabChange(tab.id)}
          className={clsx(
            'flex-1 px-3 py-2 text-sm font-medium rounded-md transition-colors',
            activeTab === tab.id
              ? 'bg-white/10 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
