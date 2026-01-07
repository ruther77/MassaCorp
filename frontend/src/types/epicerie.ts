/**
 * Types pour le domaine Epicerie (Commandes fournisseurs)
 */

export type SupplyOrderStatus = 'en_attente' | 'confirmee' | 'expediee' | 'livree' | 'annulee';

export interface VendorSummary {
  id: number;
  name: string;
  code: string | null;
}

export interface SupplyOrderLine {
  id: number;
  order_id: number;
  produit_id: number | null;
  designation: string;
  quantity: number;
  prix_unitaire: number;
  received_quantity: number | null;
  notes: string | null;
  montant_ligne: number;
  is_fully_received: boolean;
  is_partially_received: boolean;
  created_at: string;
  updated_at: string;
}

export interface SupplyOrder {
  id: number;
  tenant_id: number;
  vendor_id: number;
  reference: string | null;
  date_commande: string;
  date_livraison_prevue: string | null;
  date_livraison_reelle: string | null;
  statut: SupplyOrderStatus;
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;
  nb_lignes: number;
  nb_produits: number;
  notes: string | null;
  created_by: number | null;
  is_pending: boolean;
  is_delivered: boolean;
  is_cancelled: boolean;
  is_late: boolean;
  created_at: string;
  updated_at: string;
  vendor: VendorSummary | null;
}

export interface SupplyOrderDetail extends SupplyOrder {
  lines: SupplyOrderLine[];
}

export interface SupplyOrderLineCreate {
  produit_id?: number | null;
  designation: string;
  quantity: number;
  prix_unitaire: number;
  notes?: string | null;
}

export interface SupplyOrderCreate {
  vendor_id: number;
  reference?: string | null;
  date_commande: string;
  date_livraison_prevue?: string | null;
  notes?: string | null;
  lines?: SupplyOrderLineCreate[];
}

export interface SupplyOrderUpdate {
  reference?: string | null;
  date_livraison_prevue?: string | null;
  date_livraison_reelle?: string | null;
  statut?: SupplyOrderStatus;
  notes?: string | null;
}

export interface SupplyOrderLineUpdate {
  produit_id?: number | null;
  designation?: string;
  quantity?: number;
  prix_unitaire?: number;
  received_quantity?: number | null;
  notes?: string | null;
}

export interface ConfirmOrderRequest {
  date_livraison_prevue?: string | null;
}

export interface ReceiveOrderRequest {
  date_livraison_reelle: string;
  lines?: Array<{ line_id: number; received_quantity: number }>;
}

export interface CancelOrderRequest {
  raison?: string | null;
}

export interface SupplyOrderStats {
  total_commandes: number;
  total_montant_ht: number;
  par_statut: Record<SupplyOrderStatus, number>;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface DataResponse<T> {
  data: T;
}
