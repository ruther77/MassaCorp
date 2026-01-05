import { apiClient } from './client';
import type {
  Invoice,
  InvoiceLine,
  InvoiceFilters,
  Payment,
  PaymentAllocation,
  BankMovement,
  BankMovementFilters,
  BankAccount,
  TreasuryPosition,
  TreasurySummary,
  CashFlowForecast,
  Budget,
  BudgetSummary,
  DueDate,
  DueDateFilters,
  FinanceKPIs,
  FinanceStats,
  PaginatedResponse,
  Supplier,
  CostCenter,
  ExpenseCategory,
  FiscalYear,
} from '../types/finance';

// ============================================
// Base URL
// ============================================

const FINANCE_BASE = '/api/v1/finance';

// ============================================
// Factures
// ============================================

export const invoicesApi = {
  // Liste des factures
  getAll: async (
    filters: InvoiceFilters = {},
    page = 1,
    perPage = 20
  ): Promise<PaginatedResponse<Invoice>> => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    });

    const response = await apiClient.get(`${FINANCE_BASE}/invoices?${params}`);
    return response.data;
  },

  // Détail d'une facture
  getById: async (id: number): Promise<Invoice> => {
    const response = await apiClient.get(`${FINANCE_BASE}/invoices/${id}`);
    return response.data;
  },

  // Créer une facture
  create: async (data: Partial<Invoice>): Promise<Invoice> => {
    const response = await apiClient.post(`${FINANCE_BASE}/invoices`, data);
    return response.data;
  },

  // Modifier une facture
  update: async (id: number, data: Partial<Invoice>): Promise<Invoice> => {
    const response = await apiClient.put(`${FINANCE_BASE}/invoices/${id}`, data);
    return response.data;
  },

  // Supprimer une facture
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/invoices/${id}`);
  },

  // Changer le statut
  updateStatus: async (id: number, statut: string): Promise<Invoice> => {
    const response = await apiClient.patch(`${FINANCE_BASE}/invoices/${id}/status`, { statut });
    return response.data;
  },

  // Lignes de facture
  getLines: async (invoiceId: number): Promise<InvoiceLine[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/invoices/${invoiceId}/lines`);
    return response.data;
  },

  addLine: async (invoiceId: number, line: Partial<InvoiceLine>): Promise<InvoiceLine> => {
    const response = await apiClient.post(`${FINANCE_BASE}/invoices/${invoiceId}/lines`, line);
    return response.data;
  },

  updateLine: async (invoiceId: number, lineId: number, line: Partial<InvoiceLine>): Promise<InvoiceLine> => {
    const response = await apiClient.put(`${FINANCE_BASE}/invoices/${invoiceId}/lines/${lineId}`, line);
    return response.data;
  },

  deleteLine: async (invoiceId: number, lineId: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/invoices/${invoiceId}/lines/${lineId}`);
  },

  // Stats
  getStats: async (filters?: InvoiceFilters): Promise<FinanceStats> => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          params.set(key, String(value));
        }
      });
    }
    const response = await apiClient.get(`${FINANCE_BASE}/invoices/stats?${params}`);
    return response.data;
  },

  // Upload document
  uploadDocument: async (invoiceId: number, file: File): Promise<{ url: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(
      `${FINANCE_BASE}/invoices/${invoiceId}/document`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
};

// ============================================
// Paiements
// ============================================

export const paymentsApi = {
  getAll: async (page = 1, perPage = 20): Promise<PaginatedResponse<Payment>> => {
    const response = await apiClient.get(`${FINANCE_BASE}/payments?page=${page}&per_page=${perPage}`);
    return response.data;
  },

  getById: async (id: number): Promise<Payment> => {
    const response = await apiClient.get(`${FINANCE_BASE}/payments/${id}`);
    return response.data;
  },

  create: async (data: Partial<Payment>): Promise<Payment> => {
    const response = await apiClient.post(`${FINANCE_BASE}/payments`, data);
    return response.data;
  },

  update: async (id: number, data: Partial<Payment>): Promise<Payment> => {
    const response = await apiClient.put(`${FINANCE_BASE}/payments/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/payments/${id}`);
  },

  // Affectation paiement <-> facture
  allocate: async (
    paymentId: number,
    invoiceId: number,
    amount: number
  ): Promise<PaymentAllocation> => {
    const response = await apiClient.post(`${FINANCE_BASE}/payments/${paymentId}/allocate`, {
      facture_id: invoiceId,
      montant: amount,
    });
    return response.data;
  },

  removeAllocation: async (paymentId: number, allocationId: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/payments/${paymentId}/allocations/${allocationId}`);
  },

  getAllocations: async (paymentId: number): Promise<PaymentAllocation[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/payments/${paymentId}/allocations`);
    return response.data;
  },
};

// ============================================
// Mouvements bancaires
// ============================================

export const bankMovementsApi = {
  getAll: async (
    filters: BankMovementFilters = {},
    page = 1,
    perPage = 50
  ): Promise<PaginatedResponse<BankMovement>> => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    });

    const response = await apiClient.get(`${FINANCE_BASE}/bank-movements?${params}`);
    return response.data;
  },

  getById: async (id: number): Promise<BankMovement> => {
    const response = await apiClient.get(`${FINANCE_BASE}/bank-movements/${id}`);
    return response.data;
  },

  // Rapprochement automatique
  reconcile: async (movementId: number, paymentId: number): Promise<BankMovement> => {
    const response = await apiClient.post(`${FINANCE_BASE}/bank-movements/${movementId}/reconcile`, {
      paiement_id: paymentId,
    });
    return response.data;
  },

  // Catégoriser
  categorize: async (movementId: number, categoryId: number): Promise<BankMovement> => {
    const response = await apiClient.patch(`${FINANCE_BASE}/bank-movements/${movementId}/categorize`, {
      categorie_depense_id: categoryId,
    });
    return response.data;
  },

  // Import relevé bancaire
  importStatement: async (accountId: number, file: File): Promise<{ imported: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post(
      `${FINANCE_BASE}/bank-accounts/${accountId}/import`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },
};

// ============================================
// Comptes bancaires
// ============================================

export const bankAccountsApi = {
  getAll: async (): Promise<BankAccount[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/bank-accounts`);
    return response.data;
  },

  getById: async (id: number): Promise<BankAccount> => {
    const response = await apiClient.get(`${FINANCE_BASE}/bank-accounts/${id}`);
    return response.data;
  },

  create: async (data: Partial<BankAccount>): Promise<BankAccount> => {
    const response = await apiClient.post(`${FINANCE_BASE}/bank-accounts`, data);
    return response.data;
  },

  update: async (id: number, data: Partial<BankAccount>): Promise<BankAccount> => {
    const response = await apiClient.put(`${FINANCE_BASE}/bank-accounts/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/bank-accounts/${id}`);
  },

  getBalance: async (id: number): Promise<{ solde: number; date: string }> => {
    const response = await apiClient.get(`${FINANCE_BASE}/bank-accounts/${id}/balance`);
    return response.data;
  },
};

