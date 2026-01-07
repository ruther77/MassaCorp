"""
Service pour la gestion des charges fixes restaurant.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict

from app.models.restaurant.charge import (
    RestaurantCharge,
    RestaurantChargeType,
    RestaurantChargeFrequency,
)
from app.repositories.restaurant.charge import RestaurantChargeRepository


class ChargeNotFoundError(Exception):
    """Charge non trouvee."""
    def __init__(self, charge_id: int):
        self.charge_id = charge_id
        super().__init__(f"Charge {charge_id} non trouvee")


class InvalidChargeError(Exception):
    """Donnees de charge invalides."""
    pass


class RestaurantChargeService:
    """
    Service pour la gestion des charges fixes.

    Responsabilites:
    - CRUD charges
    - Calcul des charges mensuelles
    - Ventilation par type
    """

    def __init__(self, charge_repo: RestaurantChargeRepository):
        self.charge_repo = charge_repo

    def create_charge(
        self,
        name: str,
        charge_type: RestaurantChargeType,
        montant: int,
        frequency: RestaurantChargeFrequency = RestaurantChargeFrequency.MENSUEL,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> RestaurantCharge:
        """
        Cree une nouvelle charge.

        Args:
            name: Nom de la charge
            charge_type: Type de charge
            montant: Montant en centimes
            frequency: Frequence de paiement
            date_debut: Date de debut (defaut: aujourd'hui)
            date_fin: Date de fin (optionnel)
            notes: Notes

        Returns:
            Charge creee
        """
        if montant <= 0:
            raise InvalidChargeError("Le montant doit etre positif")

        if date_debut is None:
            date_debut = date.today()

        if date_fin is not None and date_fin < date_debut:
            raise InvalidChargeError("La date de fin doit etre apres la date de debut")

        charge = self.charge_repo.create({
            "tenant_id": self.charge_repo.tenant_id,
            "name": name,
            "type": charge_type,
            "montant": montant,
            "frequency": frequency,
            "date_debut": date_debut,
            "date_fin": date_fin,
            "notes": notes,
            "is_active": True,
        })

        return charge

    def get_charge(self, charge_id: int) -> RestaurantCharge:
        """Recupere une charge par ID."""
        charge = self.charge_repo.get(charge_id)
        if not charge:
            raise ChargeNotFoundError(charge_id)
        return charge

    def get_active_charges(self) -> List[RestaurantCharge]:
        """Recupere toutes les charges actives."""
        return self.charge_repo.get_active()

    def get_current_charges(self) -> List[RestaurantCharge]:
        """Recupere les charges en cours de validite."""
        return self.charge_repo.get_current()

    def get_charges_by_type(
        self,
        charge_type: RestaurantChargeType,
        active_only: bool = True
    ) -> List[RestaurantCharge]:
        """Recupere les charges par type."""
        return self.charge_repo.get_by_type(charge_type, active_only)

    def get_charges_by_frequency(
        self,
        frequency: RestaurantChargeFrequency
    ) -> List[RestaurantCharge]:
        """Recupere les charges par frequence."""
        return self.charge_repo.get_by_frequency(frequency)

    def update_charge(
        self,
        charge_id: int,
        name: Optional[str] = None,
        charge_type: Optional[RestaurantChargeType] = None,
        montant: Optional[int] = None,
        frequency: Optional[RestaurantChargeFrequency] = None,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> RestaurantCharge:
        """Met a jour une charge."""
        charge = self.get_charge(charge_id)

        if name is not None:
            charge.name = name
        if charge_type is not None:
            charge.type = charge_type
        if montant is not None:
            if montant <= 0:
                raise InvalidChargeError("Le montant doit etre positif")
            charge.montant = montant
        if frequency is not None:
            charge.frequency = frequency
        if date_debut is not None:
            charge.date_debut = date_debut
        if date_fin is not None:
            if charge.date_debut and date_fin < charge.date_debut:
                raise InvalidChargeError(
                    "La date de fin doit etre apres la date de debut"
                )
            charge.date_fin = date_fin
        if notes is not None:
            charge.notes = notes

        self.charge_repo.session.flush()
        return charge

    def deactivate_charge(self, charge_id: int) -> RestaurantCharge:
        """Desactive une charge."""
        charge = self.get_charge(charge_id)
        charge.is_active = False
        self.charge_repo.session.flush()
        return charge

    def end_charge(self, charge_id: int, end_date: Optional[date] = None) -> RestaurantCharge:
        """
        Termine une charge a une date donnee.

        Args:
            charge_id: ID de la charge
            end_date: Date de fin (defaut: aujourd'hui)

        Returns:
            Charge mise a jour
        """
        charge = self.get_charge(charge_id)
        charge.date_fin = end_date or date.today()
        self.charge_repo.session.flush()
        return charge

    def get_total_monthly_charges(self) -> int:
        """
        Calcule le total des charges mensuelles en centimes.

        Returns:
            Total mensualise de toutes les charges actives
        """
        return self.charge_repo.get_total_mensuel()

    def get_charges_summary(self) -> Dict:
        """
        Resume des charges par type.

        Returns:
            Dictionnaire avec totaux par type et total general
        """
        by_type = self.charge_repo.get_summary_by_type()
        total = sum(by_type.values())

        return {
            "by_type": by_type,
            "total_mensuel": total,
            "total_annuel": total * 12,
        }

    def get_charges_breakdown(self) -> List[Dict]:
        """
        Ventilation detaillee des charges.

        Returns:
            Liste des charges avec leur contribution mensuelle
        """
        charges = self.get_current_charges()
        breakdown = []

        for charge in charges:
            breakdown.append({
                "id": charge.id,
                "name": charge.name,
                "type": charge.type.value,
                "frequency": charge.frequency.value,
                "montant_brut": charge.montant,
                "montant_mensuel": charge.montant_mensuel,
            })

        return sorted(breakdown, key=lambda x: x["montant_mensuel"], reverse=True)

    def calculate_daily_charge(self) -> int:
        """
        Calcule la charge fixe journaliere en centimes.
        Base: 30 jours par mois.
        """
        monthly = self.get_total_monthly_charges()
        return monthly // 30

    def project_annual_charges(self) -> Dict:
        """
        Projection annuelle des charges.

        Returns:
            Dictionnaire avec projections par type
        """
        by_type = self.charge_repo.get_summary_by_type()

        projection = {}
        for charge_type, monthly in by_type.items():
            projection[charge_type] = {
                "mensuel": monthly,
                "annuel": monthly * 12,
            }

        total_monthly = sum(by_type.values())

        return {
            "by_type": projection,
            "total_mensuel": total_monthly,
            "total_annuel": total_monthly * 12,
        }
