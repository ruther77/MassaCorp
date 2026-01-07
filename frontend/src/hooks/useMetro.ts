import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { metroApi } from '../api/metro';
import type { MetroProductFilters } from '../types/metro';

// ============================================
// Query Keys
// ============================================

export const metroKeys = {
  all: ['metro'] as const,
  summary: () => [...metroKeys.all, 'summary'] as const,
  dashboard: () => [...metroKeys.all, 'dashboard'] as const,

  products: () => [...metroKeys.all, 'products'] as const,
  productsList: (filters: MetroProductFilters) => [...metroKeys.products(), 'list', filters] as const,
  productDetail: (id: number) => [...metroKeys.products(), 'detail', id] as const,
  productByEan: (ean: string) => [...metroKeys.products(), 'ean', ean] as const,

  factures: () => [...metroKeys.all, 'factures'] as const,
  facturesList: (page: number, perPage: number, startDate?: string, endDate?: string) =>
    [...metroKeys.factures(), 'list', page, perPage, startDate, endDate] as const,
  factureDetail: (id: number) => [...metroKeys.factures(), 'detail', id] as const,

  categories: () => [...metroKeys.all, 'categories'] as const,
  categoryStats: () => [...metroKeys.all, 'categoryStats'] as const,
  tvaStats: () => [...metroKeys.all, 'tvaStats'] as const,
};

// ============================================
// Summary & Dashboard Hooks
// ============================================

export function useMetroSummary() {
  return useQuery({
    queryKey: metroKeys.summary(),
    queryFn: () => metroApi.getSummary(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useMetroDashboard() {
  return useQuery({
    queryKey: metroKeys.dashboard(),
    queryFn: () => metroApi.getDashboard(),
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================
// Products Hooks
// ============================================

export function useMetroProducts(filters: MetroProductFilters = {}) {
  return useQuery({
    queryKey: metroKeys.productsList(filters),
    queryFn: () => metroApi.getProducts(filters),
    staleTime: 2 * 60 * 1000,
  });
}

export function useMetroProduct(productId: number) {
  return useQuery({
    queryKey: metroKeys.productDetail(productId),
    queryFn: () => metroApi.getProductById(productId),
    enabled: !!productId,
  });
}

export function useMetroProductByEan(ean: string) {
  return useQuery({
    queryKey: metroKeys.productByEan(ean),
    queryFn: () => metroApi.getProductByEan(ean),
    enabled: !!ean && ean.length >= 8,
  });
}

// ============================================
// Factures Hooks
// ============================================

export function useMetroFactures(
  page = 1,
  perPage = 20,
  startDate?: string,
  endDate?: string
) {
  return useQuery({
    queryKey: metroKeys.facturesList(page, perPage, startDate, endDate),
    queryFn: () => metroApi.getFactures(page, perPage, startDate, endDate),
    staleTime: 2 * 60 * 1000,
  });
}

export function useMetroFacture(factureId: number) {
  return useQuery({
    queryKey: metroKeys.factureDetail(factureId),
    queryFn: () => metroApi.getFactureById(factureId),
    enabled: !!factureId,
  });
}

// ============================================
// Categories & Stats Hooks
// ============================================

export function useMetroCategories() {
  return useQuery({
    queryKey: metroKeys.categories(),
    queryFn: () => metroApi.getCategories(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useMetroCategoryStats() {
  return useQuery({
    queryKey: metroKeys.categoryStats(),
    queryFn: () => metroApi.getCategoryStats(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMetroTVAStats() {
  return useQuery({
    queryKey: metroKeys.tvaStats(),
    queryFn: () => metroApi.getTVAStats(),
    staleTime: 5 * 60 * 1000,
  });
}

// ============================================
// Mutation Hooks
// ============================================

export function useImportMetroFactures() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => metroApi.importFactures(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: metroKeys.all });
    },
  });
}

export function useRecalculateMetroAggregates() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => metroApi.recalculateAggregates(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: metroKeys.all });
    },
  });
}
