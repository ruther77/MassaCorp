"""
Model RestaurantStock - Stock des ingredients.
"""
import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.restaurant.ingredient import RestaurantIngredient


class RestaurantStockMovementType(str, enum.Enum):
    """Types de mouvements de stock."""
    ENTREE = "ENTREE"
    SORTIE = "SORTIE"
    AJUSTEMENT = "AJUSTEMENT"
    PERTE = "PERTE"
    TRANSFERT = "TRANSFERT"


class RestaurantStock(Base, TimestampMixin, TenantMixin):
    """
    Stock actuel d'un ingredient.

    Stocke la quantite actuelle et la date de derniere MAJ.
    Un seul enregistrement par ingredient.

    Attributes:
        ingredient_id: FK vers l'ingredient
        quantity: Quantite actuelle en stock
        last_inventory_date: Date du dernier inventaire
    """
    __tablename__ = "restaurant_stock"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0"), nullable=False)
    last_inventory_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relations
    ingredient: Mapped["RestaurantIngredient"] = relationship(back_populates="stock")
    movements: Mapped[List["RestaurantStockMovement"]] = relationship(
        back_populates="stock",
        cascade="all, delete-orphan"
    )

    @property
    def is_low(self) -> bool:
        """Le stock est-il bas (sous le seuil d'alerte)."""
        if not self.ingredient or not self.ingredient.seuil_alerte:
            return False
        return self.quantity < self.ingredient.seuil_alerte

    @property
    def is_empty(self) -> bool:
        """Le stock est-il vide."""
        return self.quantity <= 0

    @property
    def days_since_inventory(self) -> Optional[int]:
        """Nombre de jours depuis le dernier inventaire."""
        if not self.last_inventory_date:
            return None
        return (date.today() - self.last_inventory_date).days

    @property
    def needs_inventory(self) -> bool:
        """Un inventaire est-il necessaire (> 30 jours)."""
        days = self.days_since_inventory
        if days is None:
            return True
        return days > 30

    def __repr__(self) -> str:
        return f"<RestaurantStock(ingredient_id={self.ingredient_id}, qty={self.quantity})>"


class RestaurantStockMovement(Base, TimestampMixin):
    """
    Mouvement de stock (historique).

    Attributes:
        stock_id: FK vers le stock
        type: Type de mouvement (ENTREE, SORTIE, etc.)
        quantity: Quantite du mouvement (positive)
        date_mouvement: Date du mouvement
        reference: Reference (ex: num commande, num inventaire)
        notes: Notes explicatives
    """
    __tablename__ = "restaurant_stock_movements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_stock.id", ondelete="CASCADE"),
        nullable=False
    )
    type: Mapped[RestaurantStockMovementType] = mapped_column(nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    date_mouvement: Mapped[date] = mapped_column(Date, nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    stock: Mapped["RestaurantStock"] = relationship(back_populates="movements")

    @property
    def signed_quantity(self) -> Decimal:
        """Quantite signee (negative pour sorties/pertes)."""
        if self.type in (RestaurantStockMovementType.SORTIE, RestaurantStockMovementType.PERTE):
            return -self.quantity
        return self.quantity

    @property
    def is_positive(self) -> bool:
        """Est-ce un mouvement d'entree."""
        return self.type == RestaurantStockMovementType.ENTREE

    def __repr__(self) -> str:
        return f"<RestaurantStockMovement(stock_id={self.stock_id}, type={self.type.value}, qty={self.quantity})>"
