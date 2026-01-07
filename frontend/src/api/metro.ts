import { apiClient } from './client';
import type {
  MetroSummary,
  MetroProduct,
  MetroProductsResponse,
  MetroFacturesResponse,
  MetroFactureDetail,
  MetroCategory,
  MetroDashboard,
  MetroCategoryStats,
  MetroTVAStats,
  MetroProductFilters,
} from '../types/metro';

const METRO_BASE = '/metro';

// ============================================
// Summary & Dashboard
// ============================================

export const metroApi = {
  getSummary: async (): Promise<MetroSummary> => {
    const response = await apiClient.get(`${METRO_BASE}/summary`);
    return response.data;
  },

  getDashboard: async (): Promise<MetroDashboard> => {
    const response = await apiClient.get(`${METRO_BASE}/dashboard`);
    return response.data;
  },

  // ============================================
  // Products
  // ============================================

  getProducts: async (filters: MetroProductFilters = {}): Promise<MetroProductsResponse> => {
    const params = new URLSearchParams();

    if (filters.search) params.set('search', filters.search);
    if (filters.famille) params.set('famille', filters.famille);
    if (filters.categorie) params.set('categorie', filters.categorie);
    if (filters.sort_by) params.set('sort_by', filters.sort_by);
    if (filters.sort_order) params.set('sort_order', filters.sort_order);
    if (filters.page) params.set('page', String(filters.page));
    if (filters.per_page) params.set('per_page', String(filters.per_page));

    const response = await apiClient.get(`${METRO_BASE}/products?${params}`);
    return response.data;
  },

  getProductById: async (productId: number): Promise<MetroProduct> => {
    const response = await apiClient.get(`${METRO_BASE}/products/${productId}`);
    return response.data;
  },

  getProductByEan: async (ean: string): Promise<MetroProduct> => {
    const response = await apiClient.get(`${METRO_BASE}/products/ean/${ean}`);
    return response.data;
  },

  // ============================================
  // Factures
  // ============================================

  getFactures: async (
    page = 1,
    perPage = 20,
    startDate?: string,
    endDate?: string
  ): Promise<MetroFacturesResponse> => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);

    const response = await apiClient.get(`${METRO_BASE}/factures?${params}`);
    return response.data;
  },

  getFactureById: async (factureId: number): Promise<MetroFactureDetail> => {
    const response = await apiClient.get(`${METRO_BASE}/factures/${factureId}`);
    return response.data;
  },

  // ============================================
  // Categories & Stats
  // ============================================

  getCategories: async (): Promise<MetroCategory[]> => {
    const response = await apiClient.get(`${METRO_BASE}/categories`);
    return response.data;
  },

  getCategoryStats: async (): Promise<MetroCategoryStats[]> => {
    const response = await apiClient.get(`${METRO_BASE}/stats/categories`);
    return response.data;
  },

  getTVAStats: async (): Promise<MetroTVAStats[]> => {
    const response = await apiClient.get(`${METRO_BASE}/stats/tva`);
    return response.data;
  },

  // ============================================
  // Actions
  // ============================================

  importFactures: async (file: File): Promise<{ imported: number; errors: string[] }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post(`${METRO_BASE}/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  recalculateAggregates: async (): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post(`${METRO_BASE}/recalculate`);
    return response.data;
  },
};

export default metroApi;
