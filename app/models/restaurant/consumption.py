"""
Model RestaurantConsumption - Consommations de plats.
"""
import enum
from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Text, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql

from app.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.restaurant.plat import RestaurantPlat


class RestaurantConsumptionType(str, enum.Enum):
    """Type de consommation."""
    VENTE = "VENTE"
    PERTE = "PERTE"
    REPAS_STAFF = "REPAS_STAFF"
    OFFERT = "OFFERT"


class RestaurantConsumption(Base, TimestampMixin, TenantMixin):
    """
    Consommation d'un plat (vente, perte, repas staff, offert).

    Enregistre chaque consommation de plat pour le suivi
    des revenus, couts et stocks.

    Attributes:
        plat_id: FK vers le plat consomme
        type: Type de consommation (VENTE, PERTE, REPAS_STAFF, OFFERT)
        quantite: Nombre de portions
        prix_vente: Prix de vente en centimes (0 pour pertes/staff)
        cout: Cout unitaire au moment de la conso (en centimes)
        date: Date de la consommation
        notes: Notes (ex: raison de la perte)
    """
    __tablename__ = "restaurant_consumptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    plat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("restaurant_plats.id", ondelete="CASCADE"),
        nullable=False
    )
    type: Mapped[RestaurantConsumptionType] = mapped_column(
        postgresql.ENUM(
            RestaurantConsumptionType,
            name="restaurant_consumption_type",
            create_type=False
        ),
        nullable=False,
        default=RestaurantConsumptionType.VENTE
    )
    quantite: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    prix_vente: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cout: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relations
    plat: Mapped["RestaurantPlat"] = relationship(back_populates="consumptions")

    @property
    def total_cost(self) -> int:
        """Cout total de cette consommation en centimes."""
        return self.quantite * self.cout

    @property
    def total_revenue(self) -> int:
        """Revenu total en centimes."""
        return self.quantite * self.prix_vente

    @property
    def margin(self) -> int:
        """Marge en centimes."""
        return self.total_revenue - self.total_cost

    @property
    def plat_name(self) -> str:
        """Nom du plat consomme."""
        return self.plat.name if self.plat else ""

    def __repr__(self) -> str:
        return f"<RestaurantConsumption(plat_id={self.plat_id}, date={self.date}, qty={self.quantite}, type={self.type})>"
