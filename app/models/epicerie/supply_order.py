"""
Models SupplyOrder et SupplyOrderLine - Commandes fournisseurs.
"""
import enum
from datetime import date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    BigInteger, Text, Date, Numeric, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.finance.vendor import FinanceVendor
    from app.models.metro import DimProduit


class SupplyOrderStatus(str, enum.Enum):
    """Statuts possibles d'une commande fournisseur."""
    EN_ATTENTE = "en_attente"
    CONFIRMEE = "confirmee"
    EXPEDIEE = "expediee"
    LIVREE = "livree"
    ANNULEE = "annulee"


class SupplyOrder(Base, TimestampMixin, TenantMixin):
    """
    Commande fournisseur.

    Represente une commande passee aupres d'un fournisseur (ex: METRO, Promocash).
    Contient les informations de commande et de livraison.

    Attributes:
        vendor_id: FK vers le fournisseur (finance_vendors)
        reference: Reference interne de la commande
        date_commande: Date de passage de la commande
        date_livraison_prevue: Date de livraison prevue
        date_livraison_reelle: Date de livraison effective
        statut: Statut actuel de la commande
        montant_ht: Montant total HT en centimes
        montant_tva: Montant TVA en centimes
        notes: Notes/commentaires sur la commande
        created_by: ID de l'utilisateur ayant cree la commande
    """
    __tablename__ = "supply_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    vendor_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("finance_vendors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    date_commande: Mapped[date] = mapped_column(Date, nullable=False)
    date_livraison_prevue: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_livraison_reelle: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    statut: Mapped[SupplyOrderStatus] = mapped_column(
        SQLEnum(
            SupplyOrderStatus,
            name="supply_order_status",
            create_type=False,
            values_callable=lambda x: [e.value for e in x]
        ),
        default=SupplyOrderStatus.EN_ATTENTE,
        nullable=False
    )

    # Montants en centimes
    montant_ht: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    montant_tva: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relations
    vendor: Mapped["FinanceVendor"] = relationship("FinanceVendor")
    lines: Mapped[List["SupplyOrderLine"]] = relationship(
        "SupplyOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="SupplyOrderLine.id"
    )

    __table_args__ = (
        Index("ix_supply_orders_tenant", "tenant_id"),
        Index("ix_supply_orders_vendor", "vendor_id"),
        Index("ix_supply_orders_statut", "statut"),
        Index("ix_supply_orders_date_commande", "date_commande"),
        Index("ix_supply_orders_date_livraison", "date_livraison_prevue"),
    )

    def __repr__(self) -> str:
        return f"<SupplyOrder(id={self.id}, vendor_id={self.vendor_id}, statut={self.statut.value})>"

    @property
    def nb_lignes(self) -> int:
        """Nombre de lignes dans la commande."""
        return len(self.lines) if self.lines else 0

    @property
    def nb_produits(self) -> int:
        """Nombre total de produits (somme des quantites)."""
        if not self.lines:
            return 0
        return sum(int(line.quantity) for line in self.lines)

    @property
    def montant_ttc(self) -> int:
        """Montant TTC en centimes."""
        return self.montant_ht + self.montant_tva

    @property
    def is_pending(self) -> bool:
        """La commande est-elle en attente."""
        return self.statut == SupplyOrderStatus.EN_ATTENTE

    @property
    def is_delivered(self) -> bool:
        """La commande est-elle livree."""
        return self.statut == SupplyOrderStatus.LIVREE

    @property
    def is_cancelled(self) -> bool:
        """La commande est-elle annulee."""
        return self.statut == SupplyOrderStatus.ANNULEE

    @property
    def is_late(self) -> bool:
        """La livraison est-elle en retard."""
        if self.statut in (SupplyOrderStatus.LIVREE, SupplyOrderStatus.ANNULEE):
            return False
        if not self.date_livraison_prevue:
            return False
        return date.today() > self.date_livraison_prevue

    def recalculate_totals(self) -> None:
        """Recalcule les totaux a partir des lignes."""
        if not self.lines:
            self.montant_ht = 0
            self.montant_tva = 0
            return

        self.montant_ht = sum(line.montant_ligne for line in self.lines)
        # TVA simplifiee a 20% - a ameliorer si besoin de taux differents
        self.montant_tva = int(self.montant_ht * Decimal("0.20"))


class SupplyOrderLine(Base, TimestampMixin):
    """
    Ligne de commande fournisseur.

    Represente un produit commande avec sa quantite et son prix.

    Attributes:
        order_id: FK vers la commande
        produit_id: FK vers le produit (dim_produit - catalogue METRO)
        designation: Designation du produit (copiee au moment de la commande)
        quantity: Quantite commandee
        prix_unitaire: Prix unitaire en centimes
        received_quantity: Quantite effectivement recue
    """
    __tablename__ = "supply_order_lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    order_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("supply_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    produit_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("dwh.dim_produit.id", ondelete="SET NULL"),
        nullable=True
    )

    designation: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    prix_unitaire: Mapped[int] = mapped_column(BigInteger, nullable=False)  # centimes

    received_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 3),
        nullable=True
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    order: Mapped["SupplyOrder"] = relationship("SupplyOrder", back_populates="lines")
    produit: Mapped[Optional["DimProduit"]] = relationship("DimProduit")

    __table_args__ = (
        Index("ix_supply_order_lines_order", "order_id"),
        Index("ix_supply_order_lines_produit", "produit_id"),
    )

    def __repr__(self) -> str:
        return f"<SupplyOrderLine(id={self.id}, order_id={self.order_id}, qty={self.quantity})>"

    @property
    def montant_ligne(self) -> int:
        """Montant de la ligne en centimes."""
        return int(self.quantity * self.prix_unitaire)

    @property
    def is_fully_received(self) -> bool:
        """La ligne a-t-elle ete entierement recue."""
        if self.received_quantity is None:
            return False
        return self.received_quantity >= self.quantity

    @property
    def is_partially_received(self) -> bool:
        """La ligne a-t-elle ete partiellement recue."""
        if self.received_quantity is None:
            return False
        return Decimal(0) < self.received_quantity < self.quantity
