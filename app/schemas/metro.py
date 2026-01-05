"""
Schémas Pydantic pour l'API METRO
Validation et sérialisation des données METRO
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Schémas de base
# ============================================================================

class MetroLigneBase(BaseModel):
    """Schéma de base pour une ligne de facture"""
    ean: str = Field(..., description="Code EAN du produit", max_length=20)
    article_numero: Optional[str] = Field(None, description="Numéro article METRO", max_length=20)
    designation: str = Field(..., description="Désignation du produit", max_length=255)

    # Colisage et quantités
    colisage: int = Field(1, description="Nombre d'unités par colis", ge=1)
    quantite_colis: Decimal = Field(..., description="Quantité de colis achetés", ge=0)
    quantite_unitaire: Decimal = Field(..., description="Quantité totale en unités", ge=0)

    # Prix
    prix_colis: Decimal = Field(..., description="Prix par colis HT", ge=0)
    prix_unitaire: Decimal = Field(..., description="Prix unitaire réel HT", ge=0)
    montant_ht: Decimal = Field(..., description="Montant HT", ge=0)

    # Volume/Poids
    volume_unitaire: Optional[Decimal] = Field(None, description="Volume unitaire en L")
    unite: str = Field("U", description="Unité de mesure", max_length=10)

    # TVA
    taux_tva: Decimal = Field(20, description="Taux de TVA", ge=0, le=100)
    code_tva: Optional[str] = Field(None, description="Code TVA METRO", max_length=5)
    montant_tva: Decimal = Field(0, description="Montant TVA", ge=0)

    # Classification
    regie: Optional[str] = Field(None, description="Code régie alcool", max_length=5)
    vol_alcool: Optional[Decimal] = Field(None, description="Volume d'alcool %", ge=0, le=100)
    categorie_id: Optional[int] = Field(None, description="ID catégorie unifiée")


class MetroFactureBase(BaseModel):
    """Schéma de base pour une facture"""
    numero: str = Field(..., description="Numéro de facture", max_length=50)
    date_facture: date = Field(..., description="Date de la facture")
    magasin: str = Field(..., description="Magasin METRO", max_length=100)
    total_ht: Decimal = Field(..., description="Total HT", ge=0)
    total_tva: Decimal = Field(0, description="Total TVA", ge=0)
    total_ttc: Decimal = Field(0, description="Total TTC", ge=0)


# ============================================================================
# Schémas de réponse (lecture)
# ============================================================================

class MetroLigneResponse(MetroLigneBase):
    """Réponse pour une ligne de facture"""
    id: int
    facture_id: int
    categorie: str = Field(default="Epicerie", description="Catégorie calculée")

    model_config = ConfigDict(from_attributes=True)


class MetroFactureResponse(MetroFactureBase):
    """Réponse pour une facture avec ses lignes"""
    id: int
    fichier_source: Optional[str] = None
    importee_le: datetime
    nb_lignes: int = Field(default=0, description="Nombre de lignes")
    lignes: List[MetroLigneResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MetroFactureListItem(MetroFactureBase):
    """Item de liste pour les factures (sans lignes détaillées)"""
    id: int
    nb_lignes: int = Field(default=0, description="Nombre de lignes")
    importee_le: datetime

    model_config = ConfigDict(from_attributes=True)


class MetroFactureListResponse(BaseModel):
    """Réponse paginée pour la liste des factures"""
    items: List[MetroFactureListItem]
    total: int
    page: int
    per_page: int
    pages: int


# ============================================================================
# Schémas Produits Agrégés
# ============================================================================

class MetroProduitResponse(BaseModel):
    """Réponse pour un produit agrégé (catalogue)"""
    id: int
    ean: str
    article_numero: Optional[str] = None
    designation: str

    # Colisage
    colisage_moyen: int = 1
    unite: str = "U"
    volume_unitaire: Optional[Decimal] = None

    # Agrégats quantités
    quantite_colis_totale: Decimal
    quantite_unitaire_totale: Decimal

    # Montants
    montant_total_ht: Decimal
    montant_total_tva: Decimal
    montant_total: Decimal  # TTC
    nb_achats: int

    # Prix unitaire réel (pas par colis)
    prix_unitaire_moyen: Decimal
    prix_unitaire_min: Decimal
    prix_unitaire_max: Decimal
    prix_colis_moyen: Decimal

    # TVA
    taux_tva: Decimal

    # Classification unifiée
    categorie_id: Optional[int] = None
    famille: str = "DIVERS"
    categorie: str = "Divers"
    sous_categorie: Optional[str] = None

    # Classification source METRO
    regie: Optional[str] = None
    vol_alcool: Optional[Decimal] = None

    # Dates
    premier_achat: Optional[date] = None
    dernier_achat: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class MetroProduitListResponse(BaseModel):
    """Réponse paginée pour la liste des produits"""
    items: List[MetroProduitResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ============================================================================
# Schémas pour le Dashboard / KPIs
# ============================================================================

class MetroSummary(BaseModel):
    """Résumé global des données METRO"""
    nb_factures: int = Field(..., description="Nombre total de factures")
    nb_produits: int = Field(..., description="Nombre de produits uniques")
    nb_lignes: int = Field(..., description="Nombre total de lignes")
    total_ht: Decimal = Field(..., description="Total HT global")
    total_tva: Decimal = Field(..., description="Total TVA global")
    total_ttc: Decimal = Field(..., description="Total TTC global")
    date_premiere_facture: Optional[date] = None
    date_derniere_facture: Optional[date] = None


class MetroCategoryStats(BaseModel):
    """Statistiques par catégorie"""
    categorie: str
    nb_produits: int
    quantite_totale: Decimal
    montant_total_ht: Decimal
    montant_total_tva: Decimal
    pct_ca: Decimal = Field(..., description="Pourcentage du CA")


class MetroTvaStats(BaseModel):
    """Statistiques par taux de TVA"""
    taux_tva: Decimal
    nb_produits: int
    montant_ht: Decimal
    montant_tva: Decimal
    pct_total: Decimal


class MetroDashboard(BaseModel):
    """Dashboard complet METRO"""
    summary: MetroSummary
    categories: List[MetroCategoryStats]
    tva_breakdown: List[MetroTvaStats]
    top_produits: List[MetroProduitResponse]


# ============================================================================
# Schémas d'import
# ============================================================================

class MetroLigneImport(BaseModel):
    """Schéma pour l'import d'une ligne depuis JSON"""
    ean: str
    article_numero: Optional[str] = None
    designation: str
    quantite: float
    prix_unitaire: float
    montant: float
    taux_tva: float = 20
    code_tva: Optional[str] = None
    regie: Optional[str] = None
    vol_alcool: Optional[float] = None


class MetroFactureImport(BaseModel):
    """Schéma pour l'import d'une facture depuis JSON"""
    numero: str
    date: str  # Format YYYY-MM-DD
    magasin: str
    total_ht: float
    lignes: List[MetroLigneImport]


class MetroDataImport(BaseModel):
    """Schéma pour l'import complet depuis metro_data.json"""
    summary: dict
    factures: List[MetroFactureImport]


class MetroImportResult(BaseModel):
    """Résultat d'un import METRO"""
    success: bool
    nb_factures_importees: int
    nb_lignes_importees: int
    nb_produits_agreges: int
    erreurs: List[str] = Field(default_factory=list)
    duree_ms: int
