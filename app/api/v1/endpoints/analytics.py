"""
Endpoints Analytics pour MassaCorp API
Data Warehouse - Requetes analytiques avec RLS

Endpoints disponibles:
- /analytics/categories: Liste des categories produits
- /analytics/stock/valorisation: Valorisation du stock par categorie
- /analytics/stock/mouvements: Mouvements de stock
- /analytics/ventes/restaurant: CA restaurant par periode
- /analytics/depenses/synthese: Synthese des depenses
- /analytics/dashboard: KPIs globaux
"""
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.dependencies import (
    get_current_user,
    get_db_authenticated,
)
from app.models import User


router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ============================================
# Schemas
# ============================================

class CategorieRead(BaseModel):
    categorie_id: int
    code: str
    nom: str
    famille: str
    categorie: str
    sous_categorie: Optional[str] = None
    tva_defaut: Decimal
    est_ingredient_resto: bool = False
    priorite_ingredient: int = 0

    class Config:
        from_attributes = True


class StockValorisationItem(BaseModel):
    date: date
    famille: str
    categorie: str
    quantite_totale: Decimal
    valeur_totale: Decimal
    nb_ruptures: int
    rotation_moyenne: Optional[Decimal] = None


class MouvementStockItem(BaseModel):
    date: date
    produit: str
    type_mouvement: str
    quantite: Decimal
    valeur: Optional[Decimal] = None


class VenteRestaurantItem(BaseModel):
    date: date
    canal: Optional[str] = None
    nb_plats: int
    ca_ttc: Decimal
    ca_ht: Optional[Decimal] = None
    marge_brute: Optional[Decimal] = None


class DepenseSyntheseItem(BaseModel):
    annee: int
    mois: int
    annee_mois: str
    centre_cout: Optional[str] = None
    type_cout: Optional[str] = None
    total_ht: Decimal
    total_ttc: Decimal
    budget_mensuel: Optional[Decimal] = None
    execution_pct: Optional[Decimal] = None


class TopProduitItem(BaseModel):
    produit: str
    famille: str
    categorie: str
    volume_vendu: Decimal
    ca_total: Decimal
    marge_totale: Decimal
    marge_pct: Optional[Decimal] = None


class TopPlatItem(BaseModel):
    plat: str
    categorie: Optional[str] = None
    nb_vendus: int
    ca_ttc: Decimal
    marge_brute: Decimal
    food_cost_pct: Optional[Decimal] = None
    rang_marge: int
    rang_volume: int


class DashboardKPIs(BaseModel):
    # Stock
    valeur_stock_total: Decimal = Field(default=Decimal("0"))
    nb_produits_rupture: int = 0
    rotation_moyenne: Optional[Decimal] = None

    # Ventes restaurant (30 derniers jours)
    ca_30j: Decimal = Field(default=Decimal("0"))
    nb_plats_vendus_30j: int = 0
    marge_brute_30j: Decimal = Field(default=Decimal("0"))
    food_cost_moyen: Optional[Decimal] = None

    # Depenses (mois courant)
    depenses_mois: Decimal = Field(default=Decimal("0"))

    # Categories
    nb_categories: int = 0


# ============================================
# Endpoints Categories
# ============================================

@router.get(
    "/categories",
    response_model=List[CategorieRead],
    summary="Liste des categories",
    description="Recupere toutes les categories produits"
)
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    famille: Optional[str] = Query(None, description="Filtrer par famille"),
    ingredients_only: bool = Query(False, description="Uniquement les ingredients restaurant")
):
    """
    Retourne les categories produits.
    Table partagee entre tous les tenants.
    """
    query = """
        SELECT
            categorie_id, code, nom, famille, categorie, sous_categorie,
            tva_defaut, est_ingredient_resto, priorite_ingredient
        FROM dwh.dim_categorie_produit
        WHERE actif = TRUE
    """

    params = {}

    if famille:
        query += " AND famille = :famille"
        params["famille"] = famille

    if ingredients_only:
        query += " AND est_ingredient_resto = TRUE"

    query += " ORDER BY ordre_famille, ordre_categorie"

    result = db.execute(text(query), params)

    return [
        CategorieRead(
            categorie_id=row.categorie_id,
            code=row.code,
            nom=row.nom,
            famille=row.famille,
            categorie=row.categorie,
            sous_categorie=row.sous_categorie,
            tva_defaut=row.tva_defaut,
            est_ingredient_resto=row.est_ingredient_resto,
            priorite_ingredient=row.priorite_ingredient
        )
        for row in result.fetchall()
    ]


