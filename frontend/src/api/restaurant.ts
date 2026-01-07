import { apiClient } from './client';
import type {
  Ingredient,
  IngredientCreate,
  IngredientUpdate,
  Plat,
  PlatDetail,
  PlatCreate,
  PlatUpdate,
  PlatIngredientInput,
  Stock,
  StockMovement,
  StockMovementCreate,
  StockAdjustment,
  StockAlert,
  Consumption,
  ConsumptionCreate,
  DailySummary,
  BestSeller,
  LossReport,
  Charge,
  ChargeCreate,
  ChargeUpdate,
  ChargesSummary,
  ChargesBreakdown,
  RestaurantDashboardData,
  RestaurantIngredientCategory,
  RestaurantPlatCategory,
  RestaurantChargeType,
  EpicerieLink,
  EpicerieLinkCreate,
  EpicerieLinkUpdate,
  IngredientWithLinks,
  EpicerieProduit,
  PriceSyncResult,
} from '../types/restaurant';

// ============================================
// Base URL
// ============================================

const RESTAURANT_BASE = '/restaurant';

// ============================================
// Ingredients
// ============================================

export const ingredientsApi = {
  getAll: async (
    category?: RestaurantIngredientCategory,
    activeOnly = true
  ): Promise<Ingredient[]> => {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    params.set('active_only', String(activeOnly));
    const response = await apiClient.get(`${RESTAURANT_BASE}/ingredients?${params}`);
    return response.data;
  },

  getById: async (id: number): Promise<Ingredient> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/ingredients/${id}`);
    return response.data;
  },

  create: async (data: IngredientCreate): Promise<Ingredient> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/ingredients`, data);
    return response.data;
  },

  update: async (id: number, data: IngredientUpdate): Promise<Ingredient> => {
    const response = await apiClient.patch(`${RESTAURANT_BASE}/ingredients/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${RESTAURANT_BASE}/ingredients/${id}`);
  },

  search: async (query: string): Promise<Ingredient[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/ingredients/search?q=${encodeURIComponent(query)}`);
    return response.data;
  },

  getLowStock: async (): Promise<Ingredient[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/ingredients/low-stock`);
    return response.data;
  },
};

// ============================================
// Plats
// ============================================

export const platsApi = {
  getAll: async (
    category?: RestaurantPlatCategory,
    menusOnly = false
  ): Promise<Plat[]> => {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    if (menusOnly) params.set('menus_only', 'true');
    const response = await apiClient.get(`${RESTAURANT_BASE}/plats?${params}`);
    return response.data;
  },

  getById: async (id: number): Promise<PlatDetail> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/plats/${id}`);
    return response.data;
  },

  create: async (data: PlatCreate): Promise<Plat> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/plats`, data);
    return response.data;
  },

  update: async (id: number, data: PlatUpdate): Promise<Plat> => {
    const response = await apiClient.patch(`${RESTAURANT_BASE}/plats/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${RESTAURANT_BASE}/plats/${id}`);
  },

  search: async (query: string): Promise<Plat[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/plats/search?q=${encodeURIComponent(query)}`);
    return response.data;
  },

  getUnprofitable: async (threshold = 35): Promise<Plat[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/plats/unprofitable?threshold=${threshold}`);
    return response.data;
  },

  setIngredients: async (platId: number, ingredients: PlatIngredientInput[]): Promise<PlatDetail> => {
    const response = await apiClient.put(`${RESTAURANT_BASE}/plats/${platId}/ingredients`, ingredients);
    return response.data;
  },

  addIngredient: async (platId: number, data: PlatIngredientInput): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/plats/${platId}/ingredients`, data);
    return response.data;
  },

  removeIngredient: async (platId: number, ingredientId: number): Promise<void> => {
    await apiClient.delete(`${RESTAURANT_BASE}/plats/${platId}/ingredients/${ingredientId}`);
  },
};

// ============================================
// Stock
// ============================================

export const stockApi = {
  getAll: async (): Promise<Stock[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/stock`);
    return response.data;
  },

  getByIngredient: async (ingredientId: number): Promise<Stock> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/stock/${ingredientId}`);
    return response.data;
  },

  getLowStock: async (): Promise<StockAlert[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/stock/low`);
    return response.data;
  },

  getTotalValue: async (): Promise<{ total_value: number }> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/stock/value`);
    return response.data;
  },

  createMovement: async (data: StockMovementCreate): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/stock/movement`, data);
    return response.data;
  },

  adjustStock: async (data: StockAdjustment): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/stock/adjust`, data);
    return response.data;
  },

  getMovements: async (
    ingredientId: number,
    startDate?: string,
    endDate?: string
  ): Promise<StockMovement[]> => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const response = await apiClient.get(
      `${RESTAURANT_BASE}/stock/${ingredientId}/movements?${params}`
    );
    return response.data;
  },
};

// ============================================
// Consumptions
// ============================================

export const consumptionsApi = {
  getAll: async (startDate: string, endDate: string): Promise<Consumption[]> => {
    const response = await apiClient.get(
      `${RESTAURANT_BASE}/consumptions?start_date=${startDate}&end_date=${endDate}`
    );
    return response.data;
  },

  recordSale: async (data: ConsumptionCreate): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/consumptions/sale`, data);
    return response.data;
  },

  recordLoss: async (data: ConsumptionCreate): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/consumptions/loss`, data);
    return response.data;
  },

  recordStaffMeal: async (data: ConsumptionCreate): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/consumptions/staff-meal`, data);
    return response.data;
  },

  recordOffered: async (data: ConsumptionCreate): Promise<{ id: number }> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/consumptions/offered`, data);
    return response.data;
  },

  getDailySummary: async (date: string): Promise<DailySummary> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/consumptions/summary?target_date=${date}`);
    return response.data;
  },

  getBestSellers: async (
    startDate: string,
    endDate: string,
    limit = 10
  ): Promise<BestSeller[]> => {
    const response = await apiClient.get(
      `${RESTAURANT_BASE}/consumptions/best-sellers?start_date=${startDate}&end_date=${endDate}&limit=${limit}`
    );
    return response.data;
  },

  getLossReport: async (startDate: string, endDate: string): Promise<LossReport> => {
    const response = await apiClient.get(
      `${RESTAURANT_BASE}/consumptions/losses?start_date=${startDate}&end_date=${endDate}`
    );
    return response.data;
  },
};

