import { apiClient } from './client';
import type {
  SupplyOrder,
  SupplyOrderDetail,
  SupplyOrderCreate,
  SupplyOrderUpdate,
  SupplyOrderLine,
  SupplyOrderLineCreate,
  SupplyOrderLineUpdate,
  SupplyOrderStats,
  ConfirmOrderRequest,
  ReceiveOrderRequest,
  CancelOrderRequest,
  SupplyOrderStatus,
  PaginatedResponse,
  DataResponse,
} from '../types/epicerie';

// ============================================
// Base URL
// ============================================

const EPICERIE_BASE = '/epicerie';

// ============================================
// Supply Orders
// ============================================

export const supplyOrdersApi = {
  getAll: async (
    page = 1,
    pageSize = 20,
    vendorId?: number,
    statut?: SupplyOrderStatus
  ): Promise<PaginatedResponse<SupplyOrder>> => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    if (vendorId) params.set('vendor_id', String(vendorId));
    if (statut) params.set('statut', statut);
    const response = await apiClient.get(`${EPICERIE_BASE}/orders?${params}`);
    return response.data;
  },

  getLate: async (): Promise<DataResponse<SupplyOrder[]>> => {
    const response = await apiClient.get(`${EPICERIE_BASE}/orders/late`);
    return response.data;
  },

  getById: async (orderId: number): Promise<DataResponse<SupplyOrderDetail>> => {
    const response = await apiClient.get(`${EPICERIE_BASE}/orders/${orderId}`);
    return response.data;
  },

  create: async (data: SupplyOrderCreate): Promise<DataResponse<SupplyOrderDetail>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders`, data);
    return response.data;
  },

  update: async (orderId: number, data: SupplyOrderUpdate): Promise<DataResponse<SupplyOrderDetail>> => {
    const response = await apiClient.put(`${EPICERIE_BASE}/orders/${orderId}`, data);
    return response.data;
  },

  delete: async (orderId: number): Promise<void> => {
    await apiClient.delete(`${EPICERIE_BASE}/orders/${orderId}`);
  },

  // Actions
  confirm: async (orderId: number, data?: ConfirmOrderRequest): Promise<DataResponse<SupplyOrder>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders/${orderId}/confirm`, data || {});
    return response.data;
  },

  ship: async (orderId: number): Promise<DataResponse<SupplyOrder>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders/${orderId}/ship`);
    return response.data;
  },

  receive: async (orderId: number, data: ReceiveOrderRequest): Promise<DataResponse<SupplyOrderDetail>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders/${orderId}/receive`, data);
    return response.data;
  },

  cancel: async (orderId: number, data?: CancelOrderRequest): Promise<DataResponse<SupplyOrder>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders/${orderId}/cancel`, data || {});
    return response.data;
  },

  // Stats
  getStatsByVendor: async (vendorId: number): Promise<DataResponse<SupplyOrderStats>> => {
    const response = await apiClient.get(`${EPICERIE_BASE}/orders/stats/by-vendor/${vendorId}`);
    return response.data;
  },
};

// ============================================
// Supply Order Lines
// ============================================

export const supplyOrderLinesApi = {
  add: async (orderId: number, data: SupplyOrderLineCreate): Promise<DataResponse<SupplyOrderLine>> => {
    const response = await apiClient.post(`${EPICERIE_BASE}/orders/${orderId}/lines`, data);
    return response.data;
  },

  update: async (
    orderId: number,
    lineId: number,
    data: SupplyOrderLineUpdate
  ): Promise<DataResponse<SupplyOrderLine>> => {
    const response = await apiClient.put(`${EPICERIE_BASE}/orders/${orderId}/lines/${lineId}`, data);
    return response.data;
  },

  delete: async (orderId: number, lineId: number): Promise<void> => {
    await apiClient.delete(`${EPICERIE_BASE}/orders/${orderId}/lines/${lineId}`);
  },
};
