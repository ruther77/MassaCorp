"""
Model RestaurantEpicerieLink - Liaison ingredient-produit epicerie.
"""
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Numeric, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.restaurant.ingredient import RestaurantIngredient


class RestaurantEpicerieLink(Base, TimestampMixin, TenantMixin):
    """
    Liaison entre un ingredient restaurant et un produit epicerie (DWH).

    Permet de synchroniser les prix et les stocks entre les deux domaines.

    Attributes:
        ingredient_id: FK vers l'ingredient restaurant
        produit_id: ID du produit dans le DWH (dim_produit)
        fournisseur: Code du fournisseur (METRO, TAIYAT, etc.)
        ratio: Facteur de conversion (ex: 1 kg ingredient = 1000g produit)
        is_primary: Est-ce le lien principal pour cet ingredient
    """
    __tablename__ = "restaurant_epicerie_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_ingredients.id", ondelete="CASCADE"),
        nullable=False
    )
    produit_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fournisseur: Mapped[str] = mapped_column(String(50), default="METRO", nullable=False)
    ratio: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("1.0"), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relations
    ingredient: Mapped["RestaurantIngredient"] = relationship(back_populates="epicerie_links")

    @property
    def has_valid_ratio(self) -> bool:
        """Le ratio est-il valide (> 0)."""
        return self.ratio > 0

    def convert_quantity(self, ingredient_qty: Decimal) -> Decimal:
        """
        Convertit une quantite ingredient en quantite produit.

        Args:
            ingredient_qty: Quantite dans l'unite ingredient

        Returns:
            Quantite equivalente dans l'unite produit
        """
        return ingredient_qty * self.ratio

    def __repr__(self) -> str:
        return f"<RestaurantEpicerieLink(ingredient_id={self.ingredient_id}, produit_id={self.produit_id}, ratio={self.ratio})>"
