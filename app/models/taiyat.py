"""
Modèles SQLAlchemy pour les données TAIYAT
Tables dans le schéma DWH pour les factures fournisseur TAI YAT DISTRIBUTION

Tables:
- dwh.taiyat_facture: Entêtes de factures TAIYAT
- dwh.taiyat_ligne: Lignes de factures (produits)
- dwh.taiyat_produit_agregat: Vue agrégée des produits
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


class TaiyatFacture(Base, TimestampMixin, TenantMixin):
    """
    Entête de facture TAIYAT
    Stocke les informations générales de chaque facture fournisseur
    """
    __tablename__ = "taiyat_facture"
    __table_args__ = (
        Index("ix_taiyat_facture_numero", "tenant_id", "numero"),
        Index("ix_taiyat_facture_date", "tenant_id", "date_facture"),
        Index("ix_taiyat_facture_client", "tenant_id", "client_nom"),
        UniqueConstraint("tenant_id", "numero", name="uq_taiyat_facture_numero"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(50), nullable=False, comment="Numéro de facture TAIYAT")
    date_facture: Mapped[date] = mapped_column(Date, nullable=False, comment="Date de la facture")
    echeance: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date d'échéance")

    # Client / Détenteur
    client_nom: Mapped[str] = mapped_column(String(100), nullable=False, comment="Nom client (NOUTAM, INCONTOURNABLE)")
    client_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Code client TAIYAT")

    # Totaux (TAIYAT facture en TTC)
    total_ht: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Total HT")
    total_tva: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Total TVA")
    total_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, comment="Total TTC (NET A PAYER)")

    # Métadonnées
    fichier_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Fichier PDF source")
    importee_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="Date d'import")

    # Relations
    lignes: Mapped[List["TaiyatLigne"]] = relationship("TaiyatLigne", back_populates="facture", cascade="all, delete-orphan")


class TaiyatLigne(Base, TenantMixin):
    """
    Ligne de facture TAIYAT
    Détail de chaque produit acheté
    """
    __tablename__ = "taiyat_ligne"
    __table_args__ = (
        Index("ix_taiyat_ligne_designation", "tenant_id", "designation_clean"),
        Index("ix_taiyat_ligne_facture", "facture_id"),
        Index("ix_taiyat_ligne_provenance", "tenant_id", "provenance"),
        Index("ix_taiyat_ligne_ean", "tenant_id", "ean"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    facture_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dwh.taiyat_facture.id", ondelete="CASCADE"), nullable=False)

    # Identification produit
    ean: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Code EAN (peut être renseigné manuellement)")
    designation: Mapped[str] = mapped_column(String(255), nullable=False, comment="Désignation brute du produit")
    designation_clean: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Désignation normalisée")
    provenance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Pays d'origine")

    # Quantités
    colis: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, comment="Nombre de colis")
    pieces: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="Nombre de pièces")
    unite: Mapped[str] = mapped_column(String(10), nullable=False, default="c", comment="Unité de vente")

    # Prix
    prix_unitaire_ht: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, comment="Prix unitaire HT")
    prix_unitaire_ttc: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True, comment="Prix unitaire TTC")
    montant_ttc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="Montant TTC")
    montant_ht: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True, comment="Montant HT calculé")

    # TVA
    code_tva: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="Code TVA (1=5.5%, 2=20%)")
    taux_tva: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=5.5, comment="Taux de TVA")

    # Flags
    est_remise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="Ligne de remise")

    # Classification
    categorie_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dim_categorie_produit")

    # Relation
    facture: Mapped["TaiyatFacture"] = relationship("TaiyatFacture", back_populates="lignes")


class TaiyatProduitAgregat(Base, TenantMixin):
    """
    Agrégation des produits TAIYAT par désignation normalisée
    Calculée à partir des lignes de factures
    """
    __tablename__ = "taiyat_produit_agregat"
    __table_args__ = (
        Index("ix_taiyat_produit_designation", "tenant_id", "designation_clean"),
        Index("ix_taiyat_produit_provenance", "tenant_id", "provenance"),
        Index("ix_taiyat_produit_categorie", "tenant_id", "categorie_id"),
        Index("ix_taiyat_produit_montant", "tenant_id", "montant_total"),
        Index("ix_taiyat_produit_ean", "tenant_id", "ean"),
        UniqueConstraint("tenant_id", "designation_clean", name="uq_taiyat_produit_designation"),
        {"schema": "dwh"}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identification
    ean: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Code EAN (renseigné manuellement)")
    designation_brute: Mapped[str] = mapped_column(Text, nullable=False, comment="Désignation originale")
    designation_clean: Mapped[str] = mapped_column(String(200), nullable=False, comment="Désignation normalisée (clé)")
    provenance: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="Pays d'origine principal")

    # Lien vers dim_produit (synchronisé)
    dim_produit_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="FK vers dwh.dim_produit")

    # Agrégats quantités
    quantite_colis_totale: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0, comment="Quantité totale en colis")
    quantite_pieces_totale: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True, comment="Quantité totale en pièces")
    nb_achats: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, comment="Nombre d'achats")

    # Montants
    montant_total_ht: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, comment="Montant total HT")
    montant_total_tva: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True, comment="Montant total TVA")
    montant_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, comment="Montant total TTC")

    # Prix
    prix_moyen_ht: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix moyen HT")
    prix_min_ht: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix minimum HT")
    prix_max_ht: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0, comment="Prix maximum HT")

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


# Codes TVA TAIYAT
TAIYAT_TVA_CODES = {
    "1": 5.5,   # TVA réduite (alimentaire)
    "2": 20.0,  # TVA normale
}


# Catégories TAIYAT basées sur provenance/type
TAIYAT_CATEGORIES = {
    "POISSON": ["CHINCHARD", "MORUE", "STOCKFISH", "TILAPIA", "MAQUEREAU", "SARDINE", "PILCHARD"],
    "VIANDE": ["BOEUF", "POULET", "ZWAN"],
    "LEGUMES": ["MANIOC", "PLANTAIN", "IGNAME", "YAM", "GINGEMBRE", "FOUMBOA"],
    "CEREALES": ["SEMOULE", "FARINE", "MAIS", "RIZ", "MIL"],
    "LEGUMINEUSES": ["HARICOT", "LENTILLE", "POIS"],
    "BOISSONS": ["THE", "CAFE", "BISSAP"],
    "CONDIMENTS": ["MAGGI", "AROME", "GLUTAMATE", "BOUILLON", "EPICE"],
    "CONSERVES": ["CONSERVE", "TOMATE", "CONCENTRE"],
    "LAITIERS": ["LAIT", "NIDO", "BEURRE"],
    "SNACKS": ["CHIPS", "CRACKERS"],
}


def categoriser_produit(designation: str) -> tuple:
    """
    Catégorise un produit TAIYAT basé sur sa désignation.

    Returns:
        tuple: (famille, categorie, sous_categorie)
    """
    designation_upper = designation.upper()

    for categorie, mots_cles in TAIYAT_CATEGORIES.items():
        for mot in mots_cles:
            if mot in designation_upper:
                return ("EPICERIE", categorie.capitalize(), None)

    return ("EPICERIE", "Divers", None)
