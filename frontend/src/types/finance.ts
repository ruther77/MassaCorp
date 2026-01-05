// ============================================
// Enums et types de base
// ============================================

export type InvoiceType = 'achat' | 'vente' | 'avoir_achat' | 'avoir_vente';
export type InvoiceStatus = 'brouillon' | 'validee' | 'envoyee' | 'partiellement_payee' | 'payee' | 'en_litige' | 'annulee';
export type PaymentMethod = 'virement' | 'cheque' | 'carte' | 'especes' | 'prelevement' | 'lcr';
export type PaymentStatus = 'en_attente' | 'valide' | 'rejete' | 'annule';
export type BankMovementType = 'credit' | 'debit';
export type BudgetStatus = 'brouillon' | 'valide' | 'cloture';

// ============================================
// Dimensions (DWH)
// ============================================

export interface Currency {
  devise_id: number;
  code_iso: string;
  nom: string;
  symbole: string;
  taux_change_eur: number;
}

export interface PaymentMode {
  mode_paiement_id: number;
  code: PaymentMethod;
  libelle: string;
  delai_encaissement_jours: number;
}

export interface DocumentType {
  type_document_id: number;
  code: InvoiceType;
  libelle: string;
  sens: 'debit' | 'credit';
}

export interface DocumentStatus {
  statut_document_id: number;
  code: InvoiceStatus;
  libelle: string;
  ordre_affichage: number;
  couleur: string;
}

export interface BankAccount {
  compte_bancaire_sk: number;
  compte_bancaire_id: number;
  banque_nom: string;
  iban: string;
  bic: string;
  libelle: string;
  devise_code: string;
  est_actif: boolean;
  solde_actuel?: number;
}

export interface FiscalYear {
  exercice_id: number;
  code: string;
  libelle: string;
  date_debut: string;
  date_fin: string;
  est_cloture: boolean;
  est_actif: boolean;
}

export interface Supplier {
  fournisseur_sk: number;
  fournisseur_id: number;
  code: string;
  raison_sociale: string;
  siret?: string;
  adresse?: string;
  email?: string;
  telephone?: string;
  conditions_paiement_jours: number;
  est_actif: boolean;
}

export interface CostCenter {
  cost_center_id: number;
  code: string;
  libelle: string;
  responsable?: string;
  budget_annuel?: number;
}

export interface ExpenseCategory {
  categorie_depense_id: number;
  code: string;
  libelle: string;
  compte_comptable?: string;
  parent_id?: number;
}

// ============================================
// Factures
// ============================================

export interface Invoice {
  facture_sk: number;
  facture_id: number;
  numero: string;
  type: InvoiceType;
  type_libelle: string;
  statut: InvoiceStatus;
  statut_libelle: string;
  statut_couleur: string;

  // Tiers
  fournisseur_id?: number;
  fournisseur_nom?: string;
  client_id?: number;
  client_nom?: string;

  // Dates
  date_facture: string;
  date_echeance: string;
  date_reception?: string;

  // Montants
  devise_code: string;
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;
  montant_paye: number;
  solde_du: number;

  // Paiement
  mode_paiement?: PaymentMethod;
  mode_paiement_libelle?: string;

  // Métadonnées
  reference_externe?: string;
  notes?: string;
  fichier_url?: string;
  score_confiance?: number;

  // Lignes
  lignes?: InvoiceLine[];

  // Audit
  created_at: string;
  updated_at: string;
}

export interface InvoiceLine {
  ligne_facture_sk: number;
  ligne_facture_id: number;
  facture_id: number;
  numero_ligne: number;

  // Produit
  produit_id?: number;
  produit_code?: string;
  produit_libelle?: string;

  // Description
  designation: string;
  description?: string;

  // Quantités et prix
  quantite: number;
  unite?: string;
  prix_unitaire_ht: number;
  taux_tva: number;
  montant_ht: number;
  montant_tva: number;
  montant_ttc: number;

  // Remise
  taux_remise?: number;
  montant_remise?: number;

  // Analytique
  cost_center_id?: number;
  cost_center_libelle?: string;
  categorie_depense_id?: number;
  categorie_depense_libelle?: string;
}

export interface InvoiceFilters {
  [key: string]: string | number | boolean | undefined;
  search?: string;
  type?: InvoiceType;
  statut?: InvoiceStatus;
  fournisseur_id?: number;
  date_debut?: string;
  date_fin?: string;
  montant_min?: number;
  montant_max?: number;
  en_retard?: boolean;
}

// ============================================
// Paiements
// ============================================

export interface Payment {
  paiement_sk: number;
  paiement_id: number;
  reference: string;

  // Type et statut
  mode_paiement: PaymentMethod;
  mode_paiement_libelle: string;
  statut: PaymentStatus;

  // Montant
  devise_code: string;
  montant: number;

  // Dates
  date_paiement: string;
  date_valeur?: string;

  // Compte bancaire
  compte_bancaire_id?: number;
  compte_bancaire_libelle?: string;

