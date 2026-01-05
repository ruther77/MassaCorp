import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  invoicesApi,
  paymentsApi,
  bankMovementsApi,
  bankAccountsApi,
  treasuryApi,
  budgetApi,
  dueDatesApi,
  financeAnalyticsApi,
  referentialsApi,
} from '../api/finance';
import type {
  Invoice,
  InvoiceFilters,
  Payment,
  BankMovementFilters,
  BankAccount,
  Budget,
  DueDateFilters,
} from '../types/finance';

// ============================================
// Query Keys
// ============================================

export const financeKeys = {
  all: ['finance'] as const,

  // Factures
  invoices: () => [...financeKeys.all, 'invoices'] as const,
  invoicesList: (filters: InvoiceFilters, page: number) =>
    [...financeKeys.invoices(), 'list', filters, page] as const,
  invoiceDetail: (id: number) => [...financeKeys.invoices(), 'detail', id] as const,
  invoiceStats: (filters?: InvoiceFilters) => [...financeKeys.invoices(), 'stats', filters] as const,

  // Paiements
  payments: () => [...financeKeys.all, 'payments'] as const,
  paymentsList: (page: number) => [...financeKeys.payments(), 'list', page] as const,
  paymentDetail: (id: number) => [...financeKeys.payments(), 'detail', id] as const,

  // Mouvements bancaires
  bankMovements: () => [...financeKeys.all, 'bank-movements'] as const,
  bankMovementsList: (filters: BankMovementFilters, page: number) =>
    [...financeKeys.bankMovements(), 'list', filters, page] as const,

  // Comptes bancaires
  bankAccounts: () => [...financeKeys.all, 'bank-accounts'] as const,
  bankAccountDetail: (id: number) => [...financeKeys.bankAccounts(), 'detail', id] as const,

  // Trésorerie
  treasury: () => [...financeKeys.all, 'treasury'] as const,
  treasurySummary: () => [...financeKeys.treasury(), 'summary'] as const,
  treasuryForecast: (days: number) => [...financeKeys.treasury(), 'forecast', days] as const,

  // Budget
  budgets: () => [...financeKeys.all, 'budgets'] as const,
  budgetsList: (exerciceId?: number, costCenterId?: number) =>
    [...financeKeys.budgets(), 'list', exerciceId, costCenterId] as const,
  budgetSummary: (exerciceId: number) => [...financeKeys.budgets(), 'summary', exerciceId] as const,

  // Échéances
  dueDates: () => [...financeKeys.all, 'due-dates'] as const,
  dueDatesList: (filters: DueDateFilters, page: number) =>
    [...financeKeys.dueDates(), 'list', filters, page] as const,
  dueDatesUpcoming: (days: number) => [...financeKeys.dueDates(), 'upcoming', days] as const,
  dueDatesOverdue: () => [...financeKeys.dueDates(), 'overdue'] as const,

  // Analytics
  analytics: () => [...financeKeys.all, 'analytics'] as const,
  kpis: () => [...financeKeys.analytics(), 'kpis'] as const,

  // Référentiels
  referentials: () => [...financeKeys.all, 'referentials'] as const,
  suppliers: () => [...financeKeys.referentials(), 'suppliers'] as const,
  costCenters: () => [...financeKeys.referentials(), 'cost-centers'] as const,
  expenseCategories: () => [...financeKeys.referentials(), 'expense-categories'] as const,
  fiscalYears: () => [...financeKeys.referentials(), 'fiscal-years'] as const,
};

// ============================================
// Factures Hooks
// ============================================

export function useInvoices(filters: InvoiceFilters = {}, page = 1, perPage = 20) {
  return useQuery({
    queryKey: financeKeys.invoicesList(filters, page),
    queryFn: () => invoicesApi.getAll(filters, page, perPage),
    staleTime: 30 * 1000, // 30 secondes
  });
}

export function useInvoice(id: number) {
  return useQuery({
    queryKey: financeKeys.invoiceDetail(id),
    queryFn: () => invoicesApi.getById(id),
    enabled: !!id,
  });
}