// ============================================
// Trésorerie
// ============================================

export const treasuryApi = {
  getSummary: async (): Promise<TreasurySummary> => {
    const response = await apiClient.get(`${FINANCE_BASE}/treasury/summary`);
    return response.data;
  },

  getPositions: async (date?: string): Promise<TreasuryPosition[]> => {
    const params = date ? `?date=${date}` : '';
    const response = await apiClient.get(`${FINANCE_BASE}/treasury/positions${params}`);
    return response.data;
  },

  getForecast: async (days = 30): Promise<CashFlowForecast[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/treasury/forecast?days=${days}`);
    return response.data;
  },

  getHistory: async (startDate: string, endDate: string): Promise<TreasuryPosition[]> => {
    const response = await apiClient.get(
      `${FINANCE_BASE}/treasury/history?start_date=${startDate}&end_date=${endDate}`
    );
    return response.data;
  },
};

// ============================================
// Budget
// ============================================

export const budgetApi = {
  getAll: async (exerciceId?: number, costCenterId?: number): Promise<Budget[]> => {
    const params = new URLSearchParams();
    if (exerciceId) params.set('exercice_id', String(exerciceId));
    if (costCenterId) params.set('cost_center_id', String(costCenterId));

    const response = await apiClient.get(`${FINANCE_BASE}/budgets?${params}`);
    return response.data;
  },

  getById: async (id: number): Promise<Budget> => {
    const response = await apiClient.get(`${FINANCE_BASE}/budgets/${id}`);
    return response.data;
  },

  create: async (data: Partial<Budget>): Promise<Budget> => {
    const response = await apiClient.post(`${FINANCE_BASE}/budgets`, data);
    return response.data;
  },

  update: async (id: number, data: Partial<Budget>): Promise<Budget> => {
    const response = await apiClient.put(`${FINANCE_BASE}/budgets/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${FINANCE_BASE}/budgets/${id}`);
  },

  getSummary: async (exerciceId: number): Promise<BudgetSummary> => {
    const response = await apiClient.get(`${FINANCE_BASE}/budgets/summary?exercice_id=${exerciceId}`);
    return response.data;
  },

  // Validation budget
  validate: async (id: number): Promise<Budget> => {
    const response = await apiClient.post(`${FINANCE_BASE}/budgets/${id}/validate`);
    return response.data;
  },
};

// ============================================
// Échéancier
// ============================================

export const dueDatesApi = {
  getAll: async (
    filters: DueDateFilters = {},
    page = 1,
    perPage = 50
  ): Promise<PaginatedResponse<DueDate>> => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));

    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.set(key, String(value));
      }
    });

    const response = await apiClient.get(`${FINANCE_BASE}/due-dates?${params}`);
    return response.data;
  },

  getUpcoming: async (days = 7): Promise<DueDate[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/due-dates/upcoming?days=${days}`);
    return response.data;
  },

  getOverdue: async (): Promise<DueDate[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/due-dates/overdue`);
    return response.data;
  },
};

// ============================================
// KPIs et Analytics
// ============================================

export const financeAnalyticsApi = {
  getKPIs: async (): Promise<FinanceKPIs> => {
    const response = await apiClient.get(`${FINANCE_BASE}/analytics/kpis`);
    return response.data;
  },

  getCashFlowChart: async (period: 'week' | 'month' | 'quarter' | 'year'): Promise<Array<{
    date: string;
    encaissements: number;
    decaissements: number;
    solde: number;
  }>> => {
    const response = await apiClient.get(`${FINANCE_BASE}/analytics/cashflow?period=${period}`);
    return response.data;
  },

  getExpensesByCategory: async (startDate: string, endDate: string): Promise<Array<{
    categorie_id: number;
    categorie_libelle: string;
    montant: number;
    pourcentage: number;
  }>> => {
    const response = await apiClient.get(
      `${FINANCE_BASE}/analytics/expenses-by-category?start_date=${startDate}&end_date=${endDate}`
    );
    return response.data;
  },

  getAgingReport: async (type: 'fournisseur' | 'client'): Promise<Array<{
    tranche: string;
    count: number;
    montant: number;
  }>> => {
    const response = await apiClient.get(`${FINANCE_BASE}/analytics/aging?type=${type}`);
    return response.data;
  },
};

// ============================================
// Référentiels
// ============================================

export const referentialsApi = {
  getSuppliers: async (): Promise<Supplier[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/suppliers`);
    return response.data;
  },

  getCostCenters: async (): Promise<CostCenter[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/cost-centers`);
    return response.data;
  },

  getExpenseCategories: async (): Promise<ExpenseCategory[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/expense-categories`);
    return response.data;
  },

  getFiscalYears: async (): Promise<FiscalYear[]> => {
    const response = await apiClient.get(`${FINANCE_BASE}/fiscal-years`);
    return response.data;
  },

  getActiveFiscalYear: async (): Promise<FiscalYear> => {
    const response = await apiClient.get(`${FINANCE_BASE}/fiscal-years/active`);
    return response.data;
  },
};

// Export groupé
export const financeApi = {
  invoices: invoicesApi,
  payments: paymentsApi,
  bankMovements: bankMovementsApi,
  bankAccounts: bankAccountsApi,
  treasury: treasuryApi,
  budget: budgetApi,
  dueDates: dueDatesApi,
  analytics: financeAnalyticsApi,
  referentials: referentialsApi,
};
