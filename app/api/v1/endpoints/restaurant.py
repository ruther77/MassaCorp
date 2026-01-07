"""
API Endpoints Restaurant Domain.
Gestion des ingredients, plats, stock, consommations, charges.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.restaurant.ingredient import (
    RestaurantUnit,
    RestaurantIngredientCategory,
)
from app.models.restaurant.plat import RestaurantPlatCategory
from app.models.restaurant.stock import RestaurantStockMovementType
from app.models.restaurant.consumption import RestaurantConsumptionType
from app.models.restaurant.charge import (
    RestaurantChargeType,
    RestaurantChargeFrequency,
)
from app.repositories.restaurant.ingredient import RestaurantIngredientRepository
from app.repositories.restaurant.plat import (
    RestaurantPlatRepository,
    RestaurantPlatIngredientRepository,
)
from app.repositories.restaurant.epicerie_link import RestaurantEpicerieLinkRepository
from app.services.metro import MetroService
from app.services.taiyat import TaiyatService
from app.services.eurociel import EurocielService
from app.repositories.restaurant.stock import (
    RestaurantStockRepository,
    RestaurantStockMovementRepository,
)
from app.repositories.restaurant.consumption import RestaurantConsumptionRepository
from app.repositories.restaurant.charge import RestaurantChargeRepository
from app.services.restaurant.ingredient import (
    RestaurantIngredientService,
    IngredientNotFoundError,
    IngredientNameExistsError,
)
from app.services.restaurant.plat import (
    RestaurantPlatService,
    PlatNotFoundError,
    InvalidPlatError,
)
from app.services.restaurant.stock import (
    RestaurantStockService,
    StockNotFoundError,
    InsufficientStockError,
    InvalidStockOperationError,
    NoEpicerieLinkError,
)
from app.services.restaurant.consumption import (
    RestaurantConsumptionService,
    InvalidConsumptionError,
)
from app.services.restaurant.charge import (
    RestaurantChargeService,
    ChargeNotFoundError,
    InvalidChargeError,
)

router = APIRouter(prefix="/restaurant", tags=["Restaurant"])


# =============================================================================
# Schemas
# =============================================================================

# --- Ingredients ---

class IngredientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    unit: RestaurantUnit
    category: RestaurantIngredientCategory = RestaurantIngredientCategory.AUTRE
    prix_unitaire: int = Field(default=0, ge=0, description="Prix unitaire en centimes")
    seuil_alerte: Optional[Decimal] = Field(None, ge=0)
    default_supplier_id: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class IngredientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    unit: Optional[RestaurantUnit] = None
    category: Optional[RestaurantIngredientCategory] = None
    prix_unitaire: Optional[int] = Field(None, ge=0)
    seuil_alerte: Optional[Decimal] = Field(None, ge=0)
    default_supplier_id: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class IngredientResponse(BaseModel):
    id: int
    name: str
    unit: RestaurantUnit
    category: RestaurantIngredientCategory
    prix_unitaire: int
    seuil_alerte: Optional[Decimal]
    default_supplier_id: Optional[int]
    notes: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


# --- Epicerie Links ---

class EpicerieLinkCreate(BaseModel):
    ingredient_id: int
    produit_id: int
    fournisseur: str = Field(default="METRO", description="Code fournisseur (METRO, TAIYAT, etc.)")
    ratio: Decimal = Field(default=Decimal("1.0"), gt=0)
    is_primary: bool = True

    class Config:
        extra = "forbid"


class EpicerieLinkUpdate(BaseModel):
    ratio: Optional[Decimal] = Field(None, gt=0)
    is_primary: Optional[bool] = None

    class Config:
        extra = "forbid"


class EpicerieLinkResponse(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    produit_id: int
    produit_nom: Optional[str] = None
    produit_prix: Optional[Decimal] = None
    ratio: Decimal
    is_primary: bool

    class Config:
        from_attributes = True


class IngredientWithLinksResponse(BaseModel):
    id: int
    name: str
    unit: RestaurantUnit
    category: RestaurantIngredientCategory
    prix_unitaire: int
    is_active: bool
    epicerie_links: List[EpicerieLinkResponse] = []

    class Config:
        from_attributes = True


class MetroProduitSearchResponse(BaseModel):
    id: int
    designation: str
    famille: Optional[str] = None
    prix_unitaire_moyen: Optional[Decimal] = None
    montant_total_ht: Optional[Decimal] = None

    class Config:
        from_attributes = True


# --- Plats ---

class PlatIngredientInput(BaseModel):
    ingredient_id: int
    quantite: Decimal = Field(..., gt=0)
    notes: Optional[str] = None


class PlatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    prix_vente: int = Field(..., gt=0, description="Prix de vente en centimes")
    category: RestaurantPlatCategory = RestaurantPlatCategory.PLAT
    description: Optional[str] = None
    is_menu: bool = False
    image_url: Optional[str] = None
    notes: Optional[str] = None
    ingredients: Optional[List[PlatIngredientInput]] = None

    class Config:
        extra = "forbid"


class PlatUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    prix_vente: Optional[int] = Field(None, gt=0)
    category: Optional[RestaurantPlatCategory] = None
    description: Optional[str] = None
    is_menu: Optional[bool] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class PlatIngredientResponse(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    quantite: Decimal
    cout_ligne: int
    notes: Optional[str]

    class Config:
        from_attributes = True


class PlatResponse(BaseModel):
    id: int
    name: str
    prix_vente: int
    category: RestaurantPlatCategory
    description: Optional[str]
    is_menu: bool
    is_active: bool
    cout_total: int
    food_cost_ratio: float  # Serialise en float plutot que string
    is_profitable: bool

    class Config:
        from_attributes = True


class PlatDetailResponse(PlatResponse):
    ingredients: List[PlatIngredientResponse] = []


# --- Stock ---

class StockMovementCreate(BaseModel):
    ingredient_id: int
    quantite: Decimal = Field(..., gt=0)
    movement_type: RestaurantStockMovementType
    reference: Optional[str] = None
    notes: Optional[str] = None
    cout_unitaire: Optional[int] = Field(None, ge=0)

    class Config:
        extra = "forbid"


class StockAdjustment(BaseModel):
    ingredient_id: int
    nouvelle_quantite: Decimal = Field(..., ge=0)
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class StockResponse(BaseModel):
    id: int
    ingredient_id: int
    ingredient_name: str
    quantity: Decimal
    dernier_prix_achat: Optional[int]
    valeur_stock: int
    is_low_stock: bool

    class Config:
        from_attributes = True


class StockMovementResponse(BaseModel):
    id: int
    stock_id: int
    type: RestaurantStockMovementType
    quantite: Decimal
    quantite_avant: Decimal
    reference: Optional[str]
    notes: Optional[str]
    cout_unitaire: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


class StockTransferCreate(BaseModel):
    """Transfert depuis epicerie vers restaurant."""
    ingredient_id: int
    quantite: Decimal = Field(..., gt=0, description="Quantite a transferer")
    produit_id: Optional[int] = Field(None, description="ID produit epicerie (optionnel)")
    fournisseur: Optional[str] = Field(None, description="METRO, TAIYAT, EUROCIEL, OTHER")
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class BulkStockTransfer(BaseModel):
    """Transferts multiples."""
    transfers: List[StockTransferCreate]


# --- Consumptions ---

class ConsumptionCreate(BaseModel):
    plat_id: int
    quantite: int = Field(default=1, ge=1)
    prix_vente: Optional[int] = Field(None, ge=0)
    date_consumption: Optional[date] = None
    notes: Optional[str] = None
    decrement_stock: bool = True

    class Config:
        extra = "forbid"


class ConsumptionResponse(BaseModel):
    id: int
    plat_id: int
    plat_name: str
    type: RestaurantConsumptionType
    quantite: int
    prix_vente: int
    cout: int
    date: date
    notes: Optional[str]

    class Config:
        from_attributes = True


# --- Charges ---

class ChargeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    charge_type: RestaurantChargeType
    montant: int = Field(..., gt=0, description="Montant en centimes")
    frequency: RestaurantChargeFrequency = RestaurantChargeFrequency.MENSUEL
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class ChargeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    charge_type: Optional[RestaurantChargeType] = None
    montant: Optional[int] = Field(None, gt=0)
    frequency: Optional[RestaurantChargeFrequency] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class ChargeResponse(BaseModel):
    id: int
    name: str
    type: RestaurantChargeType
    montant: int
    frequency: RestaurantChargeFrequency
    montant_mensuel: int
    date_debut: date
    date_fin: Optional[date]
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


# =============================================================================
# Dependencies
# =============================================================================

def get_ingredient_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantIngredientService:
    """Fournit le service ingredient avec isolation tenant."""
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)
    stock_repo = RestaurantStockRepository(db, current_user.tenant_id)
    return RestaurantIngredientService(ingredient_repo, stock_repo)


def get_plat_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantPlatService:
    """Fournit le service plat avec isolation tenant."""
    plat_repo = RestaurantPlatRepository(db, current_user.tenant_id)
    plat_ing_repo = RestaurantPlatIngredientRepository(db)
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)
    return RestaurantPlatService(plat_repo, plat_ing_repo, ingredient_repo)


def get_stock_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantStockService:
    """Fournit le service stock avec isolation tenant."""
    stock_repo = RestaurantStockRepository(db, current_user.tenant_id)
    movement_repo = RestaurantStockMovementRepository(db)
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)
    epicerie_link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)
    return RestaurantStockService(
        stock_repo, movement_repo, ingredient_repo, epicerie_link_repo
    )


def get_consumption_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantConsumptionService:
    """Fournit le service consumption avec isolation tenant."""
    consumption_repo = RestaurantConsumptionRepository(db, current_user.tenant_id)
    plat_service = get_plat_service(db, current_user)
    stock_service = get_stock_service(db, current_user)
    return RestaurantConsumptionService(consumption_repo, plat_service, stock_service)


def get_charge_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantChargeService:
    """Fournit le service charge avec isolation tenant."""
    charge_repo = RestaurantChargeRepository(db, current_user.tenant_id)
    return RestaurantChargeService(charge_repo)


# =============================================================================
# Ingredients Endpoints
# =============================================================================

@router.get("/ingredients", response_model=List[IngredientResponse], summary="Liste des ingredients")
def list_ingredients(
    category: Optional[RestaurantIngredientCategory] = None,
    active_only: bool = Query(True),
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Recupere les ingredients."""
    if category:
        return service.get_ingredients_by_category(category)
    if active_only:
        return service.get_active_ingredients()
    return service.get_active_ingredients()