  // Références
  reference_banque?: string;
  notes?: string;

  // Affectations
  affectations?: PaymentAllocation[];
  montant_affecte: number;
  montant_non_affecte: number;

  // Audit
  created_at: string;
}

export interface PaymentAllocation {
  affectation_id: number;
  paiement_id: number;
  facture_id: number;
  facture_numero: string;
  montant_affecte: number;
  date_affectation: string;
}

// ============================================
// Mouvements bancaires
// ============================================

export interface BankMovement {
  mouvement_sk: number;
  mouvement_id: number;

  // Compte
  compte_bancaire_id: number;
  compte_bancaire_libelle: string;

  // Mouvement
  date_operation: string;
  date_valeur: string;
  type_mouvement: BankMovementType;
  montant: number;

  // Détails
  libelle: string;
  reference?: string;

  // Rapprochement
  est_rapproche: boolean;
  paiement_id?: number;
  facture_id?: number;

  // Catégorisation
  categorie_depense_id?: number;
  categorie_depense_libelle?: string;

  // Solde
  solde_apres_operation: number;
}

export interface BankMovementFilters {
  compte_bancaire_id?: number;
  date_debut?: string;
  date_fin?: string;
  type_mouvement?: BankMovementType;
  est_rapproche?: boolean;
  montant_min?: number;
  montant_max?: number;
}

// ============================================
// Trésorerie
// ============================================

export interface TreasuryPosition {
  date_position: string;
  compte_bancaire_id: number;
  compte_bancaire_libelle: string;
  devise_code: string;
  solde_debut_journee: number;
  total_credits: number;
  total_debits: number;
  solde_fin_journee: number;
}

export interface TreasurySummary {
  date: string;
  solde_total: number;
  solde_par_devise: Array<{
    devise_code: string;
    solde: number;
    solde_eur: number;
  }>;
  variation_jour: number;
  variation_semaine: number;
  variation_mois: number;
}

export interface CashFlowForecast {
  date: string;
  solde_prevu: number;
  encaissements_prevus: number;
  decaissements_prevus: number;
  echeances_fournisseurs: number;
  echeances_clients: number;
}

// ============================================
// Budget
// ============================================

export interface Budget {
  budget_sk: number;
  budget_id: number;

  // Références
  exercice_id: number;
  exercice_libelle: string;
  cost_center_id: number;
  cost_center_libelle: string;
  categorie_depense_id?: number;
  categorie_depense_libelle?: string;

  // Période
  mois: number;
  annee: number;

  // Montants
  montant_budgete: number;
  montant_engage: number;
  montant_realise: number;
  ecart: number;
  taux_consommation: number;

  // Statut
  statut: BudgetStatus;
  notes?: string;
}

export interface BudgetSummary {
  exercice_id: number;
  exercice_libelle: string;
  total_budgete: number;
  total_engage: number;
  total_realise: number;
  ecart_global: number;
  taux_consommation_global: number;
  par_cost_center: Array<{
    cost_center_id: number;
    cost_center_libelle: string;
    budgete: number;
    realise: number;
    ecart: number;
    taux: number;
  }>;
}

// ============================================
// Échéancier
// ============================================

export interface DueDate {
  echeance_sk: number;
  echeance_id: number;

  // Facture
  facture_id: number;
  facture_numero: string;
  type_document: InvoiceType;

  // Tiers
  fournisseur_id?: number;
  fournisseur_nom?: string;
  client_id?: number;
  client_nom?: string;

  // Dates
  date_echeance: string;
  date_facture: string;

  // Montants
  devise_code: string;
  montant_initial: number;
  montant_restant: number;

  // Statut
  est_en_retard: boolean;
  jours_retard: number;
  statut_paiement: 'non_paye' | 'partiellement_paye' | 'paye';
}

export interface DueDateFilters {
  [key: string]: string | number | boolean | undefined;
  type?: 'fournisseur' | 'client' | 'tous';
  date_debut?: string;
  date_fin?: string;
  en_retard?: boolean;
  fournisseur_id?: number;
}

// ============================================
// Analytics Finance
// ============================================

export interface FinanceKPIs {
  // Trésorerie
  tresorerie_totale: number;
  variation_tresorerie_mois: number;

  // Factures
  factures_en_attente: number;
  montant_factures_en_attente: number;
  factures_en_retard: number;
  montant_factures_en_retard: number;

  // Paiements
  paiements_a_effectuer_7j: number;
  montant_paiements_7j: number;

  // Budget
  budget_consomme_pct: number;
  ecart_budget: number;

  // Encaissements
  encaissements_prevus_mois: number;
  decaissements_prevus_mois: number;
}

// ============================================
// Pagination et réponses API
// ============================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
  per_page: number;
}

export interface FinanceStats {
  total_factures: number;
  total_ttc: number;
  total_paye: number;
  total_du: number;
  par_statut: Array<{
    statut: InvoiceStatus;
    libelle: string;
    count: number;
    montant: number;
  }>;
}
