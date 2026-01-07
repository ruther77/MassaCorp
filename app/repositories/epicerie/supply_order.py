"""
Repositories pour SupplyOrder et SupplyOrderLine.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import joinedload

from app.models.epicerie import SupplyOrder, SupplyOrderLine, SupplyOrderStatus
from app.repositories.base import TenantAwareBaseRepository, BaseRepository, PaginatedResult


class SupplyOrderRepository(TenantAwareBaseRepository[SupplyOrder]):
    """
    Repository pour les commandes fournisseurs.
    Isolation multi-tenant obligatoire.
    """
    model = SupplyOrder

    def get_with_lines(self, order_id: int) -> Optional[SupplyOrder]:
        """Recupere une commande avec ses lignes."""
        return (
            self._tenant_query()
            .options(joinedload(SupplyOrder.lines))
            .options(joinedload(SupplyOrder.vendor))
            .filter(SupplyOrder.id == order_id)
            .first()
        )

    def get_by_vendor(
        self,
        vendor_id: int,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[SupplyOrder]:
        """Recupere les commandes d'un fournisseur."""
        query = (
            self._tenant_query()
            .filter(SupplyOrder.vendor_id == vendor_id)
            .order_by(SupplyOrder.date_commande.desc())
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_by_status(
        self,
        statut: SupplyOrderStatus,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[SupplyOrder]:
        """Recupere les commandes par statut."""
        query = (
            self._tenant_query()
            .filter(SupplyOrder.statut == statut)
            .order_by(SupplyOrder.date_commande.desc())
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_pending(self, page: int = 1, page_size: int = 20) -> PaginatedResult[SupplyOrder]:
        """Recupere les commandes en attente."""
        return self.get_by_status(SupplyOrderStatus.EN_ATTENTE, page, page_size)

    def get_late_deliveries(self) -> List[SupplyOrder]:
        """Recupere les commandes en retard de livraison."""
        today = date.today()
        return (
            self._tenant_query()
            .filter(
                and_(
                    SupplyOrder.statut.notin_([
                        SupplyOrderStatus.LIVREE,
                        SupplyOrderStatus.ANNULEE
                    ]),
                    SupplyOrder.date_livraison_prevue < today
                )
            )
            .order_by(SupplyOrder.date_livraison_prevue)
            .all()
        )

    def get_by_date_range(
        self,
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[SupplyOrder]:
        """Recupere les commandes dans une plage de dates."""
        query = (
            self._tenant_query()
            .filter(
                and_(
                    SupplyOrder.date_commande >= start_date,
                    SupplyOrder.date_commande <= end_date
                )
            )
            .order_by(SupplyOrder.date_commande.desc())
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_all_with_vendor(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResult[SupplyOrder]:
        """Recupere toutes les commandes avec les infos fournisseur."""
        query = (
            self._tenant_query()
            .options(joinedload(SupplyOrder.vendor))
            .order_by(SupplyOrder.date_commande.desc())
        )
        return self.paginate(page=page, page_size=page_size, query=query)

    def get_stats_by_vendor(self, vendor_id: int) -> dict:
        """Statistiques des commandes pour un fournisseur."""
        query = self._tenant_query().filter(SupplyOrder.vendor_id == vendor_id)

        total = query.count()
        total_ht = query.with_entities(func.sum(SupplyOrder.montant_ht)).scalar() or 0

        by_status = {}
        for status in SupplyOrderStatus:
            count = query.filter(SupplyOrder.statut == status).count()
            by_status[status.value] = count

        return {
            "total_commandes": total,
            "total_montant_ht": total_ht,
            "par_statut": by_status
        }


class SupplyOrderLineRepository(BaseRepository[SupplyOrderLine]):
    """
    Repository pour les lignes de commande.
    Pas de tenant direct - isolation via order_id.
    """
    model = SupplyOrderLine

    def get_by_order(self, order_id: int) -> List[SupplyOrderLine]:
        """Recupere toutes les lignes d'une commande."""
        return (
            self.session.query(SupplyOrderLine)
            .filter(SupplyOrderLine.order_id == order_id)
            .order_by(SupplyOrderLine.id)
            .all()
        )

    def get_by_produit(self, produit_id: int) -> List[SupplyOrderLine]:
        """Recupere toutes les lignes pour un produit."""
        return (
            self.session.query(SupplyOrderLine)
            .filter(SupplyOrderLine.produit_id == produit_id)
            .order_by(SupplyOrderLine.id.desc())
            .all()
        )

    def get_unreceived(self, order_id: int) -> List[SupplyOrderLine]:
        """Recupere les lignes non recues d'une commande."""
        return (
            self.session.query(SupplyOrderLine)
            .filter(
                and_(
                    SupplyOrderLine.order_id == order_id,
                    SupplyOrderLine.received_quantity.is_(None)
                )
            )
            .all()
        )
