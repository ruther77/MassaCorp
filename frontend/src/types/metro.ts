// Types pour les API Metro (Epicerie)

export interface MetroSummary {
  nb_factures: number;
  nb_produits: number;
  nb_lignes: number;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  date_premiere_facture: string | null;
  date_derniere_facture: string | null;
}

export interface MetroProduct {
  id: number;
  ean: string;
  article_numero: string;
  designation: string;
  colisage_moyen: number;
  unite: string;
  volume_unitaire: string | null;
  quantite_colis_totale: string;
  quantite_unitaire_totale: string;
  montant_total_ht: string;
  montant_total_tva: string;
  montant_total: string;
  nb_achats: number;
  prix_unitaire_moyen: string;
  prix_unitaire_min: string;
  prix_unitaire_max: string;
  prix_colis_moyen: string;
  taux_tva: string;
  categorie_id: number | null;
  famille: string;
  categorie: string;
  sous_categorie: string | null;
  regie: string;
  vol_alcool: string | null;
  premier_achat: string | null;
  dernier_achat: string | null;
}

export interface MetroProductsResponse {
  items: MetroProduct[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface MetroFacture {
  id: number;
  numero_facture: string;
  date_facture: string;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
  nb_lignes: number;
}

export interface MetroFacturesResponse {
  items: MetroFacture[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface MetroFactureDetail extends MetroFacture {
  lignes: MetroFactureLigne[];
}

export interface MetroFactureLigne {
  id: number;
  produit_id: number;
  designation: string;
  quantite: number;
  prix_unitaire: string;
  montant_ht: string;
  montant_tva: string;
  montant_ttc: string;
  taux_tva: string;
}

export interface MetroCategory {
  id: number;
  nom: string;
  famille: string;
  nb_produits: number;
}

export interface MetroDashboard {
  summary: MetroSummary;
  top_products: MetroProduct[];
  categories_breakdown: MetroCategoryStats[];
  recent_factures: MetroFacture[];
}

export interface MetroCategoryStats {
  categorie: string;
  nb_produits: number;
  montant_total: string;
  pourcentage: number;
}

export interface MetroTVAStats {
  taux: string;
  montant_ht: string;
  montant_tva: string;
  pourcentage: number;
}

export interface MetroProductFilters {
  search?: string;
  famille?: string;
  categorie?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  per_page?: number;
}