# ============================================
# Endpoints Stock
# ============================================

@router.get(
    "/stock/valorisation",
    response_model=List[StockValorisationItem],
    summary="Valorisation du stock",
    description="Valorisation du stock par categorie et par date"
)
def get_stock_valorisation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    date_debut: Optional[date] = Query(None, description="Date de debut"),
    date_fin: Optional[date] = Query(None, description="Date de fin")
):
    """
    Retourne la valorisation du stock par categorie.
    Vue pre-agregee pour performance optimale.
    """
    # Dates par defaut: 30 derniers jours
    if date_fin is None:
        date_fin = date.today()
    if date_debut is None:
        date_debut = date_fin - timedelta(days=30)

    result = db.execute(text("""
        SELECT
            date_complete, famille, categorie,
            quantite_totale, valeur_totale, nb_ruptures, rotation_moyenne
        FROM dwh.v_valorisation_stock
        WHERE date_complete BETWEEN :date_debut AND :date_fin
        ORDER BY date_complete DESC, famille, categorie
    """), {"date_debut": date_debut, "date_fin": date_fin})

    return [
        StockValorisationItem(
            date=row.date_complete,
            famille=row.famille,
            categorie=row.categorie,
            quantite_totale=row.quantite_totale or Decimal("0"),
            valeur_totale=row.valeur_totale or Decimal("0"),
            nb_ruptures=row.nb_ruptures or 0,
            rotation_moyenne=row.rotation_moyenne
        )
        for row in result.fetchall()
    ]


@router.get(
    "/stock/mouvements",
    response_model=List[MouvementStockItem],
    summary="Mouvements de stock",
    description="Historique des mouvements de stock"
)
def get_stock_mouvements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    date_debut: Optional[date] = Query(None, description="Date de debut"),
    date_fin: Optional[date] = Query(None, description="Date de fin"),
    type_mouvement: Optional[str] = Query(None, description="Type: ENTREE, SORTIE, INVENTAIRE"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre max de resultats")
):
    """
    Retourne les mouvements de stock.
    Filtre par date et type de mouvement.
    """
    if date_fin is None:
        date_fin = date.today()
    if date_debut is None:
        date_debut = date_fin - timedelta(days=30)

    query = """
        SELECT
            t.date_complete, p.nom AS produit, m.type_mouvement,
            m.quantite * m.sens AS quantite, m.valeur_mouvement
        FROM dwh.fait_mouvements_stock m
        JOIN dwh.dim_temps t ON m.date_id = t.date_id
        JOIN dwh.dim_produit p ON m.produit_sk = p.produit_sk
        WHERE t.date_complete BETWEEN :date_debut AND :date_fin
    """

    params = {"date_debut": date_debut, "date_fin": date_fin, "limit": limit}

    if type_mouvement:
        query += " AND m.type_mouvement = :type_mouvement"
        params["type_mouvement"] = type_mouvement

    query += " ORDER BY t.date_complete DESC, m.mouvement_id DESC LIMIT :limit"

    result = db.execute(text(query), params)

    return [
        MouvementStockItem(
            date=row.date_complete,
            produit=row.produit,
            type_mouvement=row.type_mouvement,
            quantite=row.quantite or Decimal("0"),
            valeur=row.valeur_mouvement
        )
        for row in result.fetchall()
    ]


# ============================================
# Endpoints Ventes Restaurant
# ============================================

@router.get(
    "/ventes/restaurant",
    response_model=List[VenteRestaurantItem],
    summary="CA Restaurant",
    description="Chiffre d'affaires restaurant par jour et canal"
)
def get_ventes_restaurant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    date_debut: Optional[date] = Query(None, description="Date de debut"),
    date_fin: Optional[date] = Query(None, description="Date de fin")
):
    """
    Retourne le CA restaurant agrege par jour.
    Vue pre-agregee pour performance optimale.
    """
    if date_fin is None:
        date_fin = date.today()
    if date_debut is None:
        date_debut = date_fin - timedelta(days=30)

    result = db.execute(text("""
        SELECT
            date_complete, canal, nb_plats, ca_ttc, ca_ht, marge_brute
        FROM dwh.v_ca_quotidien_restaurant
        WHERE date_complete BETWEEN :date_debut AND :date_fin
        ORDER BY date_complete DESC, canal
    """), {"date_debut": date_debut, "date_fin": date_fin})

    return [
        VenteRestaurantItem(
            date=row.date_complete,
            canal=row.canal,
            nb_plats=int(row.nb_plats or 0),
            ca_ttc=row.ca_ttc or Decimal("0"),
            ca_ht=row.ca_ht,
            marge_brute=row.marge_brute
        )
        for row in result.fetchall()
    ]


