/**
 * Types Restaurant Domain
 * Ingredients, Plats, Stock, Consumptions, Charges
 */

// =============================================================================
// Enums
// =============================================================================

export enum RestaurantUnit {
  UNITE = 'U',
  KILOGRAMME = 'KG',
  LITRE = 'L',
  GRAMME = 'G',
  CENTILITRE = 'CL',
  MILLILITRE = 'ML',
}

export enum RestaurantIngredientCategory {
  VIANDE = 'VIANDE',
  POISSON = 'POISSON',
  LEGUME = 'LEGUME',
  FRUIT = 'FRUIT',
  PRODUIT_LAITIER = 'PRODUIT_LAITIER',
  EPICERIE = 'EPICERIE',
  BOISSON = 'BOISSON',
  CONDIMENT = 'CONDIMENT',
  AUTRE = 'AUTRE',
}

export enum RestaurantPlatCategory {
  ENTREE = 'ENTREE',
  PLAT = 'PLAT',
  DESSERT = 'DESSERT',
  BOISSON = 'BOISSON',
  MENU = 'MENU',
  ACCOMPAGNEMENT = 'ACCOMPAGNEMENT',
  AUTRE = 'AUTRE',
  // Nouvelles categories restaurant
  VIANDES = 'VIANDES',
  POISSONS = 'POISSONS',
  BOUILLONS = 'BOUILLONS',
  GRILLADES = 'GRILLADES',
  PLATS_EN_SAUCE = 'PLATS_EN_SAUCE',
  LEGUMES = 'LEGUMES',
  TRADITIONNELS = 'TRADITIONNELS',
  SOFT = 'SOFT',
}

export enum RestaurantStockMovementType {
  ENTREE = 'ENTREE',
  SORTIE = 'SORTIE',
  AJUSTEMENT = 'AJUSTEMENT',
  PERTE = 'PERTE',
  TRANSFERT = 'TRANSFERT',
  INVENTAIRE = 'INVENTAIRE',
}

export enum RestaurantConsumptionType {
  VENTE = 'VENTE',
  PERTE = 'PERTE',
  REPAS_STAFF = 'REPAS_STAFF',
  OFFERT = 'OFFERT',
}

export enum RestaurantChargeType {
  LOYER = 'LOYER',
  SALAIRES = 'SALAIRES',
  ELECTRICITE = 'ELECTRICITE',
  EAU = 'EAU',
  GAZ = 'GAZ',
  ASSURANCE = 'ASSURANCE',
  ENTRETIEN = 'ENTRETIEN',
  MARKETING = 'MARKETING',
  AUTRES = 'AUTRES',
}

export enum RestaurantChargeFrequency {
  MENSUEL = 'MENSUEL',
  TRIMESTRIEL = 'TRIMESTRIEL',
  ANNUEL = 'ANNUEL',
  PONCTUEL = 'PONCTUEL',
}

// =============================================================================
// Ingredients
// =============================================================================

export interface Ingredient {
  id: number;
  name: string;
  unit: RestaurantUnit;
  category: RestaurantIngredientCategory;
  prix_unitaire: number; // centimes
  seuil_alerte: number | null;
  default_supplier_id: number | null;
  notes: string | null;
  is_active: boolean;
}

export interface IngredientCreate {
  name: string;
  unit: RestaurantUnit;
  category?: RestaurantIngredientCategory;
  prix_unitaire?: number;
  seuil_alerte?: number;
  default_supplier_id?: number;
  notes?: string;
}

export interface IngredientUpdate {
  name?: string;
  unit?: RestaurantUnit;
  category?: RestaurantIngredientCategory;
  prix_unitaire?: number;
  seuil_alerte?: number;
  default_supplier_id?: number;
  notes?: string;
}

// =============================================================================
// Plats
// =============================================================================

export interface PlatIngredient {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  quantite: number;
  cout_ligne: number; // centimes
  notes: string | null;
}

export interface Plat {
  id: number;
  name: string;
  prix_vente: number; // centimes
  category: RestaurantPlatCategory;
  description: string | null;
  is_menu: boolean;
  is_active: boolean;
  cout_total: number; // centimes
  food_cost_ratio: number; // percentage (0-100)
  is_profitable: boolean;
}

export interface PlatDetail extends Plat {
  ingredients: PlatIngredient[];
}

export interface PlatIngredientInput {
  ingredient_id: number;
  quantite: number;
  notes?: string;
}

export interface PlatCreate {
  name: string;
  prix_vente: number;
  category?: RestaurantPlatCategory;
  description?: string;
  is_menu?: boolean;
  image_url?: string;
  notes?: string;
  ingredients?: PlatIngredientInput[];
}

export interface PlatUpdate {
  name?: string;
  prix_vente?: number;
  category?: RestaurantPlatCategory;
  description?: string;
  is_menu?: boolean;
  image_url?: string;
  notes?: string;
}

