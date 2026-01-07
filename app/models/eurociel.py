"""
Modèles SQLAlchemy pour les données EUROCIEL
Tables dans le schéma DWH pour les factures fournisseur EUROCIEL

Fournisseur: EUROCIEL (grossiste alimentaire africain/tropical)
SIRET: 510154313
TVA: FR55510154313

Tables:
- dwh.eurociel_facture: Entêtes de factures EUROCIEL
- dwh.eurociel_ligne: Lignes de factures (produits)
- dwh.eurociel_produit_agregat: Vue agrégée des produits
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


class EurocielFacture(Base, TimestampMixin, TenantMixin):
    """
    Entête de facture EUROCIEL
    Stocke les informations générales de chaque facture fournisseur

    Types de documents:
    - FA: Facture
    - AV: Avoir (crédit)
    """
    __tablename__ = "eurociel_facture"
    __table_args__ = (
        Index("ix_eurociel_facture_numero", "tenant_id", "numero"),
        Index("ix_eurociel_facture_date", "tenant_id", "date_facture"),
        Index("ix_eurociel_facture_client", "tenant_id", "client_code"),
        UniqueConstraint("tenant_id", "numero", name="uq_eurociel_facture_numero"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(20), nullable=False, comment="Numéro de facture (FA/AV + numéro)")
    type_document: Mapped[str] = mapped_column(String(10), nullable=False, default="FA", comment="Type: FA=Facture, AV=Avoir")
    date_facture: Mapped[date] = mapped_column(Date, nullable=False, comment="Date de la facture")

    # Client / Détenteur
    client_nom: Mapped[str] = mapped_column(String(100), nullable=False, comment="Nom client (L'INCONTOURNABLE, NOUTAM)")
    client_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="Code client EUROCIEL")
    client_adresse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Adresse client")
    client_telephone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Téléphone client")

    # Totaux (facturés en HT)
    total_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total HT")
    total_tva: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total TVA")
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total TTC (NET A PAYER)")

    # Poids total
    poids_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, comment="Poids total en kg")
    quantite_totale: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True, comment="Quantité totale")

    # Métadonnées
    fichier_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Fichier PDF source")
    page_source: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="Page dans le PDF source")
    importee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="Date d'import")

    # Relations
    lignes: Mapped[List["EurocielLigne"]] = relationship("EurocielLigne", back_populates="facture", cascade="all, delete-orphan")


class EurocielLigne(Base, TenantMixin):
    """
    Ligne de facture EUROCIEL
    Détail de chaque produit acheté

    Particularités EUROCIEL:
    - Vente au poids (kg) avec prix au kg
    - TVA 5.5% (C07/C2) pour alimentaire, 20% (C08) pour non-alimentaire
    """
    __tablename__ = "eurociel_ligne"
    __table_args__ = (
        Index("ix_eurociel_ligne_designation", "tenant_id", "designation_clean"),
        Index("ix_eurociel_ligne_facture", "facture_id"),
        Index("ix_eurociel_ligne_ean", "tenant_id", "ean"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facture_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dwh.eurociel_facture.id", ondelete="CASCADE"), nullable=False)
    numero_ligne: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="Numéro de référence ligne")

    # Identification produit
    ean: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Code EAN (peut être renseigné manuellement)")
    designation: Mapped[str] = mapped_column(String(255), nullable=False, comment="Désignation brute du produit")
    designation_clean: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Désignation normalisée")

    # Quantités et poids
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=1, comment="Quantité commandée")
    poids: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, comment="Poids en kg")

    # Prix (HT)
    prix_unitaire: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="Prix unitaire HT (au colis/kg)")
    montant_ht: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="Montant HT")

    # TVA
    code_tva: Mapped[str] = mapped_column(String(5), nullable=False, default="C07", comment="Code TVA (C07=5.5%, C08=20%)")
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=5.5, comment="Taux de TVA")
    montant_tva: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Montant TVA calculé")
    montant_ttc: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Montant TTC calculé")

    # Flags
    est_promo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Produit en promotion")

    # Classification
    categorie_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dim_categorie_produit")

    # Relation
    facture: Mapped["EurocielFacture"] = relationship("EurocielFacture", back_populates="lignes")


class EurocielProduitAgregat(Base, TenantMixin):
    """
    Agrégation des produits EUROCIEL par désignation normalisée
    Calculée à partir des lignes de factures
    """
    __tablename__ = "eurociel_produit_agregat"
    __table_args__ = (
        Index("ix_eurociel_produit_designation", "tenant_id", "designation_clean"),
        Index("ix_eurociel_produit_categorie", "tenant_id", "categorie_id"),
        Index("ix_eurociel_produit_montant", "tenant_id", "montant_total"),
        Index("ix_eurociel_produit_ean", "tenant_id", "ean"),
        UniqueConstraint("tenant_id", "designation_clean", name="uq_eurociel_produit_designation"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identification
    ean: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Code EAN (renseigné manuellement)")
    designation_brute: Mapped[str] = mapped_column(Text, nullable=False, comment="Désignation originale")
    designation_clean: Mapped[str] = mapped_column(String(200), nullable=False, comment="Désignation normalisée (clé)")

    # Lien vers dim_produit (synchronisé)
    dim_produit_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dwh.dim_produit")

    # Agrégats quantités
    quantite_totale: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="Quantité totale")
    poids_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Poids total en kg")
    nb_achats: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="Nombre d'achats")

    # Montants
    montant_total_ht: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total HT")
    montant_total_tva: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, comment="Montant total TVA")
    montant_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total TTC")

    # Prix
    prix_moyen: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix moyen HT")
    prix_min: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix minimum HT")
    prix_max: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix maximum HT")

    # TVA
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=5.5, comment="Taux TVA principal")

    # Classification
    categorie_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dim_categorie_produit")
    famille: Mapped[str] = mapped_column(String(50), nullable=False, default="EPICERIE", comment="Famille")
    categorie: Mapped[str] = mapped_column(String(50), nullable=False, default="Alimentaire", comment="Catégorie")
    sous_categorie: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Sous-catégorie")

    # Dates
    premier_achat: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date du premier achat")
    dernier_achat: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date du dernier achat")

    # Métadonnées
    calcule_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="Date du dernier calcul")


# Codes TVA EUROCIEL
EUROCIEL_TVA_CODES = {
    "C07": 5.5,   # TVA réduite (alimentaire)
    "C2": 5.5,    # TVA réduite (alimentaire) - ancien code
    "C08": 20.0,  # TVA normale (non-alimentaire)
}


# Catégories EUROCIEL basées sur les produits observés
EUROCIEL_CATEGORIES = {
    "POISSON": [
        "COURBINE", "TILAPIA", "BARRACUDA", "OMBRINE", "PANGASIUS",
        "POISSON CHAT", "CREVETTE", "CRABE", "EMPEREUR", "ACOUPA",
        "KANDRATIKI", "IKAGEL"
    ],
    "VOLAILLE": [
        "POULET", "POULE", "AILE", "CUISSE", "PILON", "DINDE"
    ],
    "LEGUMES": [
        "MANIOC", "NDOLE", "FUMBWA", "GOMBO", "SAKA SAKA", "PLACALI",
        "PLANTAIN", "POMME DE TERRE", "IGNAME", "GINGEMBRE"
    ],
    "BOISSONS": [
        "MALTA", "VIMTO", "VITAMALT", "GUINESS"
    ],
    "SNACKS": [
        "CHIPS", "NOUILLE", "YUM YUM", "NEMS", "FRITE"
    ],
    "EPICERIE": [
        "LEGUME ROULEA", "SAC"
    ],
}


def categoriser_produit_eurociel(designation: str) -> tuple:
    """
    Catégorise un produit EUROCIEL basé sur sa désignation.

    Returns:
        tuple: (famille, categorie, sous_categorie)
    """
    designation_upper = designation.upper()

    for categorie, mots_cles in EUROCIEL_CATEGORIES.items():
        for mot in mots_cles:
            if mot in designation_upper:
                return ("EPICERIE", categorie.capitalize(), None)

    return ("EPICERIE", "Divers", None)


class EurocielCatalogueProduit(Base, TimestampMixin, TenantMixin):
    """
    Référence produit du catalogue EUROCIEL

    Données de référence extraites du catalogue fournisseur.
    Contient toutes les références disponibles chez EUROCIEL,
    même celles non encore achetées.
    """
    __tablename__ = "eurociel_catalogue_produit"
    __table_args__ = (
        Index("ix_eurociel_cat_ref", "tenant_id", "reference"),
        Index("ix_eurociel_cat_designation", "tenant_id", "designation"),
        Index("ix_eurociel_cat_categorie", "tenant_id", "categorie"),
        UniqueConstraint("tenant_id", "reference", name="uq_eurociel_catalogue_ref"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identification
    reference: Mapped[str] = mapped_column(String(20), nullable=False, comment="Code référence EUROCIEL (ex: 10 126)")
    designation: Mapped[str] = mapped_column(String(255), nullable=False, comment="Nom du produit")
    designation_clean: Mapped[str] = mapped_column(String(255), nullable=False, comment="Nom normalisé (uppercase)")

    # Catégorisation
    categorie: Mapped[str] = mapped_column(String(100), nullable=False, comment="Catégorie catalogue (POISSONS, VOLAILLES, etc.)")
    sous_categorie: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Sous-catégorie")

    # Caractéristiques produit
    taille: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Calibre/taille (ex: 500/800, 1000+)")
    conditionnement: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Conditionnement (ex: 10KG, 12X1KG)")
    poids_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, comment="Poids total du conditionnement en kg")
    origine: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Pays d'origine (SÉNÉGAL, CHINE, etc.)")

    # Métadonnées
    page_source: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="Page dans le catalogue PDF")
    actif: Mapped[bool] = mapped_column(Boolean, default=True, comment="Produit actif au catalogue")

    # Lien vers produit agrégé si acheté
    produit_agregat_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("dwh.eurociel_produit_agregat.id", ondelete="SET NULL"),
        nullable=True,
        comment="Lien vers le produit si acheté"
    )
