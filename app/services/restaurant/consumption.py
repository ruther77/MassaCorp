"""
Service pour la gestion des consommations restaurant.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict

from app.models.restaurant.consumption import (
    RestaurantConsumption,
    RestaurantConsumptionType,
)
from app.repositories.restaurant.consumption import RestaurantConsumptionRepository
from app.services.restaurant.plat import RestaurantPlatService, PlatNotFoundError
from app.services.restaurant.stock import RestaurantStockService, InsufficientStockError


class InvalidConsumptionError(Exception):
    """Consommation invalide."""
    pass


class RestaurantConsumptionService:
    """
    Service pour la gestion des consommations.

    Responsabilites:
    - Enregistrement des ventes/pertes
    - Mise a jour du stock
    - Statistiques de consommation
    """

    def __init__(
        self,
        consumption_repo: RestaurantConsumptionRepository,
        plat_service: RestaurantPlatService,
        stock_service: RestaurantStockService,
    ):
        self.consumption_repo = consumption_repo
        self.plat_service = plat_service
        self.stock_service = stock_service

    def record_sale(
        self,
        plat_id: int,
        quantite: int = 1,
        prix_vente: Optional[int] = None,
        date_consumption: Optional[date] = None,
        notes: Optional[str] = None,
        decrement_stock: bool = True,
    ) -> RestaurantConsumption:
        """
        Enregistre une vente de plat.

        Args:
            plat_id: ID du plat vendu
            quantite: Nombre de portions vendues
            prix_vente: Prix de vente (si different du prix standard)
            date_consumption: Date de la vente (defaut: aujourd'hui)
            notes: Notes
            decrement_stock: Decrementer le stock des ingredients

        Returns:
            Consommation creee
        """
        if quantite <= 0:
            raise InvalidConsumptionError("La quantite doit etre positive")

        # Recuperer le plat avec ses ingredients
        plat = self.plat_service.get_plat_with_ingredients(plat_id)

        # Prix de vente
        actual_prix = prix_vente if prix_vente is not None else plat.prix_vente

        # Cout du plat
        cout = plat.cout_total

        # Date
        consumption_date = date_consumption or date.today()

        # Creer la consommation
        consumption = self.consumption_repo.create({
            "tenant_id": self.consumption_repo.tenant_id,
            "plat_id": plat_id,
            "type": RestaurantConsumptionType.VENTE,
            "quantite": quantite,
            "prix_vente": actual_prix,
            "cout": cout,
            "date": consumption_date,
            "notes": notes,
        })

        # Decrementer le stock
        if decrement_stock and plat.ingredients:
            for plat_ing in plat.ingredients:
                try:
                    # Quantite totale a retirer
                    qty_to_remove = plat_ing.quantite * quantite
                    self.stock_service.remove_stock(
                        ingredient_id=plat_ing.ingredient_id,
                        quantite=qty_to_remove,
                        reference=f"Vente plat #{plat_id}",
                        allow_negative=True,  # Permettre negatif pour ventes
                    )
                except Exception:
                    # Log mais continue (stock peut ne pas exister)
                    pass

        return consumption

    def record_loss(
        self,
        plat_id: int,
        quantite: int = 1,
        date_consumption: Optional[date] = None,
        notes: Optional[str] = None,
        decrement_stock: bool = True,
    ) -> RestaurantConsumption:
        """
        Enregistre une perte de plat.

        Args:
            plat_id: ID du plat perdu
            quantite: Nombre de portions perdues
            date_consumption: Date de la perte
            notes: Raison de la perte
            decrement_stock: Decrementer le stock

        Returns:
            Consommation creee
        """
        if quantite <= 0:
            raise InvalidConsumptionError("La quantite doit etre positive")

        plat = self.plat_service.get_plat_with_ingredients(plat_id)
        consumption_date = date_consumption or date.today()
        cout = plat.cout_total

        consumption = self.consumption_repo.create({
            "tenant_id": self.consumption_repo.tenant_id,
            "plat_id": plat_id,
            "type": RestaurantConsumptionType.PERTE,
            "quantite": quantite,
            "prix_vente": 0,  # Pas de vente
            "cout": cout,
            "date": consumption_date,
            "notes": notes,
        })

        # Decrementer le stock
        if decrement_stock and plat.ingredients:
            for plat_ing in plat.ingredients:
                try:
                    qty_to_remove = plat_ing.quantite * quantite
                    self.stock_service.record_loss(
                        ingredient_id=plat_ing.ingredient_id,
                        quantite=qty_to_remove,
                        notes=f"Perte plat #{plat_id}: {notes or 'Non specifie'}",
                    )
                except Exception:
                    pass

        return consumption

    def record_staff_meal(
        self,
        plat_id: int,
        quantite: int = 1,
        date_consumption: Optional[date] = None,
        notes: Optional[str] = None,
        decrement_stock: bool = True,
    ) -> RestaurantConsumption:
        """Enregistre un repas staff."""
        if quantite <= 0:
            raise InvalidConsumptionError("La quantite doit etre positive")

        plat = self.plat_service.get_plat_with_ingredients(plat_id)
        consumption_date = date_consumption or date.today()
        cout = plat.cout_total

        consumption = self.consumption_repo.create({
            "tenant_id": self.consumption_repo.tenant_id,
            "plat_id": plat_id,
            "type": RestaurantConsumptionType.REPAS_STAFF,
            "quantite": quantite,
            "prix_vente": 0,
            "cout": cout,
            "date": consumption_date,
            "notes": notes,
        })

        if decrement_stock and plat.ingredients:
            for plat_ing in plat.ingredients:
                try:
                    qty_to_remove = plat_ing.quantite * quantite
                    self.stock_service.remove_stock(
                        ingredient_id=plat_ing.ingredient_id,
                        quantite=qty_to_remove,
                        reference=f"Repas staff - plat #{plat_id}",
                        allow_negative=True,
                    )
                except Exception:
                    pass

        return consumption

    def record_offert(
        self,
        plat_id: int,
        quantite: int = 1,
        date_consumption: Optional[date] = None,
        notes: Optional[str] = None,
        decrement_stock: bool = True,
    ) -> RestaurantConsumption:
        """Enregistre un plat offert."""
        if quantite <= 0:
            raise InvalidConsumptionError("La quantite doit etre positive")

        plat = self.plat_service.get_plat_with_ingredients(plat_id)
        consumption_date = date_consumption or date.today()
        cout = plat.cout_total

        consumption = self.consumption_repo.create({
            "tenant_id": self.consumption_repo.tenant_id,
            "plat_id": plat_id,
            "type": RestaurantConsumptionType.OFFERT,
            "quantite": quantite,
            "prix_vente": 0,
            "cout": cout,
            "date": consumption_date,
            "notes": notes,
        })

        if decrement_stock and plat.ingredients:
            for plat_ing in plat.ingredients:
                try:
                    qty_to_remove = plat_ing.quantite * quantite
                    self.stock_service.remove_stock(
                        ingredient_id=plat_ing.ingredient_id,
                        quantite=qty_to_remove,
                        reference=f"Offert - plat #{plat_id}",
                        allow_negative=True,
                    )
                except Exception:
                    pass

        return consumption

    def get_consumptions_by_date(
        self,
        start_date: date,
        end_date: date
    ) -> List[RestaurantConsumption]:
        """Recupere les consommations pour une periode."""
        return self.consumption_repo.get_by_period(start_date, end_date)

    def get_consumptions_by_plat(
        self,
        plat_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[RestaurantConsumption]:
        """Recupere les consommations d'un plat."""
        return self.consumption_repo.get_by_plat(plat_id, start_date, end_date)

    def get_daily_summary(self, target_date: date) -> Dict:
        """
        Resume des consommations d'une journee.

        Returns:
            Dictionnaire avec totaux par type
        """
        consumptions = self.consumption_repo.get_by_period(target_date, target_date)

        summary = {
            "date": target_date,
            "ventes": {"count": 0, "revenue": 0, "cost": 0},
            "pertes": {"count": 0, "cost": 0},
            "repas_staff": {"count": 0, "cost": 0},
            "offerts": {"count": 0, "cost": 0},
            "total_revenue": 0,
            "total_cost": 0,
            "margin": 0,
        }

        for c in consumptions:
            total_cost = c.cout * c.quantite
            if c.type == RestaurantConsumptionType.VENTE:
                summary["ventes"]["count"] += c.quantite
                summary["ventes"]["revenue"] += c.prix_vente * c.quantite
                summary["ventes"]["cost"] += total_cost
                summary["total_revenue"] += c.prix_vente * c.quantite
            elif c.type == RestaurantConsumptionType.PERTE:
                summary["pertes"]["count"] += c.quantite
                summary["pertes"]["cost"] += total_cost
            elif c.type == RestaurantConsumptionType.REPAS_STAFF:
                summary["repas_staff"]["count"] += c.quantite
                summary["repas_staff"]["cost"] += total_cost
            elif c.type == RestaurantConsumptionType.OFFERT:
                summary["offerts"]["count"] += c.quantite
                summary["offerts"]["cost"] += total_cost

            summary["total_cost"] += total_cost

        summary["margin"] = summary["total_revenue"] - summary["total_cost"]

        return summary

    def get_best_sellers(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[Dict]:
        """
        Recupere les plats les plus vendus.

        Returns:
            Liste triee par quantite vendue
        """
        consumptions = self.consumption_repo.get_by_period(
            start_date, end_date,
            consumption_type=RestaurantConsumptionType.VENTE
        )

        # Agreger par plat
        plat_stats: Dict[int, Dict] = {}
        for c in consumptions:
            if c.plat_id not in plat_stats:
                plat_name = c.plat.name if c.plat else f"Plat #{c.plat_id}"
                plat_stats[c.plat_id] = {
                    "plat_id": c.plat_id,
                    "plat_name": plat_name,
                    "quantity_sold": 0,
                    "revenue": 0,
                    "cost": 0,
                }
            plat_stats[c.plat_id]["quantity_sold"] += c.quantite
            plat_stats[c.plat_id]["revenue"] += c.prix_vente * c.quantite
            plat_stats[c.plat_id]["cost"] += c.cout * c.quantite

        # Trier par quantite
        sorted_plats = sorted(
            plat_stats.values(),
            key=lambda x: x["quantity_sold"],
            reverse=True
        )

        return sorted_plats[:limit]

    def get_loss_report(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Rapport sur les pertes.

        Returns:
            Dictionnaire avec details des pertes
        """
        consumptions = self.consumption_repo.get_by_period(
            start_date, end_date,
            consumption_type=RestaurantConsumptionType.PERTE
        )

        total_cost = 0
        by_plat: Dict[int, Dict] = {}

        for c in consumptions:
            cost = c.cout * c.quantite
            total_cost += cost

            if c.plat_id not in by_plat:
                plat_name = c.plat.name if c.plat else f"Plat #{c.plat_id}"
                by_plat[c.plat_id] = {
                    "plat_id": c.plat_id,
                    "plat_name": plat_name,
                    "quantity": 0,
                    "cost": 0,
                }
            by_plat[c.plat_id]["quantity"] += c.quantite
            by_plat[c.plat_id]["cost"] += cost

        return {
            "period": {"start": start_date, "end": end_date},
            "total_cost": total_cost,
            "total_items": sum(p["quantity"] for p in by_plat.values()),
            "by_plat": list(by_plat.values()),
        }
