/**
 * API Client - Catalogue Produits
 *
 * Architecture SID:
 * - Données brutes DWH -> Information interprétée -> Connaissance décisionnelle
 * - Endpoints connectés au Data Warehouse avec RLS tenant isolation
 */
import apiClient from './client'

// ============================================================================
// TYPES - Schéma dimensionnel (Star Schema)
// ============================================================================

/** Produit dans la liste (fait + dimensions dénormalisées) */
export interface ProduitListItem {
  produit_sk: number           // Surrogate key DWH
  produit_id: number           // Business key
  nom: string
  categorie_id: number | null
  categorie_nom: string | null // Dimension catégorie
  famille: string | null       // Hiérarchie catégorie
  prix_achat: number | null    // Fait
  prix_vente: number | null    // Fait
  marge_pct: number | null     // Mesure calculée
  stock_actuel: number         // Fait stock quotidien
  seuil_alerte: number | null  // Règle métier
  est_rupture: boolean         // Indicateur décisionnel
  jours_stock: number | null   // Mesure calculée (couverture)
}

/** Réponse paginée (métadonnées pour navigation) */
export interface ProduitListResponse {
  items: ProduitListItem[]
  total: number
  page: number
  per_page: number
  pages: number
}

/** Mouvement de stock (fait) */
export interface MouvementStock {
  date: string
  type_mouvement: 'ENTREE' | 'SORTIE' | 'INVENTAIRE'
  quantite: number
  source: string | null
}

/** Détail produit enrichi (faits + dimensions + historique) */
export interface ProduitDetail {
  produit_sk: number
  produit_id: number
  nom: string
  // Dimension catégorie (hiérarchie)
  categorie_id: number | null
  categorie_nom: string | null
  famille: string | null
  sous_famille: string | null
  // Faits prix
  prix_achat: number | null
  prix_vente: number | null
  tva_pct: number | null
  // Mesures calculées
  marge_unitaire: number | null
  marge_pct: number | null
  // Règles métier
  seuil_alerte: number | null
  // Fait stock quotidien
  stock_actuel: number
  stock_valeur: number | null
  conso_moy_30j: number | null
  jours_stock: number | null
  // Indicateurs décisionnels
  est_rupture: boolean
  est_surstock: boolean
  // KPIs tendance
  ventes_30j: number | null
  trend_stock_pct: number | null
  // Historique mouvements
  mouvements_recents: MouvementStock[]
}

/** Filtres catalogue (critères de décision) */
export interface CatalogFilters {
  page?: number
  per_page?: number
  q?: string              // Recherche textuelle
  famille?: string        // Filtre hiérarchie
  categorie_id?: number   // Filtre dimension
  stock_status?: 'rupture' | 'low' | 'ok'  // Filtre indicateur
  marge_filter?: 'low' | 'medium' | 'high' // Filtre mesure
}

// ============================================================================
// API FUNCTIONS - Extraction données DWH
// ============================================================================

export const catalogApi = {
  /**
   * Liste des produits paginée avec filtres
   *
   * Workflow décisionnel:
   * 1. Identification: Quels produits surveiller?
   * 2. Critères: stock_status, marge, famille
   * 3. Priorisation: Tri par pertinence métier
   */
  getProducts: async (filters: CatalogFilters = {}): Promise<ProduitListResponse> => {
    const params: Record<string, unknown> = {}

    if (filters.page) params.page = filters.page
    if (filters.per_page) params.per_page = filters.per_page
    if (filters.q) params.q = filters.q
    if (filters.famille) params.famille = filters.famille
    if (filters.categorie_id) params.categorie_id = filters.categorie_id
    if (filters.stock_status) params.stock_status = filters.stock_status
    if (filters.marge_filter) params.marge_filter = filters.marge_filter

    const response = await apiClient.get('/catalog/products', { params })
    return response.data
  },

  /**
   * Détail enrichi d'un produit
   *
   * Information interprétée:
   * - Stock actuel vs seuil -> Alerte rupture
   * - Marge vs objectif -> Performance
   * - Jours de stock -> Couverture prévisionnelle
   * - Mouvements récents -> Tendance
   */
  getProductDetail: async (produitSk: number): Promise<ProduitDetail> => {
    const response = await apiClient.get(`/catalog/products/${produitSk}`)
    return response.data
  },

  /**
   * Liste des familles (dimension hiérarchique)
   * Pour filtres et navigation
   */
  getFamilies: async (): Promise<string[]> => {
    const response = await apiClient.get('/catalog/families')
    return response.data
  },
}

export default catalogApi