export function useInvoiceStats(filters?: InvoiceFilters) {
  return useQuery({
    queryKey: financeKeys.invoiceStats(filters),
    queryFn: () => invoicesApi.getStats(filters),
    staleTime: 60 * 1000,
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Invoice>) => invoicesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

export function useUpdateInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Invoice> }) =>
      invoicesApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: financeKeys.invoiceDetail(id) });
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

export function useDeleteInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => invoicesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

export function useUpdateInvoiceStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, statut }: { id: number; statut: string }) =>
      invoicesApi.updateStatus(id, statut),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: financeKeys.invoiceDetail(id) });
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

// ============================================
// Paiements Hooks
// ============================================

export function usePayments(page = 1, perPage = 20) {
  return useQuery({
    queryKey: financeKeys.paymentsList(page),
    queryFn: () => paymentsApi.getAll(page, perPage),
    staleTime: 30 * 1000,
  });
}

export function usePayment(id: number) {
  return useQuery({
    queryKey: financeKeys.paymentDetail(id),
    queryFn: () => paymentsApi.getById(id),
    enabled: !!id,
  });
}

export function useCreatePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Payment>) => paymentsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.payments() });
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

export function useAllocatePayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      paymentId,
      invoiceId,
      amount,
    }: {
      paymentId: number;
      invoiceId: number;
      amount: number;
    }) => paymentsApi.allocate(paymentId, invoiceId, amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.payments() });
      queryClient.invalidateQueries({ queryKey: financeKeys.invoices() });
    },
  });
}

// ============================================
// Mouvements bancaires Hooks
// ============================================

export function useBankMovements(filters: BankMovementFilters = {}, page = 1, perPage = 50) {
  return useQuery({
    queryKey: financeKeys.bankMovementsList(filters, page),
    queryFn: () => bankMovementsApi.getAll(filters, page, perPage),
    staleTime: 60 * 1000,
  });
}

export function useReconcileBankMovement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ movementId, paymentId }: { movementId: number; paymentId: number }) =>
      bankMovementsApi.reconcile(movementId, paymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.bankMovements() });
      queryClient.invalidateQueries({ queryKey: financeKeys.treasury() });
    },
  });
}

export function useImportBankStatement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ accountId, file }: { accountId: number; file: File }) =>
      bankMovementsApi.importStatement(accountId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.bankMovements() });
      queryClient.invalidateQueries({ queryKey: financeKeys.bankAccounts() });
      queryClient.invalidateQueries({ queryKey: financeKeys.treasury() });
    },
  });
}

// ============================================
// Comptes bancaires Hooks
// ============================================

export function useBankAccounts() {
  return useQuery({
    queryKey: financeKeys.bankAccounts(),
    queryFn: () => bankAccountsApi.getAll(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useBankAccount(id: number) {
  return useQuery({
    queryKey: financeKeys.bankAccountDetail(id),
    queryFn: () => bankAccountsApi.getById(id),
    enabled: !!id,
  });
}

export function useCreateBankAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<BankAccount>) => bankAccountsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.bankAccounts() });
    },
  });
}

// ============================================
// Trésorerie Hooks
// ============================================

export function useTreasurySummary() {
  return useQuery({
    queryKey: financeKeys.treasurySummary(),
    queryFn: () => treasuryApi.getSummary(),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000, // Refresh toutes les 5 minutes
  });
}

export function useTreasuryForecast(days = 30) {
  return useQuery({
    queryKey: financeKeys.treasuryForecast(days),
    queryFn: () => treasuryApi.getForecast(days),
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================
// Budget Hooks
// ============================================

export function useBudgets(exerciceId?: number, costCenterId?: number) {
  return useQuery({
    queryKey: financeKeys.budgetsList(exerciceId, costCenterId),
    queryFn: () => budgetApi.getAll(exerciceId, costCenterId),
    staleTime: 2 * 60 * 1000,
  });
}

export function useBudgetSummary(exerciceId: number) {
  return useQuery({
    queryKey: financeKeys.budgetSummary(exerciceId),
    queryFn: () => budgetApi.getSummary(exerciceId),
    enabled: !!exerciceId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCreateBudget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Budget>) => budgetApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.budgets() });
    },
  });
}

