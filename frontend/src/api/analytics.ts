import apiClient from './client'

// Types
export interface DashboardKPIs {
  valeur_stock_total: string
  nb_produits_rupture: number
  rotation_moyenne: number | null
  ca_30j: string
  nb_plats_vendus_30j: number
  marge_brute_30j: string
  food_cost_moyen: number | null
  depenses_mois: string
  nb_categories: number
}

export interface Categorie {
  categorie_id: number
  code: string
  nom: string
  famille: string
  sous_famille: string | null
  tva_defaut: string
}

export interface CategorieProduit {
  categorie_id: number
  code: string
  nom: string
  famille: string
  categorie: string
  sous_categorie: string | null
  tva_defaut: string
  est_ingredient_resto: boolean
  priorite_ingredient: number
}

export interface VenteRestaurant {
  date: string
  canal: string | null
  nb_plats: number
  ca_ttc: string
  ca_ht: string | null
  marge_brute: string | null
}

export interface TopPlat {
  plat: string
  categorie: string | null
  nb_vendus: number
  ca_ttc: string
  marge_brute: string
  food_cost_pct: number | null
  rang_marge: number
  rang_volume: number
}

export interface TopProduit {
  produit: string
  famille: string
  categorie: string
  volume_vendu: string
  ca_total: string
  marge_totale: string
  marge_pct: number | null
}

export interface DepenseSynthese {
  annee: number
  mois: number
  annee_mois: string
  centre_cout: string | null
  type_cout: string | null
  total_ht: string
  total_ttc: string
  budget_mensuel: string | null
  execution_pct: number | null
}

export interface StockValorisation {
  date: string
  famille: string
  categorie: string
  quantite_totale: string
  valeur_totale: string
  nb_ruptures: number
  rotation_moyenne: number | null
}

export interface MouvementStock {
  date: string
  produit: string
  type_mouvement: string
  quantite: string
  valeur: string | null
}

// API Functions
export const analyticsApi = {
  // Dashboard KPIs
  getDashboardKPIs: async (): Promise<DashboardKPIs> => {
    const response = await apiClient.get('/analytics/dashboard')
    return response.data
  },

  // Categories
  getCategories: async (): Promise<Categorie[]> => {
    const response = await apiClient.get('/analytics/categories')
    return response.data
  },

  // Categories Produits (hierarchie complete)
  getCategoriesProduits: async (params?: {
    famille?: string
    ingredients_only?: boolean
  }): Promise<CategorieProduit[]> => {
    const response = await apiClient.get('/analytics/categories-produits', { params })
    return response.data
  },

  // Ventes Restaurant
  getVentesRestaurant: async (params?: {
    date_debut?: string
    date_fin?: string
  }): Promise<VenteRestaurant[]> => {
    const response = await apiClient.get('/analytics/ventes/restaurant', { params })
    return response.data
  },

  // Top Plats
  getTopPlats: async (limit = 10): Promise<TopPlat[]> => {
    const response = await apiClient.get('/analytics/ventes/top-plats', {
      params: { limit },
    })
    return response.data
  },

  // Top Produits
  getTopProduits: async (limit = 10): Promise<TopProduit[]> => {
    const response = await apiClient.get('/analytics/produits/top', {
      params: { limit },
    })
    return response.data
  },

  // Depenses Synthese
  getDepensesSynthese: async (params?: {
    annee?: number
    mois?: number
  }): Promise<DepenseSynthese[]> => {
    const response = await apiClient.get('/analytics/depenses/synthese', { params })
    return response.data
  },

  // Stock Valorisation
  getStockValorisation: async (params?: {
    date_debut?: string
    date_fin?: string
  }): Promise<StockValorisation[]> => {
    const response = await apiClient.get('/analytics/stock/valorisation', { params })
    return response.data
  },

  // Mouvements Stock
  getMouvementsStock: async (params?: {
    date_debut?: string
    date_fin?: string
    type_mouvement?: 'ENTREE' | 'SORTIE' | 'INVENTAIRE'
    limit?: number
  }): Promise<MouvementStock[]> => {
    const response = await apiClient.get('/analytics/stock/mouvements', { params })
    return response.data
  },
}
