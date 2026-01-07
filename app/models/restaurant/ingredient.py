"""
Model RestaurantIngredient - Ingredients pour la cuisine.
"""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Boolean, Numeric, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.restaurant.plat_ingredient import RestaurantPlatIngredient
    from app.models.restaurant.stock import RestaurantStock
    from app.models.restaurant.epicerie_link import RestaurantEpicerieLink


class RestaurantUnit(str, enum.Enum):
    """Unites de mesure pour ingredients."""
    UNITE = "U"
    KILOGRAMME = "KG"
    LITRE = "L"
    GRAMME = "G"
    CENTILITRE = "CL"
    MILLILITRE = "ML"


class RestaurantIngredientCategory(str, enum.Enum):
    """Categories d'ingredients."""
    VIANDE = "VIANDE"
    POISSON = "POISSON"
    LEGUME = "LEGUME"
    FRUIT = "FRUIT"
    PRODUIT_LAITIER = "PRODUIT_LAITIER"
    EPICERIE = "EPICERIE"
    BOISSON = "BOISSON"
    CONDIMENT = "CONDIMENT"
    AUTRE = "AUTRE"


class RestaurantIngredient(Base, TimestampMixin, TenantMixin):
    """
    Ingredient utilise dans les plats du restaurant.

    Attributes:
        name: Nom de l'ingredient
        unit: Unite de mesure (KG, L, U, etc.)
        category: Categorie de l'ingredient
        default_supplier_id: Fournisseur par defaut (FK finance_vendors)
        prix_unitaire: Prix unitaire en centimes
        seuil_alerte: Seuil d'alerte stock bas
        is_active: Ingredient actif ou archive
    """
    __tablename__ = "restaurant_ingredients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[RestaurantUnit] = mapped_column(
        Enum(
            RestaurantUnit,
            values_callable=lambda e: [m.value for m in e],
            name='restaurant_unit',
            create_type=False
        ),
        nullable=False
    )
    category: Mapped[RestaurantIngredientCategory] = mapped_column(
        Enum(
            RestaurantIngredientCategory,
            values_callable=lambda e: [m.value for m in e],
            name='restaurant_ingredient_category',
            create_type=False
        ),
        nullable=False,
        default=RestaurantIngredientCategory.AUTRE
    )
    default_supplier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("finance_vendors.id", ondelete="SET NULL"),
        nullable=True
    )
    prix_unitaire: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    seuil_alerte: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    plat_ingredients: Mapped[List["RestaurantPlatIngredient"]] = relationship(
        back_populates="ingredient",
        cascade="all, delete-orphan"
    )
    stock: Mapped[Optional["RestaurantStock"]] = relationship(
        back_populates="ingredient",
        uselist=False
    )
    epicerie_links: Mapped[List["RestaurantEpicerieLink"]] = relationship(
        back_populates="ingredient",
        cascade="all, delete-orphan"
    )

    @property
    def prix_unitaire_decimal(self) -> Decimal:
        """Prix unitaire en euros."""
        return Decimal(self.prix_unitaire) / 100

    @property
    def unit_label(self) -> str:
        """Label lisible de l'unite."""
        labels = {
            RestaurantUnit.UNITE: "unité",
            RestaurantUnit.KILOGRAMME: "kg",
            RestaurantUnit.LITRE: "L",
            RestaurantUnit.GRAMME: "g",
            RestaurantUnit.CENTILITRE: "cL",
            RestaurantUnit.MILLILITRE: "mL",
        }
        return labels.get(self.unit, str(self.unit.value))

    def __repr__(self) -> str:
        return f"<RestaurantIngredient(id={self.id}, name='{self.name}', unit={self.unit.value})>"
