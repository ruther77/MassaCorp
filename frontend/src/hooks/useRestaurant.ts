import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ingredientsApi,
  platsApi,
  stockApi,
  consumptionsApi,
  chargesApi,
  restaurantDashboardApi,
  epicerieLinksApi,
} from '../api/restaurant';
import type {
  IngredientCreate,
  IngredientUpdate,
  PlatCreate,
  PlatUpdate,
  PlatIngredientInput,
  StockMovementCreate,
  StockAdjustment,
  ConsumptionCreate,
  ChargeCreate,
  ChargeUpdate,
  RestaurantIngredientCategory,
  RestaurantPlatCategory,
  RestaurantChargeType,
  EpicerieLinkCreate,
  EpicerieLinkUpdate,
} from '../types/restaurant';

// ============================================
// Query Keys
// ============================================

export const restaurantKeys = {
  all: ['restaurant'] as const,

  // Ingredients
  ingredients: () => [...restaurantKeys.all, 'ingredients'] as const,
  ingredientsList: (category?: RestaurantIngredientCategory) =>
    [...restaurantKeys.ingredients(), 'list', category] as const,
  ingredientDetail: (id: number) => [...restaurantKeys.ingredients(), 'detail', id] as const,
  ingredientsLowStock: () => [...restaurantKeys.ingredients(), 'low-stock'] as const,
  ingredientsSearch: (query: string) => [...restaurantKeys.ingredients(), 'search', query] as const,

  // Plats
  plats: () => [...restaurantKeys.all, 'plats'] as const,
  platsList: (category?: RestaurantPlatCategory, menusOnly?: boolean) =>
    [...restaurantKeys.plats(), 'list', category, menusOnly] as const,
  platDetail: (id: number) => [...restaurantKeys.plats(), 'detail', id] as const,
  platsUnprofitable: (threshold: number) => [...restaurantKeys.plats(), 'unprofitable', threshold] as const,
  platsSearch: (query: string) => [...restaurantKeys.plats(), 'search', query] as const,

  // Stock
  stock: () => [...restaurantKeys.all, 'stock'] as const,
  stockList: () => [...restaurantKeys.stock(), 'list'] as const,
  stockByIngredient: (ingredientId: number) => [...restaurantKeys.stock(), 'ingredient', ingredientId] as const,
  stockLow: () => [...restaurantKeys.stock(), 'low'] as const,
  stockValue: () => [...restaurantKeys.stock(), 'value'] as const,
  stockMovements: (ingredientId: number, startDate?: string, endDate?: string) =>
    [...restaurantKeys.stock(), 'movements', ingredientId, startDate, endDate] as const,

  // Consumptions
  consumptions: () => [...restaurantKeys.all, 'consumptions'] as const,
  consumptionsList: (startDate: string, endDate: string) =>
    [...restaurantKeys.consumptions(), 'list', startDate, endDate] as const,
  consumptionsDailySummary: (date: string) =>
    [...restaurantKeys.consumptions(), 'daily-summary', date] as const,
  consumptionsBestSellers: (startDate: string, endDate: string, limit: number) =>
    [...restaurantKeys.consumptions(), 'best-sellers', startDate, endDate, limit] as const,
  consumptionsLossReport: (startDate: string, endDate: string) =>
    [...restaurantKeys.consumptions(), 'loss-report', startDate, endDate] as const,

  // Charges
  charges: () => [...restaurantKeys.all, 'charges'] as const,
  chargesList: (chargeType?: RestaurantChargeType) =>
    [...restaurantKeys.charges(), 'list', chargeType] as const,
  chargeDetail: (id: number) => [...restaurantKeys.charges(), 'detail', id] as const,
  chargesSummary: () => [...restaurantKeys.charges(), 'summary'] as const,
  chargesBreakdown: () => [...restaurantKeys.charges(), 'breakdown'] as const,

  // Dashboard
  dashboard: () => [...restaurantKeys.all, 'dashboard'] as const,
  dashboardData: (date?: string) => [...restaurantKeys.dashboard(), 'data', date] as const,

  // Epicerie Links
  epicerieLinks: () => [...restaurantKeys.all, 'epicerie-links'] as const,
  epicerieLinksList: (ingredientId?: number) =>
    [...restaurantKeys.epicerieLinks(), 'list', ingredientId] as const,
  ingredientsWithLinks: () => [...restaurantKeys.all, 'ingredients-with-links'] as const,
  epicerieProductsSearch: (query: string) =>
    [...restaurantKeys.all, 'epicerie-products', 'search', query] as const,
};

// ============================================
// Ingredients Hooks
// ============================================

export function useIngredients(category?: RestaurantIngredientCategory, activeOnly = true) {
  return useQuery({
    queryKey: restaurantKeys.ingredientsList(category),
    queryFn: () => ingredientsApi.getAll(category, activeOnly),
    staleTime: 30 * 1000,
  });
}

