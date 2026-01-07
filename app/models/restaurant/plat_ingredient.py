"""
Model RestaurantPlatIngredient - Composition des plats.
"""
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.restaurant.plat import RestaurantPlat
    from app.models.restaurant.ingredient import RestaurantIngredient


class RestaurantPlatIngredient(Base, TimestampMixin):
    """
    Liaison entre un plat et ses ingredients (fiche technique).

    Attributes:
        plat_id: FK vers le plat
        ingredient_id: FK vers l'ingredient
        quantite: Quantite utilisee dans le plat
        notes: Notes specifiques (ex: "couper en des")
    """
    __tablename__ = "restaurant_plat_ingredients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_plats.id", ondelete="CASCADE"),
        nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="CASCADE"),
        nullable=False
    )
    quantite: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    plat: Mapped["RestaurantPlat"] = relationship(back_populates="ingredients")
    ingredient: Mapped["RestaurantIngredient"] = relationship(back_populates="plat_ingredients")

    @property
    def cout_ligne(self) -> int:
        """Cout de cette ligne en centimes (quantite * prix_unitaire)."""
        if not self.ingredient:
            return 0
        return int(self.quantite * self.ingredient.prix_unitaire)

    @property
    def cout_ligne_decimal(self) -> Decimal:
        """Cout de cette ligne en euros."""
        return Decimal(self.cout_ligne) / 100

    @property
    def ingredient_name(self) -> str:
        """Nom de l'ingredient."""
        return self.ingredient.name if self.ingredient else ""

    @property
    def ingredient_unit(self) -> str:
        """Unite de l'ingredient."""
        return self.ingredient.unit_label if self.ingredient else ""

    def __repr__(self) -> str:
        return f"<RestaurantPlatIngredient(plat_id={self.plat_id}, ingredient_id={self.ingredient_id}, qty={self.quantite})>"