export function useValidateBudget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => budgetApi.validate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: financeKeys.budgets() });
    },
  });
}

// ============================================
// Échéances Hooks
// ============================================

export function useDueDates(filters: DueDateFilters = {}, page = 1, perPage = 50) {
  return useQuery({
    queryKey: financeKeys.dueDatesList(filters, page),
    queryFn: () => dueDatesApi.getAll(filters, page, perPage),
    staleTime: 60 * 1000,
  });
}

export function useUpcomingDueDates(days = 7) {
  return useQuery({
    queryKey: financeKeys.dueDatesUpcoming(days),
    queryFn: () => dueDatesApi.getUpcoming(days),
    staleTime: 60 * 1000,
  });
}

export function useOverdueDueDates() {
  return useQuery({
    queryKey: financeKeys.dueDatesOverdue(),
    queryFn: () => dueDatesApi.getOverdue(),
    staleTime: 60 * 1000,
  });
}

// ============================================
// Analytics Hooks
// ============================================

export function useFinanceKPIs() {
  return useQuery({
    queryKey: financeKeys.kpis(),
    queryFn: () => financeAnalyticsApi.getKPIs(),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useCashFlowChart(period: 'week' | 'month' | 'quarter' | 'year' = 'month') {
  return useQuery({
    queryKey: [...financeKeys.analytics(), 'cashflow', period],
    queryFn: () => financeAnalyticsApi.getCashFlowChart(period),
    staleTime: 5 * 60 * 1000,
  });
}

export function useExpensesByCategory(startDate: string, endDate: string) {
  return useQuery({
    queryKey: [...financeKeys.analytics(), 'expenses-by-category', startDate, endDate],
    queryFn: () => financeAnalyticsApi.getExpensesByCategory(startDate, endDate),
    enabled: !!startDate && !!endDate,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAgingReport(type: 'fournisseur' | 'client') {
  return useQuery({
    queryKey: [...financeKeys.analytics(), 'aging', type],
    queryFn: () => financeAnalyticsApi.getAgingReport(type),
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================
// Référentiels Hooks
// ============================================

export function useSuppliers() {
  return useQuery({
    queryKey: financeKeys.suppliers(),
    queryFn: () => referentialsApi.getSuppliers(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useCostCenters() {
  return useQuery({
    queryKey: financeKeys.costCenters(),
    queryFn: () => referentialsApi.getCostCenters(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useExpenseCategories() {
  return useQuery({
    queryKey: financeKeys.expenseCategories(),
    queryFn: () => referentialsApi.getExpenseCategories(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useFiscalYears() {
  return useQuery({
    queryKey: financeKeys.fiscalYears(),
    queryFn: () => referentialsApi.getFiscalYears(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useActiveFiscalYear() {
  return useQuery({
    queryKey: [...financeKeys.fiscalYears(), 'active'],
    queryFn: () => referentialsApi.getActiveFiscalYear(),
    staleTime: 10 * 60 * 1000,
  });
}

// ============================================
// Invalidation Helpers
// ============================================

export function useInvalidateFinance() {
  const queryClient = useQueryClient();

  return {
    invalidateAll: () => queryClient.invalidateQueries({ queryKey: financeKeys.all }),
    invalidateInvoices: () => queryClient.invalidateQueries({ queryKey: financeKeys.invoices() }),
    invalidatePayments: () => queryClient.invalidateQueries({ queryKey: financeKeys.payments() }),
    invalidateTreasury: () => queryClient.invalidateQueries({ queryKey: financeKeys.treasury() }),
    invalidateBudgets: () => queryClient.invalidateQueries({ queryKey: financeKeys.budgets() }),
    invalidateDueDates: () => queryClient.invalidateQueries({ queryKey: financeKeys.dueDates() }),
  };
}
