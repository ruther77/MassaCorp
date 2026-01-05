"""
Endpoints Catalogue pour MassaCorp API
Gestion des produits avec donnees DWH

Endpoints:
- GET /catalog/products: Liste des produits paginee
- GET /catalog/products/{id}: Detail d'un produit
- GET /catalog/products/{id}/movements: Mouvements d'un produit
"""
from typing import List, Optional
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user, get_db_authenticated
from app.models import User


router = APIRouter(prefix="/catalog", tags=["Catalog"])


# ============================================
# Schemas
# ============================================

class ProduitListItem(BaseModel):
    produit_sk: int
    produit_id: int
    nom: str
    categorie_id: Optional[int] = None
    categorie_nom: Optional[str] = None
    famille: Optional[str] = None
    prix_achat: Optional[Decimal] = None
    prix_vente: Optional[Decimal] = None
    marge_pct: Optional[Decimal] = None
    stock_actuel: Optional[Decimal] = None
    seuil_alerte: Optional[Decimal] = None
    est_rupture: bool = False
    jours_stock: Optional[Decimal] = None

    class Config:
        from_attributes = True


class ProduitListResponse(BaseModel):
    items: List[ProduitListItem]
    total: int
    page: int
    per_page: int
    pages: int


class MouvementStock(BaseModel):
    date: datetime
    type_mouvement: str
    quantite: Decimal
    source: Optional[str] = None


class ProduitDetail(BaseModel):
    produit_sk: int
    produit_id: int
    nom: str
    categorie_id: Optional[int] = None
    categorie_nom: Optional[str] = None
    famille: Optional[str] = None
    sous_famille: Optional[str] = None
    prix_achat: Optional[Decimal] = None
    prix_vente: Optional[Decimal] = None
    tva_pct: Optional[Decimal] = None
    marge_unitaire: Optional[Decimal] = None
    marge_pct: Optional[Decimal] = None
    seuil_alerte: Optional[Decimal] = None
    # Stock data
    stock_actuel: Optional[Decimal] = None
    stock_valeur: Optional[Decimal] = None
    conso_moy_30j: Optional[Decimal] = None
    jours_stock: Optional[Decimal] = None
    est_rupture: bool = False
    est_surstock: bool = False
    # Trends
    ventes_30j: Optional[Decimal] = None
    trend_stock_pct: Optional[Decimal] = None
    # Mouvements recents
    mouvements_recents: List[MouvementStock] = []

    class Config:
        from_attributes = True


# ============================================
# Endpoints
# ============================================

