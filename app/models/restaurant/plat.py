"""
Model RestaurantPlat - Plats et menus du restaurant.
"""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient
    from app.models.restaurant.consumption import RestaurantConsumption


class RestaurantPlatCategory(str, enum.Enum):
    """Categories de plats."""
    ENTREE = "ENTREE"
    PLAT = "PLAT"
    DESSERT = "DESSERT"
    BOISSON = "BOISSON"
    MENU = "MENU"
    ACCOMPAGNEMENT = "ACCOMPAGNEMENT"
    AUTRE = "AUTRE"
    # Nouvelles catégories
    VIANDES = "VIANDES"
    POISSONS = "POISSONS"
    BOUILLONS = "BOUILLONS"
    GRILLADES = "GRILLADES"
    PLATS_EN_SAUCE = "PLATS_EN_SAUCE"
    LEGUMES = "LEGUMES"
    TRADITIONNELS = "TRADITIONNELS"
    SOFT = "SOFT"


class RestaurantPlat(Base, TimestampMixin, TenantMixin):
    """
    Plat ou menu propose par le restaurant.

    Attributes:
        name: Nom du plat
        description: Description du plat
        category: Categorie (entree, plat, dessert, etc.)
        prix_vente: Prix de vente en centimes
        is_active: Plat actif a la carte
        is_menu: Est-ce un menu compose
        image_url: URL de l'image du plat
    """
    __tablename__ = "restaurant_plats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[RestaurantPlatCategory] = mapped_column(
        nullable=False,
        default=RestaurantPlatCategory.PLAT
    )
    prix_vente: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_menu: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    ingredients: Mapped[List["RestaurantPlatIngredient"]] = relationship(
        back_populates="plat",
        cascade="all, delete-orphan"
    )
    consumptions: Mapped[List["RestaurantConsumption"]] = relationship(
        back_populates="plat"
    )

    @property
    def prix_vente_decimal(self) -> Decimal:
        """Prix de vente en euros."""
        return Decimal(self.prix_vente) / 100

    @property
    def cout_total(self) -> int:
        """Cout total des ingredients en centimes."""
        if not self.ingredients:
            return 0
        return sum(pi.cout_ligne for pi in self.ingredients)

    @property
    def cout_total_decimal(self) -> Decimal:
        """Cout total en euros."""
        return Decimal(self.cout_total) / 100

    @property
    def marge_brute(self) -> int:
        """Marge brute en centimes (prix_vente - cout_total)."""
        return self.prix_vente - self.cout_total

    @property
    def marge_brute_decimal(self) -> Decimal:
        """Marge brute en euros."""
        return Decimal(self.marge_brute) / 100

    @property
    def food_cost_ratio(self) -> Decimal:
        """Ratio food cost (cout/prix_vente en %)."""
        if self.prix_vente == 0:
            return Decimal("0")
        return (Decimal(self.cout_total) / Decimal(self.prix_vente) * 100).quantize(Decimal("0.01"))

    @property
    def is_profitable(self) -> bool:
        """Le plat est-il rentable (food cost < 35%)."""
        return self.food_cost_ratio < Decimal("35")

    def __repr__(self) -> str:
        return f"<RestaurantPlat(id={self.id}, name='{self.name}', prix={self.prix_vente_decimal}€)>"
