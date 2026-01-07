"""
Schemas Pydantic pour le domaine Epicerie.
Commandes fournisseurs et lignes de commande.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator

from app.models.epicerie import SupplyOrderStatus
from app.schemas.base import BaseSchema, TimestampSchema


# === Schemas SupplyOrderLine ===

class SupplyOrderLineBase(BaseSchema):
    """Base pour les lignes de commande."""
    produit_id: Optional[int] = None
    designation: str = Field(..., min_length=1, max_length=500)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    prix_unitaire: int = Field(..., ge=0, description="Prix en centimes")
    notes: Optional[str] = None


class SupplyOrderLineCreate(SupplyOrderLineBase):
    """Creation d'une ligne de commande."""
    pass


class SupplyOrderLineUpdate(BaseSchema):
    """Mise a jour d'une ligne de commande."""
    produit_id: Optional[int] = None
    designation: Optional[str] = Field(None, min_length=1, max_length=500)
    quantity: Optional[Decimal] = Field(None, gt=0)
    prix_unitaire: Optional[int] = Field(None, ge=0)
    received_quantity: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class SupplyOrderLineRead(SupplyOrderLineBase, TimestampSchema):
    """Lecture d'une ligne de commande."""
    id: int
    order_id: int
    received_quantity: Optional[Decimal] = None
    montant_ligne: int = Field(description="Montant total en centimes")
    is_fully_received: bool
    is_partially_received: bool


# === Schemas SupplyOrder ===

class SupplyOrderBase(BaseSchema):
    """Base pour les commandes fournisseurs."""
    vendor_id: int
    reference: Optional[str] = Field(None, max_length=100)
    date_commande: date
    date_livraison_prevue: Optional[date] = None
    notes: Optional[str] = None


class SupplyOrderCreate(SupplyOrderBase):
    """Creation d'une commande fournisseur."""
    lines: List[SupplyOrderLineCreate] = Field(default_factory=list)

    @field_validator('date_commande')
    @classmethod
    def date_commande_not_future(cls, v: date) -> date:
        """La date de commande ne peut pas etre dans le futur."""
        if v > date.today():
            raise ValueError("La date de commande ne peut pas etre dans le futur")
        return v


class SupplyOrderUpdate(BaseSchema):
    """Mise a jour d'une commande fournisseur."""
    reference: Optional[str] = Field(None, max_length=100)
    date_livraison_prevue: Optional[date] = None
    date_livraison_reelle: Optional[date] = None
    statut: Optional[SupplyOrderStatus] = None
    notes: Optional[str] = None


class VendorSummary(BaseSchema):
    """Resume d'un fournisseur pour affichage."""
    id: int
    name: str
    code: Optional[str] = None


class SupplyOrderRead(SupplyOrderBase, TimestampSchema):
    """Lecture d'une commande fournisseur."""
    id: int
    tenant_id: int
    statut: SupplyOrderStatus
    date_livraison_reelle: Optional[date] = None
    montant_ht: int = Field(description="Montant HT en centimes")
    montant_tva: int = Field(description="Montant TVA en centimes")
    montant_ttc: int = Field(description="Montant TTC en centimes")
    nb_lignes: int
    nb_produits: int
    created_by: Optional[int] = None
    is_pending: bool
    is_delivered: bool
    is_cancelled: bool
    is_late: bool
    vendor: Optional[VendorSummary] = None


class SupplyOrderDetail(SupplyOrderRead):
    """Detail complet d'une commande avec ses lignes."""
    lines: List[SupplyOrderLineRead] = []


class SupplyOrderStats(BaseSchema):
    """Statistiques des commandes."""
    total_commandes: int
    total_montant_ht: int
    par_statut: dict


# === Schemas pour actions ===

class ConfirmOrderRequest(BaseSchema):
    """Confirmer une commande."""
    date_livraison_prevue: Optional[date] = None


class ReceiveOrderRequest(BaseSchema):
    """Recevoir une commande."""
    date_livraison_reelle: date = Field(default_factory=date.today)
    lines: Optional[List[dict]] = Field(
        default=None,
        description="Liste des {line_id, received_quantity} pour reception partielle"
    )


class CancelOrderRequest(BaseSchema):
    """Annuler une commande."""
    raison: Optional[str] = None