@router.post("/ingredients", response_model=IngredientResponse, status_code=201, summary="Creer un ingredient")
def create_ingredient(
    data: IngredientCreate,
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Cree un nouvel ingredient."""
    try:
        return service.create_ingredient(**data.model_dump())
    except IngredientNameExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/ingredients/low-stock", response_model=List[IngredientResponse], summary="Ingredients en stock bas")
def list_low_stock_ingredients(
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Recupere les ingredients en stock bas."""
    return service.get_low_stock_ingredients()


@router.get("/ingredients/search", response_model=List[IngredientResponse], summary="Rechercher ingredients")
def search_ingredients(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Recherche ingredients par nom."""
    return service.search_ingredients(q)


@router.get("/ingredients/{ingredient_id}", response_model=IngredientResponse, summary="Detail d'un ingredient")
def get_ingredient(
    ingredient_id: int,
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Recupere un ingredient par ID."""
    try:
        return service.get_ingredient(ingredient_id)
    except IngredientNotFoundError:
        raise HTTPException(status_code=404, detail="Ingredient non trouve")


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientResponse, summary="Modifier un ingredient")
def update_ingredient(
    ingredient_id: int,
    data: IngredientUpdate,
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Met a jour un ingredient."""
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return service.update_ingredient(ingredient_id, **update_data)
    except IngredientNotFoundError:
        raise HTTPException(status_code=404, detail="Ingredient non trouve")
    except IngredientNameExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/ingredients/{ingredient_id}", status_code=204, summary="Desactiver un ingredient")
def deactivate_ingredient(
    ingredient_id: int,
    service: RestaurantIngredientService = Depends(get_ingredient_service)
):
    """Desactive un ingredient."""
    try:
        service.deactivate_ingredient(ingredient_id)
    except IngredientNotFoundError:
        raise HTTPException(status_code=404, detail="Ingredient non trouve")


# =============================================================================
# Epicerie Links Endpoints (Rapprochement Ingredients-Produits)
# =============================================================================

def get_epicerie_link_repo(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RestaurantEpicerieLinkRepository:
    """Fournit le repository des liens epicerie."""
    return RestaurantEpicerieLinkRepository(db, current_user.tenant_id)


def get_metro_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MetroService:
    """Fournit le service Metro."""
    return MetroService(db=db, tenant_id=current_user.tenant_id)


def get_taiyat_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TaiyatService:
    """Fournit le service Taiyat."""
    return TaiyatService(db=db, tenant_id=current_user.tenant_id)


@router.get("/epicerie-links", summary="Liste des liens ingredients-epicerie")
def list_epicerie_links(
    ingredient_id: Optional[int] = Query(None, description="Filtrer par ingredient"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    metro_service: MetroService = Depends(get_metro_service)
):
    """
    Liste tous les liens entre ingredients et produits epicerie.
    Permet de voir quels ingredients sont lies a quels produits Metro.
    """
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)

    if ingredient_id:
        links = link_repo.get_by_ingredient(ingredient_id)
    else:
        # Get all links
        from sqlalchemy import select
        from app.models.restaurant.epicerie_link import RestaurantEpicerieLink
        stmt = select(RestaurantEpicerieLink).where(
            RestaurantEpicerieLink.tenant_id == current_user.tenant_id
        )
        links = list(db.execute(stmt).scalars().all())

    # Services fournisseurs
    taiyat_service = TaiyatService(db=db, tenant_id=current_user.tenant_id)
    eurociel_service = EurocielService(db=db, tenant_id=current_user.tenant_id)

    # Enrichir avec les infos produit selon fournisseur
    result = []
    for link in links:
        ingredient = ingredient_repo.get(link.ingredient_id)
        fournisseur = getattr(link, 'fournisseur', 'METRO') or 'METRO'
        produit_nom = None
        produit_prix = None

        if fournisseur == "METRO":
            produit = metro_service.get_produit_agrege(link.produit_id)
            if produit:
                produit_nom = produit.get("designation_clean") or produit.get("designation")
                produit_prix = int(produit.get("prix_unitaire_moyen", 0) * 100) if produit.get("prix_unitaire_moyen") else None
        elif fournisseur == "TAIYAT":
            produit = taiyat_service.get_product_by_id(link.produit_id)
            if produit:
                produit_nom = produit.get("designation_clean") or produit.get("designation")
                produit_prix = int(produit.get("prix_moyen_kg", 0) * 100) if produit.get("prix_moyen_kg") else None
        elif fournisseur == "EUROCIEL":
            produit = eurociel_service.get_product_by_id(link.produit_id)
            if produit:
                produit_nom = produit.get("designation_clean") or produit.get("designation")
                produit_prix = int(produit.get("prix_moyen", 0) * 100) if produit.get("prix_moyen") else None

        result.append({
            "id": link.id,
            "ingredient_id": link.ingredient_id,
            "ingredient_name": ingredient.name if ingredient else "",
            "produit_id": link.produit_id,
            "produit_nom": produit_nom,
            "produit_prix": produit_prix,
            "fournisseur": fournisseur,
            "ratio": link.ratio,
            "is_primary": link.is_primary,
        })

    return result


@router.get("/ingredients-with-links", summary="Ingredients avec leurs liens epicerie")
def list_ingredients_with_links(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste tous les ingredients avec leurs liens epicerie.
    Supporte les fournisseurs METRO, TAIYAT et EUROCIEL.
    """
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)

    # Services fournisseurs
    metro_service = MetroService(db=db, tenant_id=current_user.tenant_id)
    taiyat_service = TaiyatService(db=db, tenant_id=current_user.tenant_id)
    eurociel_service = EurocielService(db=db, tenant_id=current_user.tenant_id)

    ingredients = ingredient_repo.get_all(limit=500)

    result = []
    for ing in ingredients:
        links = link_repo.get_by_ingredient(ing.id)

        links_data = []
        for link in links:
            fournisseur = getattr(link, 'fournisseur', 'METRO') or 'METRO'
            produit_nom = None
            produit_prix = None

            if fournisseur == "METRO":
                # Utiliser metro_produit_agregat qui contient les bons IDs
                produit = metro_service.get_produit_agrege(link.produit_id)
                if produit:
                    produit_nom = produit.get("designation_clean") or produit.get("designation")
                    produit_prix = int(produit.get("prix_unitaire_moyen", 0) * 100) if produit.get("prix_unitaire_moyen") else None
            elif fournisseur == "TAIYAT":
                produit = taiyat_service.get_product_by_id(link.produit_id)
                if produit:
                    produit_nom = produit.get("designation_clean") or produit.get("designation")
                    produit_prix = int(produit.get("prix_moyen_kg", 0) * 100) if produit.get("prix_moyen_kg") else None
            elif fournisseur == "EUROCIEL":
                produit = eurociel_service.get_product_by_id(link.produit_id)
                if produit:
                    produit_nom = produit.get("designation_clean") or produit.get("designation")
                    produit_prix = int(produit.get("prix_moyen", 0) * 100) if produit.get("prix_moyen") else None
            elif fournisseur == "OTHER":
                # Chercher dans other_produit_agregat
                from sqlalchemy import text
                other_result = db.execute(
                    text("SELECT designation, prix_unitaire FROM dwh.other_produit_agregat WHERE id = :id"),
                    {"id": link.produit_id}
                ).fetchone()
                if other_result:
                    produit_nom = other_result[0]
                    produit_prix = int(other_result[1] * 100) if other_result[1] else None

            links_data.append({
                "id": link.id,
                "ingredient_id": link.ingredient_id,
                "ingredient_name": ing.name,
                "produit_id": link.produit_id,
                "produit_nom": produit_nom,
                "produit_prix": produit_prix,
                "fournisseur": fournisseur,
                "ratio": link.ratio,
                "is_primary": link.is_primary,
            })

        result.append({
            "id": ing.id,
            "name": ing.name,
            "unit": ing.unit,
            "category": ing.category,
            "prix_unitaire": ing.prix_unitaire,
            "is_active": ing.is_active,
            "epicerie_links": links_data,
        })

    return result


@router.post("/epicerie-links", status_code=201, summary="Creer un lien ingredient-epicerie")
def create_epicerie_link(
    data: EpicerieLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cree un lien entre un ingredient et un produit fournisseur.
    Supporte METRO, TAIYAT et EUROCIEL.
    """
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)

    # Verifier que l'ingredient existe
    ingredient = ingredient_repo.get(data.ingredient_id)
    if not ingredient:
        raise HTTPException(status_code=404, detail="Ingredient non trouve")

    # Verifier que le produit existe selon le fournisseur
    produit_nom = None
    produit_prix = None
    fournisseur = data.fournisseur.upper()

    if fournisseur == "METRO":
        metro_service = MetroService(db=db, tenant_id=current_user.tenant_id)
        # Utiliser metro_produit_agregat qui contient les bons IDs
        produit = metro_service.get_produit_agrege(data.produit_id)
        if not produit:
            raise HTTPException(status_code=404, detail="Produit METRO non trouve")
        produit_nom = produit.get("designation_clean") or produit.get("designation")
        produit_prix = int(produit.get("prix_unitaire_moyen", 0) * 100) if produit.get("prix_unitaire_moyen") else None
    elif fournisseur == "TAIYAT":
        taiyat_service = TaiyatService(db=db, tenant_id=current_user.tenant_id)
        produit = taiyat_service.get_product_by_id(data.produit_id)
        if not produit:
            raise HTTPException(status_code=404, detail="Produit TAIYAT non trouve")
        produit_nom = produit.get("designation_clean") or produit.get("designation")
        produit_prix = int(produit.get("prix_moyen_kg", 0) * 100) if produit.get("prix_moyen_kg") else None
    elif fournisseur == "EUROCIEL":
        eurociel_service = EurocielService(db=db, tenant_id=current_user.tenant_id)
        produit = eurociel_service.get_product_by_id(data.produit_id)
        if not produit:
            raise HTTPException(status_code=404, detail="Produit EUROCIEL non trouve")
        produit_nom = produit.get("designation_clean") or produit.get("designation")
        produit_prix = int(produit.get("prix_moyen", 0) * 100) if produit.get("prix_moyen") else None
    else:
        raise HTTPException(status_code=400, detail=f"Fournisseur non supporte: {fournisseur}")

    # Verifier si le lien existe deja (meme fournisseur + meme produit_id)
    existing = link_repo.get_by_ingredient(data.ingredient_id)
    for ex_link in existing:
        if ex_link.produit_id == data.produit_id and ex_link.fournisseur == fournisseur:
            raise HTTPException(status_code=409, detail="Ce lien existe deja")

    # Si is_primary, desactiver les autres liens primaires
    if data.is_primary:
        for link in existing:
            if link.is_primary:
                link.is_primary = False

    # Creer le lien
    from app.models.restaurant.epicerie_link import RestaurantEpicerieLink
    link = RestaurantEpicerieLink(
        tenant_id=current_user.tenant_id,
        ingredient_id=data.ingredient_id,
        produit_id=data.produit_id,
        fournisseur=fournisseur,
        ratio=data.ratio,
        is_primary=data.is_primary,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    return {
        "id": link.id,
        "ingredient_id": link.ingredient_id,
        "ingredient_name": ingredient.name,
        "produit_id": link.produit_id,
        "produit_nom": produit_nom,
        "produit_prix": produit_prix,
        "fournisseur": fournisseur,
        "ratio": link.ratio,
        "is_primary": link.is_primary,
        "message": "Lien cree avec succes",
    }


@router.patch("/epicerie-links/{link_id}", summary="Modifier un lien")
def update_epicerie_link(
    link_id: int,
    data: EpicerieLinkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Met a jour un lien ingredient-epicerie."""
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)

    link = link_repo.get(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Lien non trouve")

    if data.ratio is not None:
        link.ratio = data.ratio

    if data.is_primary is not None:
        if data.is_primary:
            link_repo.set_primary(link_id)
        else:
            link.is_primary = False

    db.commit()

    return {"id": link.id, "message": "Lien mis a jour"}


@router.delete("/epicerie-links/{link_id}", status_code=204, summary="Supprimer un lien")
def delete_epicerie_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprime un lien ingredient-epicerie."""
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)

    link = link_repo.get(link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Lien non trouve")

    db.delete(link)
    db.commit()


@router.get("/epicerie-products/search", summary="Rechercher produits fournisseurs")
def search_epicerie_products(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    fournisseur: Optional[str] = Query(None, description="Filtrer par fournisseur (metro, taiyat, eurociel, all)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Recherche des produits fournisseurs pour le rapprochement.
    Cherche dans Metro, Taiyat et Eurociel simultanement.
    Utilise une recherche multi-mots et multi-champs.
    """
    results = []
    fournisseur_filter = (fournisseur or "all").lower()
    # Donner a chaque source une bonne limite pour maximiser les resultats
    per_source = max(50, limit) if fournisseur_filter == "all" else limit

    # Recherche METRO
    if fournisseur_filter in ("metro", "all"):
        try:
            metro_service = MetroService(db=db, tenant_id=current_user.tenant_id)
            produits, _ = metro_service.get_produits(
                page=1,
                per_page=per_source,
                q=q,
                sort_by="designation",
                sort_order="asc",
            )
            for p in produits:
                results.append({
                    "id": p.id,
                    "fournisseur": "METRO",
                    "fournisseur_color": "blue",
                    "designation": p.designation_brute or p.nom_court,
                    "famille": p.famille,
                    "categorie": p.categorie,
                    "prix_unitaire_moyen": int(p.prix_achat_unitaire * 100) if p.prix_achat_unitaire else None,
                    "unite": "U",
                })
        except Exception as e:
            import logging
            logging.error(f"Erreur recherche METRO: {e}")
            pass

    # Recherche TAIYAT
    if fournisseur_filter in ("taiyat", "all"):
        try:
            taiyat_service = TaiyatService(db=db, tenant_id=current_user.tenant_id)
            taiyat_result = taiyat_service.get_products(
                page=1,
                per_page=per_source,
                search=q,
                sort_by="designation_clean",
                sort_order="asc",
            )
            for p in taiyat_result.get("items", []):
                results.append({
                    "id": p["id"],
                    "fournisseur": "TAIYAT",
                    "fournisseur_color": "green",
                    "designation": p.get("designation_clean") or p.get("designation"),
                    "famille": p.get("provenance", "Fruits & Legumes"),
                    "categorie": p.get("provenance"),
                    "prix_unitaire_moyen": int(p.get("prix_moyen_kg", 0) * 100) if p.get("prix_moyen_kg") else None,
                    "unite": "kg",
                })
        except Exception as e:
            import logging
            logging.error(f"Erreur recherche TAIYAT: {e}")
            pass

    # Recherche EUROCIEL
    if fournisseur_filter in ("eurociel", "all"):
        try:
            eurociel_service = EurocielService(db=db, tenant_id=current_user.tenant_id)
            eurociel_result = eurociel_service.get_products(
                page=1,
                per_page=per_source,
                search=q,
                sort_by="designation_clean",
                sort_order="asc",
            )
            for p in eurociel_result.get("items", []):
                results.append({
                    "id": p["id"],
                    "fournisseur": "EUROCIEL",
                    "fournisseur_color": "purple",
                    "designation": p.get("designation_clean") or p.get("designation"),
                    "famille": p.get("categorie", "Produits tropicaux"),
                    "categorie": p.get("categorie"),
                    "prix_unitaire_moyen": int(p.get("prix_moyen", 0) * 100) if p.get("prix_moyen") else None,
                    "unite": "kg",
                })
        except Exception as e:
            import logging
            logging.error(f"Erreur recherche EUROCIEL: {e}")
            pass

    # Recherche OTHER (produits manuels)
    if fournisseur_filter in ("other", "all"):
        try:
            from sqlalchemy import text
            other_query = text("""
                SELECT id, designation, categorie, prix_unitaire, unite
                FROM dwh.other_produit_agregat
                WHERE LOWER(designation) LIKE :search
                ORDER BY designation
                LIMIT :limit
            """)
            other_results = db.execute(
                other_query,
                {"search": f"%{q.lower()}%", "limit": per_source}
            ).fetchall()
            for p in other_results:
                results.append({
                    "id": p[0],
                    "fournisseur": "OTHER",
                    "fournisseur_color": "gray",
                    "designation": p[1],
                    "famille": p[2] or "Autres produits",
                    "categorie": p[2],
                    "prix_unitaire_moyen": int(p[3] * 100) if p[3] else None,
                    "unite": p[4] or "U",
                })
        except Exception as e:
            import logging
            logging.error(f"Erreur recherche OTHER: {e}")
            pass

    # Trier par pertinence intelligente
    q_lower = q.lower().strip()
    search_terms = q_lower.split()

    def calculate_relevance(item):
        """
        Calcule un score de pertinence (plus bas = meilleur)
        0: Match exact
        1: Commence par le terme
        2: Contient tous les termes
        3: Contient certains termes
        4: Pas de match
        """
        designation = (item.get("designation") or "").lower()

        # Match exact
        if designation == q_lower:
            return (0, designation)

        # Commence par le terme de recherche
        if designation.startswith(q_lower):
            return (1, designation)

        # Verifie combien de termes sont presents
        matches = sum(1 for term in search_terms if term in designation)

        if matches == len(search_terms):
            # Tous les termes trouves
            return (2, designation)
        elif matches > 0:
            # Certains termes trouves (moins de matches = score plus eleve)
            return (3 + (len(search_terms) - matches), designation)

        return (10, designation)

    results.sort(key=calculate_relevance)

    return results[:limit]


@router.post("/sync-prices-from-epicerie", summary="Synchroniser les prix depuis epicerie")
def sync_prices_from_epicerie(
    force: bool = Query(False, description="Forcer la mise a jour de tous les prix"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    metro_service: MetroService = Depends(get_metro_service)
):
    """
    Synchronise les prix des ingredients depuis les produits epicerie lies.
    Met a jour prix_unitaire de l'ingredient a partir du prix du produit * ratio.
    """
    link_repo = RestaurantEpicerieLinkRepository(db, current_user.tenant_id)
    ingredient_repo = RestaurantIngredientRepository(db, current_user.tenant_id)

    # Get all primary links
    from sqlalchemy import select
    from app.models.restaurant.epicerie_link import RestaurantEpicerieLink
    stmt = select(RestaurantEpicerieLink).where(
        RestaurantEpicerieLink.tenant_id == current_user.tenant_id,
        RestaurantEpicerieLink.is_primary == True
    )
    links = list(db.execute(stmt).scalars().all())

    updated = 0
    skipped = 0
    errors = []
    price_changes = []

    # Services fournisseurs
    taiyat_service = TaiyatService(db=db, tenant_id=current_user.tenant_id)
    eurociel_service = EurocielService(db=db, tenant_id=current_user.tenant_id)

    for link in links:
        try:
            ingredient = ingredient_repo.get(link.ingredient_id)
            if not ingredient:
                errors.append({"ingredient_id": link.ingredient_id, "error": "Ingredient non trouve"})
                continue

            fournisseur = getattr(link, 'fournisseur', 'METRO') or 'METRO'
            produit_prix = None
            produit_nom = None

            if fournisseur == "METRO":
                produit = metro_service.get_produit_agrege(link.produit_id)
                if produit:
                    produit_prix = produit.get("prix_unitaire_moyen")
                    produit_nom = produit.get("designation_clean") or produit.get("designation")
            elif fournisseur == "TAIYAT":
                produit = taiyat_service.get_product_by_id(link.produit_id)
                if produit:
                    produit_prix = produit.get("prix_moyen_kg")
                    produit_nom = produit.get("designation_clean") or produit.get("designation")
            elif fournisseur == "EUROCIEL":
                produit = eurociel_service.get_product_by_id(link.produit_id)
                if produit:
                    produit_prix = produit.get("prix_moyen")
                    produit_nom = produit.get("designation_clean") or produit.get("designation")

            if not produit_prix:
                skipped += 1
                continue

            # Calculer le nouveau prix (en centimes, arrondi)
            new_prix = int(float(produit_prix) * float(link.ratio) * 100)
            old_prix = ingredient.prix_unitaire

            # Mettre a jour seulement si different ou force
            if force or abs(new_prix - old_prix) > 1:
                ingredient.prix_unitaire = new_prix
                updated += 1
                price_changes.append({
                    "ingredient_id": ingredient.id,
                    "ingredient_name": ingredient.name,
                    "old_prix": old_prix,
                    "new_prix": new_prix,
                    "produit_nom": produit_nom,
                    "fournisseur": fournisseur,
                })
            else:
                skipped += 1

        except Exception as e:
            errors.append({"ingredient_id": link.ingredient_id, "error": str(e)})

    db.commit()

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "price_changes": price_changes,
    }


# =============================================================================
# Plats Endpoints
# =============================================================================

@router.get("/plats", response_model=List[PlatResponse], summary="Liste des plats")
def list_plats(
    category: Optional[RestaurantPlatCategory] = None,
    menus_only: bool = Query(False),
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Recupere les plats."""
    if menus_only:
        return service.get_menus()
    if category:
        return service.get_plats_by_category(category)
    return service.get_active_plats()


@router.post("/plats", response_model=PlatResponse, status_code=201, summary="Creer un plat")
def create_plat(
    data: PlatCreate,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Cree un nouveau plat."""
    try:
        payload = data.model_dump()
        if payload.get("ingredients"):
            payload["ingredients"] = [ing.model_dump() if hasattr(ing, "model_dump") else ing for ing in payload["ingredients"]]
        return service.create_plat(**payload)
    except InvalidPlatError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/plats/search", response_model=List[PlatResponse], summary="Rechercher plats")
def search_plats(
    q: str = Query(..., min_length=1, description="Terme de recherche"),
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Recherche plats par nom."""
    return service.search_plats(q)


@router.get("/plats/unprofitable", response_model=List[PlatResponse], summary="Plats non rentables")
def list_unprofitable_plats(
    threshold: int = Query(35, ge=0, le=100, description="Seuil food cost %"),
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Recupere les plats avec un food cost > seuil."""
    return service.get_unprofitable_plats(threshold)


@router.get("/plats/{plat_id}", response_model=PlatDetailResponse, summary="Detail d'un plat")
def get_plat(
    plat_id: int,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Recupere un plat avec ses ingredients."""
    try:
        plat = service.get_plat_with_ingredients(plat_id)
        # Build response with ingredient details
        ingredients = []
        for pi in plat.ingredients or []:
            ingredients.append({
                "id": pi.id,
                "ingredient_id": pi.ingredient_id,
                "ingredient_name": pi.ingredient.name if pi.ingredient else "",
                "quantite": pi.quantite,
                "cout_ligne": pi.cout_ligne,
                "notes": pi.notes,
            })
        return {
            "id": plat.id,
            "name": plat.name,
            "prix_vente": plat.prix_vente,
            "category": plat.category,
            "description": plat.description,
            "is_menu": plat.is_menu,
            "is_active": plat.is_active,
            "cout_total": plat.cout_total,
            "food_cost_ratio": plat.food_cost_ratio,
            "is_profitable": plat.is_profitable,
            "ingredients": ingredients,
        }
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")


@router.patch("/plats/{plat_id}", response_model=PlatResponse, summary="Modifier un plat")
def update_plat(
    plat_id: int,
    data: PlatUpdate,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Met a jour un plat."""
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return service.update_plat(plat_id, **update_data)
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidPlatError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/plats/{plat_id}", status_code=204, summary="Desactiver un plat")
def deactivate_plat(
    plat_id: int,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Desactive un plat."""
    try:
        service.deactivate_plat(plat_id)
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")


@router.put("/plats/{plat_id}/ingredients", response_model=PlatDetailResponse, summary="Definir ingredients d'un plat")
def set_plat_ingredients(
    plat_id: int,
    ingredients: List[PlatIngredientInput],
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Remplace tous les ingredients d'un plat."""
    try:
        plat = service.set_ingredients(
            plat_id,
            [ing.model_dump() for ing in ingredients]
        )
        # Build response
        ing_list = []
        for pi in plat.ingredients or []:
            ing_list.append({
                "id": pi.id,
                "ingredient_id": pi.ingredient_id,
                "ingredient_name": pi.ingredient.name if pi.ingredient else "",
                "quantite": pi.quantite,
                "cout_ligne": pi.cout_ligne,
                "notes": pi.notes,
            })
        return {
            "id": plat.id,
            "name": plat.name,
            "prix_vente": plat.prix_vente,
            "category": plat.category,
            "description": plat.description,
            "is_menu": plat.is_menu,
            "is_active": plat.is_active,
            "cout_total": plat.cout_total,
            "food_cost_ratio": plat.food_cost_ratio,
            "is_profitable": plat.is_profitable,
            "ingredients": ing_list,
        }
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidPlatError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plats/{plat_id}/ingredients", status_code=201, summary="Ajouter un ingredient a un plat")
def add_plat_ingredient(
    plat_id: int,
    data: PlatIngredientInput,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Ajoute un ingredient a un plat."""
    try:
        pi = service.add_ingredient(
            plat_id,
            data.ingredient_id,
            data.quantite,
            data.notes
        )
        return {"id": pi.id, "message": "Ingredient ajoute"}
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidPlatError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/plats/{plat_id}/ingredients/{ingredient_id}", status_code=204, summary="Retirer un ingredient")
def remove_plat_ingredient(
    plat_id: int,
    ingredient_id: int,
    service: RestaurantPlatService = Depends(get_plat_service)
):
    """Retire un ingredient d'un plat."""
    service.remove_ingredient(plat_id, ingredient_id)


# =============================================================================
# Stock Endpoints
# =============================================================================

@router.get("/stock", response_model=List[StockResponse], summary="Liste des stocks")
def list_stocks(
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Recupere tous les stocks."""
    stocks = service.get_all_stocks()
    result = []
    for s in stocks:
        prix_unitaire = s.ingredient.prix_unitaire if s.ingredient else 0
        valeur_stock = int(s.quantity * prix_unitaire) if prix_unitaire else 0
        result.append({
            "id": s.id,
            "ingredient_id": s.ingredient_id,
            "ingredient_name": s.ingredient.name if s.ingredient else "",
            "quantity": s.quantity,
            "dernier_prix_achat": prix_unitaire,
            "valeur_stock": valeur_stock,
            "is_low_stock": s.is_low,
        })
    return result


@router.get("/stock/low", summary="Alertes de stock bas")
def list_low_stock(
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Recupere les alertes de stock bas."""
    return service.get_stock_alerts()


@router.get("/stock/value", summary="Valeur totale du stock")
def get_stock_value(
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Calcule la valeur totale du stock."""
    return {"total_value": service.calculate_total_stock_value()}


@router.post("/stock/movement", status_code=201, summary="Enregistrer un mouvement")
def create_stock_movement(
    data: StockMovementCreate,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Enregistre un mouvement de stock (entree/sortie)."""
    try:
        if data.movement_type in [RestaurantStockMovementType.ENTREE, RestaurantStockMovementType.AJUSTEMENT]:
            movement = service.add_stock(
                ingredient_id=data.ingredient_id,
                quantite=data.quantite,
                movement_type=data.movement_type,
                reference=data.reference,
                notes=data.notes,
                cout_unitaire=data.cout_unitaire,
            )
        else:
            movement = service.remove_stock(
                ingredient_id=data.ingredient_id,
                quantite=data.quantite,
                movement_type=data.movement_type,
                reference=data.reference,
                notes=data.notes,
            )
        return {"id": movement.id, "message": "Mouvement enregistre"}
    except InvalidStockOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stock/adjust", status_code=201, summary="Ajuster le stock (inventaire)")
def adjust_stock(
    data: StockAdjustment,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Ajuste le stock a une nouvelle valeur."""
    try:
        movement = service.adjust_stock(
            ingredient_id=data.ingredient_id,
            nouvelle_quantite=data.nouvelle_quantite,
            notes=data.notes,
        )
        return {"id": movement.id, "message": "Stock ajuste"}
    except InvalidStockOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stock/{ingredient_id}", response_model=StockResponse, summary="Stock d'un ingredient")
def get_stock(
    ingredient_id: int,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Recupere le stock d'un ingredient."""
    try:
        s = service.get_stock(ingredient_id)
        # Calcul de la valeur du stock
        prix_unitaire = s.ingredient.prix_unitaire if s.ingredient else 0
        valeur_stock = int(s.quantity * prix_unitaire) if prix_unitaire else 0
        return {
            "id": s.id,
            "ingredient_id": s.ingredient_id,
            "ingredient_name": s.ingredient.name if s.ingredient else "",
            "quantity": s.quantity,
            "dernier_prix_achat": prix_unitaire,
            "valeur_stock": valeur_stock,
            "is_low_stock": s.is_low,
        }
    except StockNotFoundError:
        raise HTTPException(status_code=404, detail="Stock non trouve")


@router.get("/stock/{ingredient_id}/movements", summary="Historique mouvements")
def get_stock_movements(
    ingredient_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Recupere l'historique des mouvements d'un ingredient."""
    try:
        movements = service.get_movements(ingredient_id, start_date, end_date)
        return [
            {
                "id": m.id,
                "stock_id": m.stock_id,
                "type": m.type,
                "quantite": m.quantite,
                "quantite_avant": m.quantite_avant,
                "reference": m.reference,
                "notes": m.notes,
                "cout_unitaire": m.cout_unitaire,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in movements
        ]
    except StockNotFoundError:
        raise HTTPException(status_code=404, detail="Stock non trouve")


# --- Transfer Endpoints ---

@router.post("/stock/transfer", status_code=201, summary="Transfert epicerie vers restaurant")
def transfer_from_epicerie(
    data: StockTransferCreate,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """
    Transfere du stock depuis l'epicerie vers le restaurant.

    Utilise le lien principal ingredient-produit sauf si produit_id/fournisseur specifies.
    """
    try:
        movement = service.transfer_from_epicerie(
            ingredient_id=data.ingredient_id,
            quantite=data.quantite,
            produit_id=data.produit_id,
            fournisseur=data.fournisseur,
            notes=data.notes,
        )
        return {
            "id": movement.id,
            "message": "Transfert effectue",
            "ingredient_id": data.ingredient_id,
            "quantite": str(data.quantite),
        }
    except NoEpicerieLinkError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidStockOperationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stock/transfer/bulk", status_code=201, summary="Transferts multiples")
def bulk_transfer_from_epicerie(
    data: BulkStockTransfer,
    service: RestaurantStockService = Depends(get_stock_service)
):
    """Effectue plusieurs transferts en une seule requete."""
    transfers = [
        {
            "ingredient_id": t.ingredient_id,
            "quantite": t.quantite,
            "produit_id": t.produit_id,
            "fournisseur": t.fournisseur,
            "notes": t.notes,
        }
        for t in data.transfers
    ]
    movements = service.bulk_transfer_from_epicerie(transfers)
    return {
        "message": f"{len(movements)} transferts effectues",
        "count": len(movements),
        "ids": [m.id for m in movements],
    }


@router.post("/stock/auto-replenish", status_code=201, summary="Reappro auto depuis epicerie")
def auto_replenish_from_epicerie(
    ingredient_id: Optional[int] = Query(None, description="ID ingredient (tous si non specifie)"),
    service: RestaurantStockService = Depends(get_stock_service)
):
    """
    Reapprovisionne automatiquement les ingredients en dessous du seuil d'alerte.

    Transfere depuis l'epicerie la quantite manquante + 20% de marge.
    """
    movements = service.auto_replenish_from_epicerie(ingredient_id)
    return {
        "message": f"{len(movements)} ingredients reapprovisionnes",
        "count": len(movements),
        "ids": [m.id for m in movements],
    }


# =============================================================================
# Consumptions Endpoints
# =============================================================================

@router.get("/consumptions", summary="Liste des consommations")
def list_consumptions(
    start_date: date = Query(..., description="Date de debut"),
    end_date: date = Query(..., description="Date de fin"),
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Recupere les consommations pour une periode."""
    consumptions = service.get_consumptions_by_date(start_date, end_date)
    return [
        {
            "id": c.id,
            "plat_id": c.plat_id,
            "plat_name": c.plat.name if c.plat else "",
            "type": c.type,
            "quantite": c.quantite,
            "prix_vente": c.prix_vente,
            "cout": c.cout,
            "date": c.date,
            "notes": c.notes,
        }
        for c in consumptions
    ]


@router.post("/consumptions/sale", status_code=201, summary="Enregistrer une vente")
def record_sale(
    data: ConsumptionCreate,
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Enregistre une vente de plat."""
    try:
        consumption = service.record_sale(
            plat_id=data.plat_id,
            quantite=data.quantite,
            prix_vente=data.prix_vente,
            date_consumption=data.date_consumption,
            notes=data.notes,
            decrement_stock=data.decrement_stock,
        )
        return {"id": consumption.id, "message": "Vente enregistree"}
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidConsumptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/consumptions/loss", status_code=201, summary="Enregistrer une perte")
def record_loss(
    data: ConsumptionCreate,
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Enregistre une perte de plat."""
    try:
        consumption = service.record_loss(
            plat_id=data.plat_id,
            quantite=data.quantite,
            date_consumption=data.date_consumption,
            notes=data.notes,
            decrement_stock=data.decrement_stock,
        )
        return {"id": consumption.id, "message": "Perte enregistree"}
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidConsumptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/consumptions/staff-meal", status_code=201, summary="Enregistrer repas staff")
def record_staff_meal(
    data: ConsumptionCreate,
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Enregistre un repas staff."""
    try:
        consumption = service.record_staff_meal(
            plat_id=data.plat_id,
            quantite=data.quantite,
            date_consumption=data.date_consumption,
            notes=data.notes,
            decrement_stock=data.decrement_stock,
        )
        return {"id": consumption.id, "message": "Repas staff enregistre"}
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidConsumptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/consumptions/offered", status_code=201, summary="Enregistrer plat offert")
def record_offered(
    data: ConsumptionCreate,
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Enregistre un plat offert."""
    try:
        consumption = service.record_offert(
            plat_id=data.plat_id,
            quantite=data.quantite,
            date_consumption=data.date_consumption,
            notes=data.notes,
            decrement_stock=data.decrement_stock,
        )
        return {"id": consumption.id, "message": "Offert enregistre"}
    except PlatNotFoundError:
        raise HTTPException(status_code=404, detail="Plat non trouve")
    except InvalidConsumptionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/consumptions/summary", summary="Resume journalier")
def get_daily_summary(
    target_date: date = Query(..., description="Date cible"),
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Resume des consommations d'une journee."""
    return service.get_daily_summary(target_date)


@router.get("/consumptions/best-sellers", summary="Meilleurs ventes")
def get_best_sellers(
    start_date: date = Query(..., description="Date de debut"),
    end_date: date = Query(..., description="Date de fin"),
    limit: int = Query(10, ge=1, le=50),
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Recupere les plats les plus vendus."""
    return service.get_best_sellers(start_date, end_date, limit)


@router.get("/consumptions/losses", summary="Rapport des pertes")
def get_loss_report(
    start_date: date = Query(..., description="Date de debut"),
    end_date: date = Query(..., description="Date de fin"),
    service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Rapport sur les pertes."""
    return service.get_loss_report(start_date, end_date)


# =============================================================================
# Charges Endpoints
# =============================================================================

@router.get("/charges", response_model=List[ChargeResponse], summary="Liste des charges")
def list_charges(
    charge_type: Optional[RestaurantChargeType] = None,
    active_only: bool = Query(True),
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Recupere les charges."""
    if charge_type:
        return service.get_charges_by_type(charge_type, active_only)
    if active_only:
        return service.get_active_charges()
    return service.get_active_charges()


@router.post("/charges", response_model=ChargeResponse, status_code=201, summary="Creer une charge")
def create_charge(
    data: ChargeCreate,
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Cree une nouvelle charge."""
    try:
        return service.create_charge(**data.model_dump())
    except InvalidChargeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/charges/summary", summary="Resume des charges")
def get_charges_summary(
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Resume des charges par type."""
    return service.get_charges_summary()


@router.get("/charges/breakdown", summary="Ventilation des charges")
def get_charges_breakdown(
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Ventilation detaillee des charges."""
    return service.get_charges_breakdown()


@router.get("/charges/{charge_id}", response_model=ChargeResponse, summary="Detail d'une charge")
def get_charge(
    charge_id: int,
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Recupere une charge par ID."""
    try:
        return service.get_charge(charge_id)
    except ChargeNotFoundError:
        raise HTTPException(status_code=404, detail="Charge non trouvee")


@router.patch("/charges/{charge_id}", response_model=ChargeResponse, summary="Modifier une charge")
def update_charge(
    charge_id: int,
    data: ChargeUpdate,
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Met a jour une charge."""
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return service.update_charge(charge_id, **update_data)
    except ChargeNotFoundError:
        raise HTTPException(status_code=404, detail="Charge non trouvee")
    except InvalidChargeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/charges/{charge_id}", status_code=204, summary="Desactiver une charge")
def deactivate_charge(
    charge_id: int,
    service: RestaurantChargeService = Depends(get_charge_service)
):
    """Desactive une charge."""
    try:
        service.deactivate_charge(charge_id)
    except ChargeNotFoundError:
        raise HTTPException(status_code=404, detail="Charge non trouvee")


# =============================================================================
# Dashboard Endpoint
# =============================================================================

@router.get("/dashboard", summary="Dashboard restaurant")
def get_dashboard(
    target_date: Optional[date] = None,
    stock_service: RestaurantStockService = Depends(get_stock_service),
    charge_service: RestaurantChargeService = Depends(get_charge_service),
    consumption_service: RestaurantConsumptionService = Depends(get_consumption_service)
):
    """Recupere les KPIs du dashboard restaurant."""
    check_date = target_date or date.today()

    # Stock
    stock_value = stock_service.calculate_total_stock_value()
    stock_alerts = stock_service.get_stock_alerts()

    # Charges
    charges_summary = charge_service.get_charges_summary()

    # Consommations du jour
    daily_summary = consumption_service.get_daily_summary(check_date)

    return {
        "date": check_date,
        "stock": {
            "total_value": stock_value,
            "alerts_count": len(stock_alerts),
            "alerts": stock_alerts[:5],  # Top 5 alertes
        },
        "charges": {
            "monthly_total": charges_summary["total_mensuel"],
            "by_type": charges_summary["by_type"],
        },
        "daily": {
            "revenue": daily_summary["total_revenue"],
            "cost": daily_summary["total_cost"],
            "margin": daily_summary["margin"],
            "sales_count": daily_summary["ventes"]["count"],
            "losses_count": daily_summary["pertes"]["count"],
        },
    }
