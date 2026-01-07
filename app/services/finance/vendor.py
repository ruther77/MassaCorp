"""
Service pour la gestion des fournisseurs (vendors).
"""
import logging
from typing import List, Optional

from app.models.finance.vendor import FinanceVendor
from app.repositories.finance.vendor import FinanceVendorRepository
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class VendorNotFoundError(AppException):
    """Fournisseur non trouve."""
    status_code = 404
    error_code = "VENDOR_NOT_FOUND"

    def __init__(self, vendor_id: int):
        super().__init__(message=f"Fournisseur {vendor_id} non trouve")
        self.vendor_id = vendor_id


class VendorCodeExistsError(AppException):
    """Code fournisseur deja utilise."""
    status_code = 409
    error_code = "VENDOR_CODE_EXISTS"

    def __init__(self, code: str):
        super().__init__(message=f"Le code '{code}' existe deja")
        self.code = code


class FinanceVendorService:
    """
    Service de gestion des fournisseurs.
    """

    def __init__(self, vendor_repository: FinanceVendorRepository):
        self.vendor_repository = vendor_repository

    def create_vendor(
        self,
        entity_id: int,
        name: str,
        code: Optional[str] = None,
        siret: Optional[str] = None,
        tva_intra: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        address: Optional[str] = None,
        postal_code: Optional[str] = None,
        city: Optional[str] = None,
        country: str = "FR",
        iban: Optional[str] = None,
        bic: Optional[str] = None,
        payment_terms_days: int = 30,
        notes: Optional[str] = None,
    ) -> FinanceVendor:
        """
        Cree un nouveau fournisseur.

        Args:
            entity_id: ID de l'entite financiere
            name: Nom du fournisseur
            code: Code unique optionnel
            ... autres champs

        Returns:
            Le fournisseur cree

        Raises:
            VendorCodeExistsError: Si le code existe deja
        """
        # Verifier unicite du code si fourni
        if code:
            existing = self.vendor_repository.get_by_code(entity_id, code)
            if existing:
                raise VendorCodeExistsError(code)

        vendor = self.vendor_repository.create({
            "entity_id": entity_id,
            "name": name,
            "code": code.upper() if code else None,
            "siret": siret,
            "tva_intra": tva_intra,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "address": address,
            "postal_code": postal_code,
            "city": city,
            "country": country,
            "iban": iban,
            "bic": bic,
            "payment_terms_days": payment_terms_days,
            "notes": notes,
            "is_active": True,
        })

        logger.info(f"Fournisseur cree: {vendor.id} - {vendor.name}")
        return vendor

    def get_vendor(self, vendor_id: int) -> FinanceVendor:
        """
        Recupere un fournisseur par ID.

        Raises:
            VendorNotFoundError: Si le fournisseur n'existe pas
        """
        vendor = self.vendor_repository.get(vendor_id)
        if not vendor:
            raise VendorNotFoundError(vendor_id)
        return vendor

    def get_vendors_by_entity(self, entity_id: int) -> List[FinanceVendor]:
        """Recupere tous les fournisseurs d'une entite."""
        return self.vendor_repository.get_by_entity(entity_id)

    def get_active_vendors(self, entity_id: int) -> List[FinanceVendor]:
        """Recupere les fournisseurs actifs d'une entite."""
        return self.vendor_repository.get_active_by_entity(entity_id)

    def search_vendors(self, entity_id: int, name: str) -> List[FinanceVendor]:
        """Recherche des fournisseurs par nom."""
        return self.vendor_repository.search_by_name(entity_id, name)

    def update_vendor(
        self,
        vendor_id: int,
        **data
    ) -> FinanceVendor:
        """
        Met a jour un fournisseur.

        Raises:
            VendorNotFoundError: Si le fournisseur n'existe pas
            VendorCodeExistsError: Si le nouveau code existe deja
        """
        vendor = self.get_vendor(vendor_id)

        # Verifier unicite du code si modifie
        if "code" in data and data["code"] and data["code"] != vendor.code:
            existing = self.vendor_repository.get_by_code(vendor.entity_id, data["code"])
            if existing:
                raise VendorCodeExistsError(data["code"])
            data["code"] = data["code"].upper()

        updated = self.vendor_repository.update(vendor_id, data)
        logger.info(f"Fournisseur mis a jour: {vendor_id}")
        return updated

    def deactivate_vendor(self, vendor_id: int) -> FinanceVendor:
        """Desactive un fournisseur."""
        vendor = self.get_vendor(vendor_id)
        return self.vendor_repository.update(vendor_id, {"is_active": False})

    def activate_vendor(self, vendor_id: int) -> FinanceVendor:
        """Reactive un fournisseur."""
        vendor = self.get_vendor(vendor_id)
        return self.vendor_repository.update(vendor_id, {"is_active": True})

    def delete_vendor(self, vendor_id: int) -> bool:
        """
        Supprime un fournisseur.

        Note: La suppression echouera s'il y a des factures associees.
        """
        vendor = self.get_vendor(vendor_id)
        return self.vendor_repository.delete(vendor_id)
