// Auth
export { useAuth } from './useAuth';

// Data fetching (existing)
export { useProducts, useProductDetail, useFamilies, useInvalidateCatalog } from './useProducts';

// State management
export { useLocalStorage, useSessionStorage } from './useLocalStorage';
export { useModal, useMultiModal, useConfirmModal } from './useModal';
export type { UseModalResult, UseMultiModalResult, UseConfirmModalResult } from './useModal';

// Data handling
export { usePagination, useClientPagination } from './usePagination';
export type { PaginationState, PaginationResult, UsePaginationOptions } from './usePagination';

export { useSort, useClientSort } from './useSort';
export type { SortDirection, SortState, UseSortOptions, UseSortResult } from './useSort';

export { useFilter, useClientFilter, filterUtils } from './useFilter';
export type { FilterValue, FilterState, UseFilterOptions, UseFilterResult } from './useFilter';

// Utilities
export { useDebounce } from './useDebounce';
export { useToast } from '../components/ui/Toast';
export { useClipboard, useClipboardRead } from './useClipboard';
export type { UseClipboardOptions, UseClipboardResult, UseClipboardReadResult } from './useClipboard';

export { useOnClickOutside, useOnClickOutsideMultiple, useClickOutsideState } from './useOnClickOutside';

export { useMediaQuery, useBreakpoint, useCurrentBreakpoint, useResponsive, breakpoints } from './useMediaQuery';
export type { Breakpoint } from './useMediaQuery';

export { useAsync, useAsyncRetry, usePolling } from './useAsync';
export type { AsyncStatus, AsyncState, UseAsyncResult, UseAsyncRetryOptions } from './useAsync';

export { useKeyPress, useKeyboardShortcuts, useEscapeKey, useEnterKey, useArrowNavigation, useListNavigation } from './useKeyboard';
export type { KeyboardShortcut } from './useKeyboard';

// Finance
export {
  // Factures
  useInvoices,
  useInvoice,
  useInvoiceStats,
  useCreateInvoice,
  useUpdateInvoice,
  useDeleteInvoice,
  useUpdateInvoiceStatus,
  // Paiements
  usePayments,
  usePayment,
  useCreatePayment,
  useAllocatePayment,
  // Mouvements bancaires
  useBankMovements,
  useReconcileBankMovement,
  useImportBankStatement,
  // Comptes bancaires
  useBankAccounts,
  useBankAccount,
  useCreateBankAccount,
  // Trésorerie
  useTreasurySummary,
  useTreasuryForecast,
  // Budget
  useBudgets,
  useBudgetSummary,
  useCreateBudget,
  useValidateBudget,
  // Échéances
  useDueDates,
  useUpcomingDueDates,
  useOverdueDueDates,
  // Analytics
  useFinanceKPIs,
  useCashFlowChart,
  useExpensesByCategory,
  useAgingReport,
  // Référentiels
  useSuppliers,
  useCostCenters,
  useExpenseCategories,
  useFiscalYears,
  useActiveFiscalYear,
  // Utils
  useInvalidateFinance,
  financeKeys,
} from './useFinance';
