"""
Model RestaurantCharge - Charges fixes du restaurant.
"""
import enum
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Text, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, TenantMixin


class RestaurantChargeType(str, enum.Enum):
    """Types de charges."""
    LOYER = "LOYER"
    SALAIRES = "SALAIRES"
    ELECTRICITE = "ELECTRICITE"
    EAU = "EAU"
    GAZ = "GAZ"
    ASSURANCE = "ASSURANCE"
    ENTRETIEN = "ENTRETIEN"
    MARKETING = "MARKETING"
    AUTRES = "AUTRES"


class RestaurantChargeFrequency(str, enum.Enum):
    """Frequence des charges."""
    MENSUEL = "MENSUEL"
    TRIMESTRIEL = "TRIMESTRIEL"
    ANNUEL = "ANNUEL"
    PONCTUEL = "PONCTUEL"


class RestaurantCharge(Base, TimestampMixin, TenantMixin):
    """
    Charge fixe du restaurant.

    Permet de suivre les charges fixes pour calculer
    le seuil de rentabilite.

    Attributes:
        name: Nom/description de la charge
        type: Type de charge (loyer, salaires, etc.)
        montant: Montant en centimes
        frequency: Frequence (mensuel, annuel, etc.)
        date_debut: Date de debut de validite
        date_fin: Date de fin de validite (optionnel)
        is_active: Charge active
    """
    __tablename__ = "restaurant_charges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[RestaurantChargeType] = mapped_column(nullable=False)
    montant: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frequency: Mapped[RestaurantChargeFrequency] = mapped_column(
        nullable=False,
        default=RestaurantChargeFrequency.MENSUEL
    )
    date_debut: Mapped[date] = mapped_column(Date, nullable=False)
    date_fin: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @property
    def montant_decimal(self) -> Decimal:
        """Montant en euros."""
        return Decimal(self.montant) / 100

    @property
    def montant_mensuel(self) -> int:
        """Montant ramene au mois en centimes."""
        if self.frequency == RestaurantChargeFrequency.MENSUEL:
            return self.montant
        elif self.frequency == RestaurantChargeFrequency.TRIMESTRIEL:
            return self.montant // 3
        elif self.frequency == RestaurantChargeFrequency.ANNUEL:
            return self.montant // 12
        else:  # PONCTUEL
            return self.montant

    @property
    def montant_mensuel_decimal(self) -> Decimal:
        """Montant mensuel en euros."""
        return Decimal(self.montant_mensuel) / 100

    @property
    def is_current(self) -> bool:
        """La charge est-elle en cours de validite."""
        today = date.today()
        if not self.is_active:
            return False
        if self.date_debut > today:
            return False
        if self.date_fin and self.date_fin < today:
            return False
        return True

    def __repr__(self) -> str:
        return f"<RestaurantCharge(id={self.id}, name='{self.name}', montant={self.montant_decimal}€/{self.frequency.value})>"