@router.get(
    "/ventes/top-plats",
    response_model=List[TopPlatItem],
    summary="Top plats vendus",
    description="Classement des plats par marge et volume"
)
def get_top_plats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    limit: int = Query(10, ge=1, le=100, description="Nombre de plats")
):
    """
    Retourne le classement des plats par marge.
    Vue pre-agregee avec ranking.
    """
    result = db.execute(text("""
        SELECT
            plat, categorie, nb_vendus, ca_ttc, marge_brute,
            food_cost_pct, rang_marge, rang_volume
        FROM dwh.v_top_plats_restaurant
        ORDER BY rang_marge
        LIMIT :limit
    """), {"limit": limit})

    return [
        TopPlatItem(
            plat=row.plat,
            categorie=row.categorie,
            nb_vendus=int(row.nb_vendus or 0),
            ca_ttc=row.ca_ttc or Decimal("0"),
            marge_brute=row.marge_brute or Decimal("0"),
            food_cost_pct=row.food_cost_pct,
            rang_marge=row.rang_marge,
            rang_volume=row.rang_volume
        )
        for row in result.fetchall()
    ]


# ============================================
# Endpoints Depenses
# ============================================

@router.get(
    "/depenses/synthese",
    response_model=List[DepenseSyntheseItem],
    summary="Synthese des depenses",
    description="Depenses par centre de cout et mois"
)
def get_depenses_synthese(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    annee: Optional[int] = Query(None, description="Annee"),
    mois: Optional[int] = Query(None, ge=1, le=12, description="Mois")
):
    """
    Retourne la synthese des depenses par centre de cout.
    Vue pre-agregee avec suivi budgetaire.
    """
    query = """
        SELECT
            annee, mois, annee_mois, centre_cout, type_cout,
            total_ht, total_ttc, budget_mensuel, execution_pct
        FROM dwh.v_synthese_depenses
        WHERE tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
    """

    params = {}

    if annee:
        query += " AND annee = :annee"
        params["annee"] = annee

    if mois:
        query += " AND mois = :mois"
        params["mois"] = mois

    query += " ORDER BY annee DESC, mois DESC, centre_cout"

    result = db.execute(text(query), params)

    return [
        DepenseSyntheseItem(
            annee=row.annee,
            mois=row.mois,
            annee_mois=row.annee_mois,
            centre_cout=row.centre_cout,
            type_cout=row.type_cout,
            total_ht=row.total_ht or Decimal("0"),
            total_ttc=row.total_ttc or Decimal("0"),
            budget_mensuel=row.budget_mensuel,
            execution_pct=row.execution_pct
        )
        for row in result.fetchall()
    ]


# ============================================
# Endpoints Top Produits
# ============================================

@router.get(
    "/produits/top",
    response_model=List[TopProduitItem],
    summary="Top produits epicerie",
    description="Classement des produits par CA et marge"
)
def get_top_produits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    limit: int = Query(10, ge=1, le=100, description="Nombre de produits")
):
    """
    Retourne le classement des produits epicerie.
    Vue pre-agregee avec calcul de marge.
    """
    result = db.execute(text("""
        SELECT
            produit, famille, categorie, volume_vendu, ca_total, marge_totale, marge_pct
        FROM dwh.v_top_produits_epicerie
        ORDER BY ca_total DESC
        LIMIT :limit
    """), {"limit": limit})

    return [
        TopProduitItem(
            produit=row.produit,
            famille=row.famille,
            categorie=row.categorie,
            volume_vendu=row.volume_vendu or Decimal("0"),
            ca_total=row.ca_total or Decimal("0"),
            marge_totale=row.marge_totale or Decimal("0"),
            marge_pct=row.marge_pct
        )
        for row in result.fetchall()
    ]


# ============================================
# Dashboard KPIs
# ============================================

