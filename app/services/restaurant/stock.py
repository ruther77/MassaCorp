"""
Service pour la gestion du stock restaurant.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.models.restaurant.stock import (
    RestaurantStock,
    RestaurantStockMovement,
    RestaurantStockMovementType,
)
from app.repositories.restaurant.stock import (
    RestaurantStockRepository,
    RestaurantStockMovementRepository,
)
from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
from app.repositories.restaurant.epicerie_link import RestaurantEpicerieLinkRepository


class StockNotFoundError(Exception):
    """Stock non trouve."""
    def __init__(self, ingredient_id: int):
        self.ingredient_id = ingredient_id
        super().__init__(f"Stock pour ingredient {ingredient_id} non trouve")


class InsufficientStockError(Exception):
    """Stock insuffisant."""
    def __init__(self, ingredient_id: int, requested: Decimal, available: Decimal):
        self.ingredient_id = ingredient_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuffisant pour ingredient {ingredient_id}: "
            f"demande {requested}, disponible {available}"
        )


class InvalidStockOperationError(Exception):
    """Operation de stock invalide."""
    pass


class NoEpicerieLinkError(Exception):
    """Aucun lien epicerie pour cet ingredient."""
    def __init__(self, ingredient_id: int):
        self.ingredient_id = ingredient_id
        super().__init__(f"Aucun lien epicerie pour ingredient {ingredient_id}")


class RestaurantStockService:
    """
    Service pour la gestion du stock.

    Responsabilites:
    - Gestion des niveaux de stock
    - Enregistrement des mouvements
    - Alertes de stock bas
    """

    def __init__(
        self,
        stock_repo: RestaurantStockRepository,
        movement_repo: RestaurantStockMovementRepository,
        ingredient_repo: RestaurantIngredientRepository,
        epicerie_link_repo: Optional[RestaurantEpicerieLinkRepository] = None,
    ):
        self.stock_repo = stock_repo
        self.movement_repo = movement_repo
        self.ingredient_repo = ingredient_repo
        self.epicerie_link_repo = epicerie_link_repo

    def get_stock(self, ingredient_id: int) -> RestaurantStock:
        """Recupere le stock d'un ingredient."""
        stock = self.stock_repo.get_by_ingredient(ingredient_id)
        if not stock:
            raise StockNotFoundError(ingredient_id)
        return stock

    def get_or_create_stock(self, ingredient_id: int) -> RestaurantStock:
        """Recupere ou cree le stock d'un ingredient."""
        return self.stock_repo.get_or_create(ingredient_id)

    def get_all_stocks(self) -> List[RestaurantStock]:
        """Recupere tous les stocks."""
        return self.stock_repo.get_all_with_ingredients()

    def get_low_stock_items(self) -> List[RestaurantStock]:
        """Recupere les items en stock bas."""
        return self.stock_repo.get_low_stock()

    def add_stock(
        self,
        ingredient_id: int,
        quantite: Decimal,
        movement_type: RestaurantStockMovementType = RestaurantStockMovementType.ENTREE,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        cout_unitaire: Optional[int] = None,
    ) -> RestaurantStockMovement:
        """
        Ajoute du stock (entree).

        Args:
            ingredient_id: ID de l'ingredient
            quantite: Quantite a ajouter
            movement_type: Type de mouvement (ENTREE ou AJUSTEMENT)
            reference: Reference externe (numero de facture, etc.)
            notes: Notes
            cout_unitaire: Cout unitaire en centimes

        Returns:
            Mouvement cree
        """
        if quantite <= 0:
            raise InvalidStockOperationError("La quantite doit etre positive")

        if movement_type not in [
            RestaurantStockMovementType.ENTREE,
            RestaurantStockMovementType.AJUSTEMENT
        ]:
            raise InvalidStockOperationError(
                "Type de mouvement invalide pour ajout de stock"
            )

        stock = self.get_or_create_stock(ingredient_id)

        # Creer le mouvement
        movement = self.movement_repo.create({
            "stock_id": stock.id,
            "type": movement_type,
            "quantity": quantite,
            "date_mouvement": date.today(),
            "reference": reference,
            "notes": notes,
        })

        # Mettre a jour le stock
        stock.quantity += quantite
        self.stock_repo.session.flush()

        return movement

    def remove_stock(
        self,
        ingredient_id: int,
        quantite: Decimal,
        movement_type: RestaurantStockMovementType = RestaurantStockMovementType.SORTIE,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        allow_negative: bool = False,
    ) -> RestaurantStockMovement:
        """
        Retire du stock (sortie).

        Args:
            ingredient_id: ID de l'ingredient
            quantite: Quantite a retirer (positive)
            movement_type: Type de mouvement (SORTIE, PERTE, AJUSTEMENT)
            reference: Reference externe
            notes: Notes
            allow_negative: Autoriser stock negatif

        Returns:
            Mouvement cree
        """
        if quantite <= 0:
            raise InvalidStockOperationError("La quantite doit etre positive")

        if movement_type not in [
            RestaurantStockMovementType.SORTIE,
            RestaurantStockMovementType.PERTE,
            RestaurantStockMovementType.AJUSTEMENT
        ]:
            raise InvalidStockOperationError(
                "Type de mouvement invalide pour retrait de stock"
            )

        stock = self.get_or_create_stock(ingredient_id)

        if not allow_negative and stock.quantity < quantite:
            raise InsufficientStockError(
                ingredient_id,
                quantite,
                stock.quantity
            )

        # Creer le mouvement
        movement = self.movement_repo.create({
            "stock_id": stock.id,
            "type": movement_type,
            "quantity": quantite,  # Toujours positif dans le mouvement
            "date_mouvement": date.today(),
            "reference": reference,
            "notes": notes,
        })

        # Mettre a jour le stock
        stock.quantity -= quantite
        self.stock_repo.session.flush()

        return movement

    def adjust_stock(
        self,
        ingredient_id: int,
        nouvelle_quantite: Decimal,
        notes: Optional[str] = None,
    ) -> RestaurantStockMovement:
        """
        Ajuste le stock a une nouvelle valeur (inventaire).

        Args:
            ingredient_id: ID de l'ingredient
            nouvelle_quantite: Nouvelle quantite
            notes: Notes explicatives

        Returns:
            Mouvement cree
        """
        if nouvelle_quantite < 0:
            raise InvalidStockOperationError("La quantite ne peut pas etre negative")

        stock = self.get_or_create_stock(ingredient_id)
        difference = nouvelle_quantite - stock.quantity

        # Creer le mouvement d'inventaire
        movement = self.movement_repo.create({
            "stock_id": stock.id,
            "type": RestaurantStockMovementType.AJUSTEMENT,
            "quantity": abs(difference),
            "date_mouvement": date.today(),
            "notes": notes or "Ajustement inventaire",
        })

        # Mettre a jour le stock
        stock.quantity = nouvelle_quantite
        stock.last_inventory_date = date.today()
        self.stock_repo.session.flush()

        return movement

    def record_loss(
        self,
        ingredient_id: int,
        quantite: Decimal,
        notes: Optional[str] = None,
    ) -> RestaurantStockMovement:
        """
        Enregistre une perte de stock.

        Args:
            ingredient_id: ID de l'ingredient
            quantite: Quantite perdue (positive)
            notes: Raison de la perte

        Returns:
            Mouvement cree
        """
        return self.remove_stock(
            ingredient_id=ingredient_id,
            quantite=quantite,
            movement_type=RestaurantStockMovementType.PERTE,
            notes=notes,
            allow_negative=False,
        )

    def get_movements(
        self,
        ingredient_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[RestaurantStockMovement]:
        """Recupere l'historique des mouvements d'un ingredient."""
        stock = self.get_stock(ingredient_id)
        if start_date and end_date:
            return self.movement_repo.get_by_period(stock.id, start_date, end_date)
        return self.movement_repo.get_by_stock(stock.id)

    def get_recent_movements(
        self,
        limit: int = 50
    ) -> List[RestaurantStockMovement]:
        """Recupere les mouvements recents."""
        return self.movement_repo.get_recent(limit)

    def get_stock_alerts(self) -> List[dict]:
        """
        Recupere les alertes de stock.

        Returns:
            Liste de dictionnaires avec ingredient et niveau d'alerte
        """
        low_stocks = self.get_low_stock_items()
        alerts = []
        for stock in low_stocks:
            if stock.ingredient and stock.ingredient.seuil_alerte:
                deficit = stock.ingredient.seuil_alerte - stock.quantity
                alerts.append({
                    "ingredient_id": stock.ingredient_id,
                    "ingredient_name": stock.ingredient.name,
                    "quantity": stock.quantity,
                    "seuil_alerte": stock.ingredient.seuil_alerte,
                    "deficit": deficit,
                    "unit": stock.ingredient.unit.value if stock.ingredient else None,
                })
        return alerts

    def calculate_total_stock_value(self) -> int:
        """
        Calcule la valeur totale du stock en centimes.

        Returns:
            Valeur totale du stock en centimes
        """
        stocks = self.get_all_stocks()
        total = 0
        for stock in stocks:
            if stock.ingredient and stock.ingredient.prix_unitaire:
                total += int(stock.quantity * stock.ingredient.prix_unitaire)
        return total

    def transfer_from_epicerie(
        self,
        ingredient_id: int,
        quantite: Decimal,
        produit_id: Optional[int] = None,
        fournisseur: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> RestaurantStockMovement:
        """
        Transfert de stock depuis l'epicerie vers le restaurant.

        Args:
            ingredient_id: ID de l'ingredient restaurant
            quantite: Quantite a transferer (en unite de l'ingredient: kg, L, U)
            produit_id: ID du produit epicerie (optionnel, sinon utilise lien primaire)
            fournisseur: Fournisseur source (METRO, TAIYAT, EUROCIEL, OTHER)
            notes: Notes

        Returns:
            Mouvement cree

        Raises:
            NoEpicerieLinkError: Si aucun lien epicerie n'existe
            InvalidStockOperationError: Si quantite invalide
        """
        if quantite <= 0:
            raise InvalidStockOperationError("La quantite doit etre positive")

        if not self.epicerie_link_repo:
            raise InvalidStockOperationError(
                "EpicerieLinkRepository requis pour les transferts"
            )

        # Trouver le lien epicerie
        if produit_id and fournisseur:
            # Lien specifique
            links = self.epicerie_link_repo.get_by_ingredient(ingredient_id)
            link = next(
                (l for l in links if l.produit_id == produit_id and l.fournisseur == fournisseur),
                None
            )
        else:
            # Lien primaire
            link = self.epicerie_link_repo.get_primary_by_ingredient(ingredient_id)

        if not link:
            raise NoEpicerieLinkError(ingredient_id)

        # Creer le mouvement de transfert
        stock = self.get_or_create_stock(ingredient_id)

        reference = f"Transfert {link.fournisseur} #{link.produit_id}"
        if notes:
            reference = f"{reference} - {notes}"

        movement = self.movement_repo.create({
            "stock_id": stock.id,
            "type": RestaurantStockMovementType.TRANSFERT,
            "quantity": quantite,
            "date_mouvement": date.today(),
            "reference": reference,
            "notes": f"Depuis {link.fournisseur} produit #{link.produit_id}",
        })

        # Mettre a jour le stock restaurant
        stock.quantity += quantite
        self.stock_repo.session.flush()

        return movement

    def bulk_transfer_from_epicerie(
        self,
        transfers: List[dict],
    ) -> List[RestaurantStockMovement]:
        """
        Transferts multiples depuis l'epicerie.

        Args:
            transfers: Liste de dicts avec ingredient_id, quantite, etc.

        Returns:
            Liste de mouvements crees
        """
        movements = []
        for t in transfers:
            try:
                movement = self.transfer_from_epicerie(
                    ingredient_id=t["ingredient_id"],
                    quantite=Decimal(str(t["quantite"])),
                    produit_id=t.get("produit_id"),
                    fournisseur=t.get("fournisseur"),
                    notes=t.get("notes"),
                )
                movements.append(movement)
            except (NoEpicerieLinkError, InvalidStockOperationError):
                # Log et continue
                pass
        return movements

    def auto_replenish_from_epicerie(
        self,
        ingredient_id: Optional[int] = None,
    ) -> List[RestaurantStockMovement]:
        """
        Reapprovisionne automatiquement les ingredients en dessous du seuil.

        Si ingredient_id est specifie, traite uniquement cet ingredient.
        Sinon, traite tous les ingredients en stock bas.

        Returns:
            Liste de mouvements crees
        """
        if not self.epicerie_link_repo:
            return []

        movements = []

        if ingredient_id:
            # Un seul ingredient
            stock = self.stock_repo.get_by_ingredient(ingredient_id)
            ingredient = self.ingredient_repo.get(ingredient_id)
            if stock and ingredient and ingredient.seuil_alerte:
                if stock.quantity < ingredient.seuil_alerte:
                    # Transferer la quantite manquante + 20% de marge
                    deficit = ingredient.seuil_alerte - stock.quantity
                    quantite = deficit * Decimal("1.2")
                    try:
                        movement = self.transfer_from_epicerie(
                            ingredient_id=ingredient_id,
                            quantite=quantite,
                            notes="Reappro auto",
                        )
                        movements.append(movement)
                    except (NoEpicerieLinkError, InvalidStockOperationError):
                        pass
        else:
            # Tous les ingredients en stock bas
            low_stocks = self.get_low_stock_items()
            for stock in low_stocks:
                if stock.ingredient and stock.ingredient.seuil_alerte:
                    deficit = stock.ingredient.seuil_alerte - stock.quantity
                    quantite = deficit * Decimal("1.2")
                    try:
                        movement = self.transfer_from_epicerie(
                            ingredient_id=stock.ingredient_id,
                            quantite=quantite,
                            notes="Reappro auto",
                        )
                        movements.append(movement)
                    except (NoEpicerieLinkError, InvalidStockOperationError):
                        pass

        return movements