@router.get(
    "/products",
    response_model=ProduitListResponse,
    summary="Liste des produits",
    description="Retourne la liste paginee des produits avec donnees stock"
)
def list_products(
    page: int = Query(1, ge=1, description="Numero de page"),
    per_page: int = Query(50, ge=1, le=200, description="Produits par page"),
    q: Optional[str] = Query(None, description="Recherche par nom"),
    famille: Optional[str] = Query(None, description="Filtrer par famille"),
    categorie_id: Optional[int] = Query(None, description="Filtrer par categorie"),
    stock_status: Optional[str] = Query(None, description="Statut stock: rupture, low, ok"),
    marge_filter: Optional[str] = Query(None, description="Filtre marge: low, medium, high"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """
    Liste paginee des produits avec informations stock.
    """
    # Build filters
    filters = []
    params = {"tenant_id": current_user.tenant_id}

    if q:
        filters.append("LOWER(p.nom) LIKE LOWER(:search)")
        params["search"] = f"%{q}%"

    if famille:
        filters.append("c.famille = :famille")
        params["famille"] = famille

    if categorie_id:
        filters.append("p.categorie_id = :categorie_id")
        params["categorie_id"] = categorie_id

    if stock_status == "rupture":
        filters.append("COALESCE(s.est_rupture, false) = true")
    elif stock_status == "low":
        filters.append("COALESCE(s.stock_quantite, 0) <= COALESCE(p.seuil_alerte, 10)")
    elif stock_status == "ok":
        filters.append("COALESCE(s.stock_quantite, 0) > COALESCE(p.seuil_alerte, 10)")

    if marge_filter == "low":
        filters.append("COALESCE(p.marge_pct, 0) < 20")
    elif marge_filter == "medium":
        filters.append("p.marge_pct >= 20 AND p.marge_pct <= 40")
    elif marge_filter == "high":
        filters.append("p.marge_pct > 40")

    where_clause = " AND ".join(filters) if filters else "1=1"

    # Count total
    count_query = text(f"""
        SELECT COUNT(*)
        FROM dwh.dim_produit p
        LEFT JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
        LEFT JOIN dwh.fait_stock_quotidien s ON p.produit_sk = s.produit_sk
            AND s.date_id = (SELECT MAX(date_id) FROM dwh.fait_stock_quotidien)
        WHERE p.tenant_id = :tenant_id
          AND p.est_actuel = true
          AND {where_clause}
    """)

    total = db.execute(count_query, params).scalar() or 0
    pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page

    # Query products
    query = text(f"""
        SELECT
            p.produit_sk,
            p.produit_id,
            p.nom,
            p.categorie_id,
            c.nom as categorie_nom,
            c.famille,
            p.prix_achat,
            p.prix_vente,
            p.marge_pct,
            COALESCE(s.stock_quantite, 0) as stock_actuel,
            p.seuil_alerte,
            COALESCE(s.est_rupture, false) as est_rupture,
            s.jours_stock
        FROM dwh.dim_produit p
        LEFT JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
        LEFT JOIN dwh.fait_stock_quotidien s ON p.produit_sk = s.produit_sk
            AND s.date_id = (SELECT MAX(date_id) FROM dwh.fait_stock_quotidien)
        WHERE p.tenant_id = :tenant_id
          AND p.est_actuel = true
          AND {where_clause}
        ORDER BY p.nom
        LIMIT :limit OFFSET :offset
    """)

    params["limit"] = per_page
    params["offset"] = offset

    result = db.execute(query, params)
    items = [
        ProduitListItem(
            produit_sk=row[0],
            produit_id=row[1],
            nom=row[2],
            categorie_id=row[3],
            categorie_nom=row[4],
            famille=row[5],
            prix_achat=row[6],
            prix_vente=row[7],
            marge_pct=row[8],
            stock_actuel=row[9],
            seuil_alerte=row[10],
            est_rupture=row[11],
            jours_stock=row[12],
        )
        for row in result.fetchall()
    ]

    return ProduitListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/products/{produit_sk}",
    response_model=ProduitDetail,
    summary="Detail d'un produit",
    description="Retourne les details complets d'un produit avec stock et mouvements"
)
def get_product_detail(
    produit_sk: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """
    Detail enrichi d'un produit avec:
    - Informations de base (prix, marge, categorie)
    - Donnees stock actuelles
    - Consommation moyenne 30j
    - Jours de stock restants
    - Mouvements recents (10 derniers)
    """
    # Get product details
    query = text("""
        SELECT
            p.produit_sk,
            p.produit_id,
            p.nom,
            p.categorie_id,
            c.nom as categorie_nom,
            c.famille,
            c.sous_famille,
            p.prix_achat,
            p.prix_vente,
            p.tva_pct,
            p.marge_unitaire,
            p.marge_pct,
            p.seuil_alerte,
            COALESCE(s.stock_quantite, 0) as stock_actuel,
            s.stock_valeur,
            s.conso_moy_30j,
            s.jours_stock,
            COALESCE(s.est_rupture, false) as est_rupture,
            COALESCE(s.est_surstock, false) as est_surstock
        FROM dwh.dim_produit p
        LEFT JOIN dwh.dim_categorie_produit c ON p.categorie_id = c.categorie_id
        LEFT JOIN dwh.fait_stock_quotidien s ON p.produit_sk = s.produit_sk
            AND s.date_id = (SELECT MAX(date_id) FROM dwh.fait_stock_quotidien)
        WHERE p.tenant_id = :tenant_id
          AND p.produit_sk = :produit_sk
          AND p.est_actuel = true
    """)

    result = db.execute(query, {"tenant_id": current_user.tenant_id, "produit_sk": produit_sk})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit non trouve"
        )

    # Get recent movements
    movements_query = text("""
        SELECT
            t.date_complete as date,
            m.type_mouvement,
            m.quantite,
            m.source
        FROM dwh.fait_mouvements_stock m
        JOIN dwh.dim_temps t ON m.date_id = t.date_id
        WHERE m.produit_sk = :produit_sk
        ORDER BY t.date_complete DESC
        LIMIT 10
    """)

    movements_result = db.execute(movements_query, {"produit_sk": produit_sk})
    mouvements = [
        MouvementStock(
            date=r[0],
            type_mouvement=r[1],
            quantite=r[2],
            source=r[3],
        )
        for r in movements_result.fetchall()
    ]

    return ProduitDetail(
        produit_sk=row[0],
        produit_id=row[1],
        nom=row[2],
        categorie_id=row[3],
        categorie_nom=row[4],
        famille=row[5],
        sous_famille=row[6],
        prix_achat=row[7],
        prix_vente=row[8],
        tva_pct=row[9],
        marge_unitaire=row[10],
        marge_pct=row[11],
        seuil_alerte=row[12],
        stock_actuel=row[13],
        stock_valeur=row[14],
        conso_moy_30j=row[15],
        jours_stock=row[16],
        est_rupture=row[17],
        est_surstock=row[18],
        mouvements_recents=mouvements,
    )


@router.get(
    "/families",
    response_model=List[str],
    summary="Liste des familles",
    description="Retourne la liste des familles de produits"
)
def list_families(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Liste des familles pour les filtres."""
    query = text("""
        SELECT DISTINCT c.famille
        FROM dwh.dim_categorie_produit c
        JOIN dwh.dim_produit p ON p.categorie_id = c.categorie_id
        WHERE p.tenant_id = :tenant_id
          AND p.est_actuel = true
        ORDER BY c.famille
    """)

    result = db.execute(query, {"tenant_id": current_user.tenant_id})
    return [row[0] for row in result.fetchall()]