export function useIngredient(id: number) {
  return useQuery({
    queryKey: restaurantKeys.ingredientDetail(id),
    queryFn: () => ingredientsApi.getById(id),
    enabled: !!id,
  });
}

export function useIngredientsLowStock() {
  return useQuery({
    queryKey: restaurantKeys.ingredientsLowStock(),
    queryFn: () => ingredientsApi.getLowStock(),
    staleTime: 60 * 1000,
  });
}

export function useSearchIngredients(query: string) {
  return useQuery({
    queryKey: restaurantKeys.ingredientsSearch(query),
    queryFn: () => ingredientsApi.search(query),
    enabled: query.length >= 2,
  });
}

export function useCreateIngredient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: IngredientCreate) => ingredientsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
    },
  });
}

export function useUpdateIngredient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: IngredientUpdate }) =>
      ingredientsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
    },
  });
}

export function useDeleteIngredient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => ingredientsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
    },
  });
}

// ============================================
// Plats Hooks
// ============================================

export function usePlats(category?: RestaurantPlatCategory, menusOnly = false) {
  return useQuery({
    queryKey: restaurantKeys.platsList(category, menusOnly),
    queryFn: () => platsApi.getAll(category, menusOnly),
    staleTime: 30 * 1000,
  });
}

export function usePlat(id: number) {
  return useQuery({
    queryKey: restaurantKeys.platDetail(id),
    queryFn: () => platsApi.getById(id),
    enabled: !!id,
  });
}

export function useUnprofitablePlats(threshold = 35) {
  return useQuery({
    queryKey: restaurantKeys.platsUnprofitable(threshold),
    queryFn: () => platsApi.getUnprofitable(threshold),
    staleTime: 60 * 1000,
  });
}

export function useSearchPlats(query: string) {
  return useQuery({
    queryKey: restaurantKeys.platsSearch(query),
    queryFn: () => platsApi.search(query),
    enabled: query.length >= 2,
  });
}

export function useCreatePlat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PlatCreate) => platsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.plats() });
    },
  });
}

export function useUpdatePlat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PlatUpdate }) =>
      platsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.plats() });
    },
  });
}

export function useDeletePlat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => platsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.plats() });
    },
  });
}

export function useSetPlatIngredients() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ platId, ingredients }: { platId: number; ingredients: PlatIngredientInput[] }) =>
      platsApi.setIngredients(platId, ingredients),
    onSuccess: (_, { platId }) => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.platDetail(platId) });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.plats() });
    },
  });
}

export function useAddPlatIngredient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ platId, data }: { platId: number; data: PlatIngredientInput }) =>
      platsApi.addIngredient(platId, data),
    onSuccess: (_, { platId }) => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.platDetail(platId) });
    },
  });
}

export function useRemovePlatIngredient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ platId, ingredientId }: { platId: number; ingredientId: number }) =>
      platsApi.removeIngredient(platId, ingredientId),
    onSuccess: (_, { platId }) => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.platDetail(platId) });
    },
  });
}

// ============================================
// Stock Hooks
// ============================================

export function useStocks() {
  return useQuery({
    queryKey: restaurantKeys.stockList(),
    queryFn: () => stockApi.getAll(),
    staleTime: 30 * 1000,
  });
}

export function useStockByIngredient(ingredientId: number) {
  return useQuery({
    queryKey: restaurantKeys.stockByIngredient(ingredientId),
    queryFn: () => stockApi.getByIngredient(ingredientId),
    enabled: !!ingredientId,
  });
}

export function useLowStock() {
  return useQuery({
    queryKey: restaurantKeys.stockLow(),
    queryFn: () => stockApi.getLowStock(),
    staleTime: 60 * 1000,
  });
}

export function useStockTotalValue() {
  return useQuery({
    queryKey: restaurantKeys.stockValue(),
    queryFn: () => stockApi.getTotalValue(),
    staleTime: 60 * 1000,
  });
}

export function useStockMovements(ingredientId: number, startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: restaurantKeys.stockMovements(ingredientId, startDate, endDate),
    queryFn: () => stockApi.getMovements(ingredientId, startDate, endDate),
    enabled: !!ingredientId,
  });
}

export function useCreateStockMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StockMovementCreate) => stockApi.createMovement(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
    },
  });
}

export function useAdjustStock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StockAdjustment) => stockApi.adjustStock(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
    },
  });
}

// ============================================
// Consumptions Hooks
// ============================================

