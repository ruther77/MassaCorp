"""
Modèles SQLAlchemy pour les données METRO
Tables dans le schéma DWH pour les factures fournisseur METRO

Tables:
- dwh.metro_facture: Entêtes de factures METRO
- dwh.metro_ligne: Lignes de factures (produits)
- dwh.metro_produit_agregat: Vue agrégée des produits par EAN
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Date, DateTime, Numeric, Boolean,
    ForeignKey, Index, Text, func, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin


class MetroFacture(Base, TimestampMixin, TenantMixin):
    """
    Entête de facture METRO
    Stocke les informations générales de chaque facture fournisseur
    """
    __tablename__ = "metro_facture"
    __table_args__ = (
        Index("ix_metro_facture_numero", "tenant_id", "numero"),
        Index("ix_metro_facture_date", "tenant_id", "date_facture"),
        UniqueConstraint("tenant_id", "numero", name="uq_metro_facture_numero"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(50), nullable=False, comment="Numéro de facture METRO")
    date_facture: Mapped[date] = mapped_column(Date, nullable=False, comment="Date de la facture")
    magasin: Mapped[str] = mapped_column(String(100), nullable=False, comment="Magasin METRO")

    # Totaux
    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total HT")
    total_tva: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total TVA")
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total TTC")

    # Métadonnées
    fichier_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Fichier PDF source")
    importee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="Date d'import")

    # Relations
    lignes: Mapped[List["MetroLigne"]] = relationship("MetroLigne", back_populates="facture", cascade="all, delete-orphan")


class MetroLigne(Base, TenantMixin):
    """
    Ligne de facture METRO
    Détail de chaque produit acheté
    """
    __tablename__ = "metro_ligne"
    __table_args__ = (
        Index("ix_metro_ligne_ean", "tenant_id", "ean"),
        Index("ix_metro_ligne_facture", "facture_id"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facture_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dwh.metro_facture.id", ondelete="CASCADE"), nullable=False)

    # Identification produit
    ean: Mapped[str] = mapped_column(String(20), nullable=False, comment="Code EAN du produit")
    article_numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Numéro article METRO")
    designation: Mapped[str] = mapped_column(String(255), nullable=False, comment="Désignation du produit")

    # Colisage et quantité
    colisage: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="Nombre d'unités par colis")
    quantite_colis: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, comment="Quantité de colis achetés")
    quantite_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, comment="Quantité totale en unités (colis * colisage)")

    # Prix
    prix_colis: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="Prix unitaire par colis HT")
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="Prix unitaire réel HT (prix_colis / colisage)")
    montant_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="Montant HT")

    # Volume/Poids (pour calcul prix au litre/kg)
    volume_unitaire: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Volume unitaire en L")
    poids_unitaire: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Poids unitaire en kg")
    unite: Mapped[str] = mapped_column(String(10), nullable=False, default="U", comment="Unité de mesure (U, L, KG)")

    # TVA
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=20, comment="Taux de TVA")
    code_tva: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="Code TVA METRO")
    montant_tva: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Montant TVA")

    # Classification alcools (source)
    regie: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="Code régie (S=Spiritueux, B=Bières, T=Vins, M=Mixtes)")
    vol_alcool: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True, comment="Volume d'alcool %")

    # Lien vers catégorie unifiée
    categorie_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dim_categorie_produit")

    # Relation
    facture: Mapped["MetroFacture"] = relationship("MetroFacture", back_populates="lignes")


class MetroProduitAgregat(Base, TenantMixin):
    """
    Vue matérialisée des produits METRO agrégés par EAN
    Calculée à partir des lignes de factures
    Contient les totaux et moyennes pour l'affichage catalogue
    """
    __tablename__ = "metro_produit_agregat"
    __table_args__ = (
        Index("ix_metro_produit_ean", "tenant_id", "ean"),
        Index("ix_metro_produit_categorie", "tenant_id", "categorie_id"),
        Index("ix_metro_produit_famille", "tenant_id", "famille"),
        Index("ix_metro_produit_montant", "tenant_id", "montant_total"),
        UniqueConstraint("tenant_id", "ean", name="uq_metro_produit_ean"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ean: Mapped[str] = mapped_column(String(20), nullable=False, comment="Code EAN unique")
    article_numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Numéro article METRO")
    designation: Mapped[str] = mapped_column(String(255), nullable=False, comment="Désignation du produit")

    # Colisage moyen
    colisage_moyen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="Colisage moyen observé")
    unite: Mapped[str] = mapped_column(String(10), nullable=False, default="U", comment="Unité de mesure")
    volume_unitaire: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Volume unitaire en L")

    # Agrégats en colis
    quantite_colis_totale: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="Quantité totale en colis")
    # Agrégats en unités réelles
    quantite_unitaire_totale: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="Quantité totale en unités")

    # Montants
    montant_total_ht: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total HT")
    montant_total_tva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total TVA")
    montant_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total TTC")
    nb_achats: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="Nombre d'achats")

    # Prix calculés (par unité réelle, pas par colis)
    prix_unitaire_moyen: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix moyen par unité")
    prix_unitaire_min: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix minimum par unité")
    prix_unitaire_max: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix maximum par unité")
    # Prix par colis (pour référence)
    prix_colis_moyen: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix moyen par colis")

    # TVA
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=20, comment="Taux TVA principal")

    # Classification unifiée (lien vers dim_categorie_produit)
    categorie_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dim_categorie_produit")
    famille: Mapped[str] = mapped_column(String(50), nullable=False, default="DIVERS", comment="Famille (BOISSONS, EPICERIE, etc.)")
    categorie: Mapped[str] = mapped_column(String(50), nullable=False, default="Divers", comment="Catégorie")
    sous_categorie: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Sous-catégorie")

    # Classification source METRO (régie alcools)
    regie: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="Code régie METRO")
    vol_alcool: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True, comment="Volume d'alcool %")

    # Dates
    premier_achat: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date du premier achat")
    dernier_achat: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date du dernier achat")

    # Métadonnées
    calcule_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="Date du dernier calcul")


class DimProduit(Base):
    """
    Référentiel maître des produits
    Table unifiée avec normalisation des désignations
    """
    __tablename__ = "dim_produit"
    __table_args__ = (
        Index("ix_dim_produit_ean", "ean"),
        Index("ix_dim_produit_marque", "marque"),
        Index("ix_dim_produit_famille", "famille", "categorie"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ean: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, comment="Code EAN unique")
    article_numero: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Numéro article fournisseur")

    # Désignations
    designation_brute: Mapped[str] = mapped_column(Text, nullable=False, comment="Désignation originale")
    designation_clean: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Désignation normalisée")
    nom_court: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, comment="Nom court pour affichage")

    # Marque et type
    marque: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Marque identifiée")
    type_produit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Type (Whisky, Vodka, etc.)")

    # Classification
    famille: Mapped[str] = mapped_column(String(50), nullable=False, default="EPICERIE", comment="Famille")
    categorie: Mapped[str] = mapped_column(String(50), nullable=False, default="Divers", comment="Catégorie")
    sous_categorie: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Sous-catégorie")

    # Caractéristiques
    contenance_cl: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True, comment="Contenance en CL")
    contenance_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Contenance affichée")
    degre_alcool: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True, comment="Degré d'alcool")

    # Colisage et TVA
    colisage_standard: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="Colisage standard")
    regie: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="Code régie alcool")
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=20, comment="Taux TVA")

    # Prix actuels
    prix_achat_unitaire: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Prix unitaire actuel")
    prix_achat_colis: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Prix colis actuel")
    date_dernier_prix: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date dernier prix")

    # Agrégats
    nb_achats: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="Nombre d'achats")
    quantite_totale_achetee: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="Quantité totale")
    montant_total_achats: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total HT")

    # Métadonnées
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="METRO", comment="Source des données")
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="Produit actif")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Constantes pour les catégories
METRO_CATEGORIES = {
    "S": "Spiritueux",
    "B": "Bières",
    "T": "Vins",
    "M": "Alcools",
    None: "Epicerie",
}


def get_categorie(regie: Optional[str]) -> str:
    """Retourne la catégorie à partir du code régie"""
    return METRO_CATEGORIES.get(regie, "Epicerie")