// =============================================================================
// Stock
// =============================================================================

export interface Stock {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  quantite_actuelle: number;
  dernier_prix_achat: number | null;
  valeur_stock: number; // centimes
  is_low_stock: boolean;
}

export interface StockMovement {
  id: number;
  stock_id: number;
  type: RestaurantStockMovementType;
  quantite: number;
  quantite_avant: number;
  reference: string | null;
  notes: string | null;
  cout_unitaire: number | null;
  created_at: string;
}

export interface StockMovementCreate {
  ingredient_id: number;
  quantite: number;
  movement_type: RestaurantStockMovementType;
  reference?: string;
  notes?: string;
  cout_unitaire?: number;
}

export interface StockAdjustment {
  ingredient_id: number;
  nouvelle_quantite: number;
  notes?: string;
}

export interface StockAlert {
  ingredient_id: number;
  ingredient_name: string;
  quantite_actuelle: number;
  seuil_alerte: number;
  unit: RestaurantUnit;
}

// =============================================================================
// Consumptions
// =============================================================================

export interface Consumption {
  id: number;
  plat_id: number;
  plat_name: string;
  type: RestaurantConsumptionType;
  quantite: number;
  prix_vente: number;
  cout: number;
  date: string;
  notes: string | null;
}

export interface ConsumptionCreate {
  plat_id: number;
  quantite?: number;
  prix_vente?: number;
  date_consumption?: string;
  notes?: string;
  decrement_stock?: boolean;
}

export interface DailySummary {
  date: string;
  total_revenue: number;
  total_cost: number;
  margin: number;
  ventes: { count: number; revenue: number };
  pertes: { count: number; cost: number };
  repas_staff: { count: number; cost: number };
  offerts: { count: number; cost: number };
}

export interface BestSeller {
  plat_id: number;
  plat_name: string;
  total_sold: number;
  total_revenue: number;
}

export interface LossReport {
  total_losses: number;
  total_cost: number;
  by_plat: { plat_id: number; plat_name: string; count: number; cost: number }[];
}

// =============================================================================
// Charges
// =============================================================================

export interface Charge {
  id: number;
  name: string;
  type: RestaurantChargeType;
  montant: number; // centimes
  frequency: RestaurantChargeFrequency;
  montant_mensuel: number; // centimes (normalized)
  date_debut: string;
  date_fin: string | null;
  is_active: boolean;
  notes: string | null;
}

export interface ChargeCreate {
  name: string;
  charge_type: RestaurantChargeType;
  montant: number;
  frequency?: RestaurantChargeFrequency;
  date_debut?: string;
  date_fin?: string;
  notes?: string;
}

export interface ChargeUpdate {
  name?: string;
  charge_type?: RestaurantChargeType;
  montant?: number;
  frequency?: RestaurantChargeFrequency;
  date_debut?: string;
  date_fin?: string;
  notes?: string;
}

export interface ChargesSummary {
  total_mensuel: number;
  by_type: Record<RestaurantChargeType, number>;
}

export interface ChargesBreakdown {
  type: RestaurantChargeType;
  charges: Charge[];
  total: number;
}

// =============================================================================
// Dashboard
// =============================================================================

export interface RestaurantDashboardData {
  date: string;
  stock: {
    total_value: number;
    alerts_count: number;
    alerts: StockAlert[];
  };
  charges: {
    monthly_total: number;
    by_type: Record<RestaurantChargeType, number>;
  };
  daily: {
    revenue: number;
    cost: number;
    margin: number;
    sales_count: number;
    losses_count: number;
  };
}

// =============================================================================
// Helpers
// =============================================================================

export const UNIT_LABELS: Record<RestaurantUnit, string> = {
  [RestaurantUnit.UNITE]: 'Unite',
  [RestaurantUnit.KILOGRAMME]: 'Kg',
  [RestaurantUnit.LITRE]: 'L',
  [RestaurantUnit.GRAMME]: 'g',
  [RestaurantUnit.CENTILITRE]: 'cL',
  [RestaurantUnit.MILLILITRE]: 'mL',
};

export const INGREDIENT_CATEGORY_LABELS: Record<RestaurantIngredientCategory, string> = {
  [RestaurantIngredientCategory.VIANDE]: 'Viande',
  [RestaurantIngredientCategory.POISSON]: 'Poisson',
  [RestaurantIngredientCategory.LEGUME]: 'Legume',
  [RestaurantIngredientCategory.FRUIT]: 'Fruit',
  [RestaurantIngredientCategory.PRODUIT_LAITIER]: 'Produit laitier',
  [RestaurantIngredientCategory.EPICERIE]: 'Epicerie',
  [RestaurantIngredientCategory.BOISSON]: 'Boisson',
  [RestaurantIngredientCategory.CONDIMENT]: 'Condiment',
  [RestaurantIngredientCategory.AUTRE]: 'Autre',
};