export function useConsumptions(startDate: string, endDate: string) {
  return useQuery({
    queryKey: restaurantKeys.consumptionsList(startDate, endDate),
    queryFn: () => consumptionsApi.getAll(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });
}

export function useDailySummary(date: string) {
  return useQuery({
    queryKey: restaurantKeys.consumptionsDailySummary(date),
    queryFn: () => consumptionsApi.getDailySummary(date),
    enabled: !!date,
  });
}

export function useBestSellers(startDate: string, endDate: string, limit = 10) {
  return useQuery({
    queryKey: restaurantKeys.consumptionsBestSellers(startDate, endDate, limit),
    queryFn: () => consumptionsApi.getBestSellers(startDate, endDate, limit),
    enabled: !!startDate && !!endDate,
  });
}

export function useLossReport(startDate: string, endDate: string) {
  return useQuery({
    queryKey: restaurantKeys.consumptionsLossReport(startDate, endDate),
    queryFn: () => consumptionsApi.getLossReport(startDate, endDate),
    enabled: !!startDate && !!endDate,
  });
}

export function useRecordSale() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ConsumptionCreate) => consumptionsApi.recordSale(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.consumptions() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.dashboard() });
    },
  });
}

export function useRecordLoss() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ConsumptionCreate) => consumptionsApi.recordLoss(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.consumptions() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.dashboard() });
    },
  });
}

export function useRecordStaffMeal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ConsumptionCreate) => consumptionsApi.recordStaffMeal(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.consumptions() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
    },
  });
}

export function useRecordOffered() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ConsumptionCreate) => consumptionsApi.recordOffered(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.consumptions() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.stock() });
    },
  });
}

// ============================================
// Charges Hooks
// ============================================

export function useCharges(chargeType?: RestaurantChargeType, activeOnly = true) {
  return useQuery({
    queryKey: restaurantKeys.chargesList(chargeType),
    queryFn: () => chargesApi.getAll(chargeType, activeOnly),
    staleTime: 60 * 1000,
  });
}

export function useCharge(id: number) {
  return useQuery({
    queryKey: restaurantKeys.chargeDetail(id),
    queryFn: () => chargesApi.getById(id),
    enabled: !!id,
  });
}

export function useChargesSummary() {
  return useQuery({
    queryKey: restaurantKeys.chargesSummary(),
    queryFn: () => chargesApi.getSummary(),
    staleTime: 60 * 1000,
  });
}

export function useChargesBreakdown() {
  return useQuery({
    queryKey: restaurantKeys.chargesBreakdown(),
    queryFn: () => chargesApi.getBreakdown(),
    staleTime: 60 * 1000,
  });
}

export function useCreateCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChargeCreate) => chargesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.charges() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.dashboard() });
    },
  });
}

export function useUpdateCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ChargeUpdate }) =>
      chargesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.charges() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.dashboard() });
    },
  });
}

export function useDeleteCharge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => chargesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.charges() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.dashboard() });
    },
  });
}

// ============================================
// Dashboard Hook
// ============================================

export function useRestaurantDashboard(date?: string) {
  return useQuery({
    queryKey: restaurantKeys.dashboardData(date),
    queryFn: () => restaurantDashboardApi.getData(date),
    staleTime: 30 * 1000,
  });
}

// ============================================
// Epicerie Links Hooks
// ============================================

export function useEpicerieLinks(ingredientId?: number) {
  return useQuery({
    queryKey: restaurantKeys.epicerieLinksList(ingredientId),
    queryFn: () => epicerieLinksApi.getAll(ingredientId),
    staleTime: 60 * 1000,
  });
}

export function useIngredientsWithLinks() {
  return useQuery({
    queryKey: restaurantKeys.ingredientsWithLinks(),
    queryFn: () => epicerieLinksApi.getIngredientsWithLinks(),
    staleTime: 60 * 1000,
  });
}

export function useCreateEpicerieLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: EpicerieLinkCreate) => epicerieLinksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.epicerieLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredientsWithLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
    },
  });
}

export function useUpdateEpicerieLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ linkId, data }: { linkId: number; data: EpicerieLinkUpdate }) =>
      epicerieLinksApi.update(linkId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.epicerieLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredientsWithLinks() });
    },
  });
}

export function useDeleteEpicerieLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (linkId: number) => epicerieLinksApi.delete(linkId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.epicerieLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredientsWithLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
    },
  });
}

export function useSearchEpicerieProducts(query: string, limit = 100, fournisseur?: string) {
  return useQuery({
    queryKey: [...restaurantKeys.epicerieProductsSearch(query), fournisseur, limit],
    queryFn: () => epicerieLinksApi.searchProducts(query, limit, fournisseur),
    enabled: query.length >= 2,
    staleTime: 60 * 1000, // Cache plus long pour eviter les requetes repetees
  });
}

export function useSyncPricesFromEpicerie() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ force = false }: { force?: boolean } = {}) => epicerieLinksApi.syncPrices(force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredients() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.epicerieLinks() });
      queryClient.invalidateQueries({ queryKey: restaurantKeys.ingredientsWithLinks() });
    },
  });
}