@router.get(
    "/dashboard",
    response_model=DashboardKPIs,
    summary="KPIs Dashboard",
    description="Indicateurs cles pour le dashboard principal"
)
def get_dashboard_kpis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated)
):
    """
    Retourne les KPIs principaux pour le dashboard.
    Agrege les donnees des differentes vues DWH.
    """
    today = date.today()
    date_30j = today - timedelta(days=30)
    date_id_today = int(today.strftime("%Y%m%d"))
    date_id_30j = int(date_30j.strftime("%Y%m%d"))

    # Nombre de categories
    cat_result = db.execute(text("SELECT COUNT(*) FROM dwh.dim_categorie_produit WHERE actif = TRUE"))
    nb_categories = cat_result.scalar() or 0

    # Stock (dernier snapshot disponible)
    stock_result = db.execute(text("""
        SELECT
            SUM(stock_valeur) AS valeur_total,
            SUM(CASE WHEN est_rupture THEN 1 ELSE 0 END) AS nb_ruptures,
            AVG(jours_stock) AS rotation_moy
        FROM dwh.fait_stock_quotidien
        WHERE date_id = (SELECT MAX(date_id) FROM dwh.fait_stock_quotidien)
    """))
    stock_row = stock_result.fetchone()

    # Ventes restaurant 30j
    ventes_result = db.execute(text("""
        SELECT
            SUM(ca_ttc) AS ca_total,
            SUM(quantite) AS nb_plats,
            SUM(marge_brute) AS marge_total,
            AVG(cout_matiere / NULLIF(ca_ttc, 0) * 100) AS food_cost_moyen
        FROM dwh.fait_ventes_restaurant
        WHERE date_id BETWEEN :date_30j AND :date_today
    """), {"date_30j": date_id_30j, "date_today": date_id_today})
    ventes_row = ventes_result.fetchone()

    # Depenses mois courant
    mois_debut = date(today.year, today.month, 1)
    date_id_mois = int(mois_debut.strftime("%Y%m%d"))

    depenses_result = db.execute(text("""
        SELECT SUM(montant_ttc) AS total
        FROM dwh.fait_depenses
        WHERE date_id >= :date_mois
    """), {"date_mois": date_id_mois})
    depenses_total = depenses_result.scalar() or Decimal("0")

    return DashboardKPIs(
        valeur_stock_total=stock_row.valeur_total if stock_row and stock_row.valeur_total else Decimal("0"),
        nb_produits_rupture=int(stock_row.nb_ruptures) if stock_row and stock_row.nb_ruptures else 0,
        rotation_moyenne=stock_row.rotation_moy if stock_row else None,
        ca_30j=ventes_row.ca_total if ventes_row and ventes_row.ca_total else Decimal("0"),
        nb_plats_vendus_30j=int(ventes_row.nb_plats) if ventes_row and ventes_row.nb_plats else 0,
        marge_brute_30j=ventes_row.marge_total if ventes_row and ventes_row.marge_total else Decimal("0"),
        food_cost_moyen=ventes_row.food_cost_moyen if ventes_row else None,
        depenses_mois=depenses_total,
        nb_categories=nb_categories
    )


# ============================================
# Classification automatique des produits
# ============================================

class ClassificationResult(BaseModel):
    total: int
    classified: int
    unclassified: int
    classification_rate: float
    categories: Dict[str, int]
    unclassified_samples: List[str] = []

    class Config:
        from_attributes = True


@router.post(
    "/classify-products",
    response_model=ClassificationResult,
    summary="Classifier les produits automatiquement",
    description="Classifie tous les produits du tenant dans les categories DWH"
)
def classify_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated)
):
    """
    Lance la classification automatique des produits.
    Utilise des patterns regex pour assigner les categories.
    Necessite droits admin.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits administrateur requis"
        )

    from app.services.product_classifier import classify_all_products

    result = classify_all_products(db, tenant_id=current_user.tenant_id)

    return ClassificationResult(**result)


@router.get(
    "/classify-products/preview",
    summary="Apercu de la classification",
    description="Montre un apercu de la classification sans modifier la base"
)
def preview_classification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
    limit: int = Query(10, ge=1, le=100, description="Nombre d'exemples par categorie")
):
    """
    Affiche un apercu de la classification sans sauvegarder.
    """
    from app.services.product_classifier import classify_product

    # Recuperer quelques produits
    result = db.execute(text("""
        SELECT id, nom FROM public.produits
        WHERE tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::bigint
        LIMIT 500
    """))

    products = [{"id": row[0], "nom": row[1]} for row in result.fetchall()]

    # Classifier
    preview = {}
    for p in products:
        category, pattern = classify_product(p['nom'])
        if category not in preview:
            preview[category] = []
        if len(preview[category]) < limit:
            preview[category].append({
                "id": p['id'],
                "nom": p['nom'],
                "pattern": pattern
            })

    return {
        "total_products": len(products),
        "preview": preview
    }