// ============================================
// Charges
// ============================================

export const chargesApi = {
  getAll: async (
    chargeType?: RestaurantChargeType,
    activeOnly = true
  ): Promise<Charge[]> => {
    const params = new URLSearchParams();
    if (chargeType) params.set('charge_type', chargeType);
    params.set('active_only', String(activeOnly));
    const response = await apiClient.get(`${RESTAURANT_BASE}/charges?${params}`);
    return response.data;
  },

  getById: async (id: number): Promise<Charge> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/charges/${id}`);
    return response.data;
  },

  create: async (data: ChargeCreate): Promise<Charge> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/charges`, data);
    return response.data;
  },

  update: async (id: number, data: ChargeUpdate): Promise<Charge> => {
    const response = await apiClient.patch(`${RESTAURANT_BASE}/charges/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`${RESTAURANT_BASE}/charges/${id}`);
  },

  getSummary: async (): Promise<ChargesSummary> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/charges/summary`);
    return response.data;
  },

  getBreakdown: async (): Promise<ChargesBreakdown[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/charges/breakdown`);
    return response.data;
  },
};

// ============================================
// Dashboard
// ============================================

export const restaurantDashboardApi = {
  getData: async (date?: string): Promise<RestaurantDashboardData> => {
    const params = date ? `?target_date=${date}` : '';
    const response = await apiClient.get(`${RESTAURANT_BASE}/dashboard${params}`);
    return response.data;
  },
};

// ============================================
// Epicerie Links (Rapprochement)
// ============================================

export const epicerieLinksApi = {
  getAll: async (ingredientId?: number): Promise<EpicerieLink[]> => {
    const params = ingredientId ? `?ingredient_id=${ingredientId}` : '';
    const response = await apiClient.get(`${RESTAURANT_BASE}/epicerie-links${params}`);
    return response.data;
  },

  getIngredientsWithLinks: async (): Promise<IngredientWithLinks[]> => {
    const response = await apiClient.get(`${RESTAURANT_BASE}/ingredients-with-links`);
    return response.data;
  },

  create: async (data: EpicerieLinkCreate): Promise<EpicerieLink> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/epicerie-links`, data);
    return response.data;
  },

  update: async (linkId: number, data: EpicerieLinkUpdate): Promise<{ id: number }> => {
    const response = await apiClient.patch(`${RESTAURANT_BASE}/epicerie-links/${linkId}`, data);
    return response.data;
  },

  delete: async (linkId: number): Promise<void> => {
    await apiClient.delete(`${RESTAURANT_BASE}/epicerie-links/${linkId}`);
  },

  searchProducts: async (query: string, limit = 100, fournisseur?: string): Promise<EpicerieProduit[]> => {
    const params = new URLSearchParams({
      q: query,
      limit: limit.toString(),
    });
    if (fournisseur) {
      params.append('fournisseur', fournisseur);
    }
    const response = await apiClient.get(
      `${RESTAURANT_BASE}/epicerie-products/search?${params.toString()}`
    );
    return response.data;
  },

  syncPrices: async (force = false): Promise<PriceSyncResult> => {
    const response = await apiClient.post(`${RESTAURANT_BASE}/sync-prices-from-epicerie?force=${force}`);
    return response.data;
  },
};