export const PLAT_CATEGORY_LABELS: Record<RestaurantPlatCategory, string> = {
  [RestaurantPlatCategory.ENTREE]: 'Entrees',
  [RestaurantPlatCategory.PLAT]: 'Plat',
  [RestaurantPlatCategory.DESSERT]: 'Desserts',
  [RestaurantPlatCategory.BOISSON]: 'Boissons',
  [RestaurantPlatCategory.MENU]: 'Menus',
  [RestaurantPlatCategory.ACCOMPAGNEMENT]: 'Accompagnements',
  [RestaurantPlatCategory.AUTRE]: 'Autre',
  [RestaurantPlatCategory.VIANDES]: 'Viandes',
  [RestaurantPlatCategory.POISSONS]: 'Poissons',
  [RestaurantPlatCategory.BOUILLONS]: 'Bouillons',
  [RestaurantPlatCategory.GRILLADES]: 'Grillades',
  [RestaurantPlatCategory.PLATS_EN_SAUCE]: 'Plats en sauce',
  [RestaurantPlatCategory.LEGUMES]: 'Legumes',
  [RestaurantPlatCategory.TRADITIONNELS]: 'Traditionnels',
  [RestaurantPlatCategory.SOFT]: 'Soft drinks',
};

export const CHARGE_TYPE_LABELS: Record<RestaurantChargeType, string> = {
  [RestaurantChargeType.LOYER]: 'Loyer',
  [RestaurantChargeType.SALAIRES]: 'Salaires',
  [RestaurantChargeType.ELECTRICITE]: 'Electricite',
  [RestaurantChargeType.EAU]: 'Eau',
  [RestaurantChargeType.GAZ]: 'Gaz',
  [RestaurantChargeType.ASSURANCE]: 'Assurance',
  [RestaurantChargeType.ENTRETIEN]: 'Entretien',
  [RestaurantChargeType.MARKETING]: 'Marketing',
  [RestaurantChargeType.AUTRES]: 'Autres',
};

export const CHARGE_FREQUENCY_LABELS: Record<RestaurantChargeFrequency, string> = {
  [RestaurantChargeFrequency.MENSUEL]: 'Mensuel',
  [RestaurantChargeFrequency.TRIMESTRIEL]: 'Trimestriel',
  [RestaurantChargeFrequency.ANNUEL]: 'Annuel',
  [RestaurantChargeFrequency.PONCTUEL]: 'Ponctuel',
};

export const CONSUMPTION_TYPE_LABELS: Record<RestaurantConsumptionType, string> = {
  [RestaurantConsumptionType.VENTE]: 'Vente',
  [RestaurantConsumptionType.PERTE]: 'Perte',
  [RestaurantConsumptionType.REPAS_STAFF]: 'Repas staff',
  [RestaurantConsumptionType.OFFERT]: 'Offert',
};

export const STOCK_MOVEMENT_TYPE_LABELS: Record<RestaurantStockMovementType, string> = {
  [RestaurantStockMovementType.ENTREE]: 'Entree',
  [RestaurantStockMovementType.SORTIE]: 'Sortie',
  [RestaurantStockMovementType.AJUSTEMENT]: 'Ajustement',
  [RestaurantStockMovementType.PERTE]: 'Perte',
  [RestaurantStockMovementType.TRANSFERT]: 'Transfert',
  [RestaurantStockMovementType.INVENTAIRE]: 'Inventaire',
};

// =============================================================================
// Epicerie Links (Rapprochement)
// =============================================================================

export type FournisseurType = 'METRO' | 'TAIYAT' | 'EUROCIEL' | 'OTHER';

export interface EpicerieLink {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  produit_id: number;
  produit_nom: string | null;
  produit_prix: number | null;
  fournisseur: FournisseurType;
  ratio: number;
  is_primary: boolean;
}

export interface EpicerieLinkCreate {
  ingredient_id: number;
  produit_id: number;
  fournisseur: FournisseurType;
  ratio?: number;
  is_primary?: boolean;
}

export interface EpicerieLinkUpdate {
  ratio?: number;
  is_primary?: boolean;
}

export interface IngredientWithLinks extends Ingredient {
  epicerie_links: EpicerieLink[];
}

export interface EpicerieProduit {
  id: number;
  fournisseur: FournisseurType;
  fournisseur_color: string;
  designation: string;
  famille: string | null;
  categorie: string | null;
  prix_unitaire_moyen: number | null;
  unite: string | null;
}

export interface PriceSyncResult {
  updated: number;
  skipped: number;
  errors: { ingredient_id: number; error: string }[];
  price_changes: {
    ingredient_id: number;
    ingredient_name: string;
    old_prix: number;
    new_prix: number;
    produit_nom: string;
  }[];
}
