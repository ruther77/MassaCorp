"""
Endpoints METRO pour MassaCorp API
Gestion des produits et factures fournisseur METRO

Endpoints:
- GET /metro/products: Liste des produits agrégés (catalogue)
- GET /metro/products/{id}: Détail d'un produit
- GET /metro/products/ean/{ean}: Produit par EAN
- GET /metro/factures: Liste des factures
- GET /metro/factures/{id}: Détail d'une facture avec lignes
- GET /metro/dashboard: KPIs et statistiques
- GET /metro/categories: Statistiques par catégorie
- POST /metro/import: Import des données JSON
- POST /metro/recalculate: Recalcul des agrégats
"""
from typing import List, Optional
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db_authenticated
from app.models import User
from app.services.metro import MetroService
from app.schemas.metro import (
    MetroProduitResponse,
    MetroProduitListResponse,
    MetroFactureResponse,
    MetroFactureListItem,
    MetroFactureListResponse,
    MetroSummary,
    MetroCategoryStats,
    MetroTvaStats,
    MetroDashboard,
    MetroImportResult,
)


router = APIRouter(prefix="/metro", tags=["METRO"])


def get_metro_service(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
) -> MetroService:
    """Dependency pour obtenir le service METRO"""
    return MetroService(db=db, tenant_id=current_user.tenant_id)


# ============================================
# Endpoints Produits
# ============================================

@router.get(
    "/products",
    response_model=MetroProduitListResponse,
    summary="Liste des produits METRO",
    description="Retourne la liste paginée des produits agrégés avec filtres"
)
def list_products(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(50, ge=1, le=1000, description="Produits par page"),
    q: Optional[str] = Query(None, description="Recherche par nom ou EAN"),
    famille: Optional[str] = Query(None, description="Filtrer par famille"),
    categorie: Optional[str] = Query(None, description="Filtrer par catégorie"),
    taux_tva: Optional[float] = Query(None, description="Filtrer par taux TVA"),
    sort_by: str = Query("montant_total", description="Colonne de tri"),
    sort_order: str = Query("desc", description="Ordre de tri (asc/desc)"),
    service: MetroService = Depends(get_metro_service),
):
    """
    Liste paginée des produits METRO agrégés.

    Tri possible sur:
    - montant_total (défaut)
    - prix_unitaire_moyen
    - quantite_unitaire_totale
    - nb_achats
    - designation
    """
    taux = Decimal(str(taux_tva)) if taux_tva is not None else None

    produits, total = service.get_produits(
        page=page,
        per_page=per_page,
        q=q,
        categorie=categorie,
        taux_tva=taux,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    pages = (total + per_page - 1) // per_page

    from decimal import Decimal
    return MetroProduitListResponse(
        items=[
            MetroProduitResponse(
                id=p.id,
                ean=p.ean,
                article_numero=p.article_numero,
                designation=p.nom_court or p.designation_brute,
                colisage_moyen=p.colisage_standard,
                unite="U",
                volume_unitaire=p.contenance_cl,
                quantite_colis_totale=p.quantite_totale_achetee / p.colisage_standard if p.colisage_standard > 0 else p.quantite_totale_achetee,
                quantite_unitaire_totale=p.quantite_totale_achetee,
                montant_total_ht=p.montant_total_achats,
                montant_total_tva=p.montant_total_achats * p.taux_tva / 100,
                montant_total=p.montant_total_achats * (1 + p.taux_tva / 100),
                nb_achats=p.nb_achats,
                prix_unitaire_moyen=p.prix_achat_unitaire or Decimal(0),
                prix_unitaire_min=p.prix_achat_unitaire or Decimal(0),
                prix_unitaire_max=p.prix_achat_unitaire or Decimal(0),
                prix_colis_moyen=p.prix_achat_colis or Decimal(0),
                taux_tva=p.taux_tva,
                categorie_id=None,
                famille=p.famille,
                categorie=p.categorie,
                sous_categorie=p.sous_categorie,
                regie=p.regie,
                vol_alcool=p.degre_alcool,
                premier_achat=None,
                dernier_achat=p.date_dernier_prix,
            )
            for p in produits
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/products/{produit_id}",
    response_model=MetroProduitResponse,
    summary="Détail d'un produit METRO",
)
def get_product(
    produit_id: int,
    service: MetroService = Depends(get_metro_service),
):
    """Retourne le détail d'un produit agrégé."""
    produit = service.get_produit(produit_id)
    if not produit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit non trouvé"
        )

    from decimal import Decimal
    p = produit
    return MetroProduitResponse(
        id=p.id,
        ean=p.ean,
        article_numero=p.article_numero,
        designation=p.nom_court or p.designation_brute,
        colisage_moyen=p.colisage_standard,
        unite="U",
        volume_unitaire=p.contenance_cl,
        quantite_colis_totale=p.quantite_totale_achetee / p.colisage_standard if p.colisage_standard > 0 else p.quantite_totale_achetee,
        quantite_unitaire_totale=p.quantite_totale_achetee,
        montant_total_ht=p.montant_total_achats,
        montant_total_tva=p.montant_total_achats * p.taux_tva / 100,
        montant_total=p.montant_total_achats * (1 + p.taux_tva / 100),
        nb_achats=p.nb_achats,
        prix_unitaire_moyen=p.prix_achat_unitaire or Decimal(0),
        prix_unitaire_min=p.prix_achat_unitaire or Decimal(0),
        prix_unitaire_max=p.prix_achat_unitaire or Decimal(0),
        prix_colis_moyen=p.prix_achat_colis or Decimal(0),
        taux_tva=p.taux_tva,
        categorie_id=None,
        famille=p.famille,
        categorie=p.categorie,
        sous_categorie=p.sous_categorie,
        regie=p.regie,
        vol_alcool=p.degre_alcool,
        premier_achat=None,
        dernier_achat=p.date_dernier_prix,
    )


@router.get(
    "/products/ean/{ean}",
    response_model=MetroProduitResponse,
    summary="Produit par EAN",
)
def get_product_by_ean(
    ean: str,
    service: MetroService = Depends(get_metro_service),
):
    """Retourne le détail d'un produit par son code EAN."""
    produit = service.get_produit_par_ean(ean)
    if not produit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit EAN {ean} non trouvé"
        )

    from decimal import Decimal
    p = produit
    return MetroProduitResponse(
        id=p.id,
        ean=p.ean,
        article_numero=p.article_numero,
        designation=p.nom_court or p.designation_brute,
        colisage_moyen=p.colisage_standard,
        unite="U",
        volume_unitaire=p.contenance_cl,
        quantite_colis_totale=p.quantite_totale_achetee / p.colisage_standard if p.colisage_standard > 0 else p.quantite_totale_achetee,
        quantite_unitaire_totale=p.quantite_totale_achetee,
        montant_total_ht=p.montant_total_achats,
        montant_total_tva=p.montant_total_achats * p.taux_tva / 100,
        montant_total=p.montant_total_achats * (1 + p.taux_tva / 100),
        nb_achats=p.nb_achats,
        prix_unitaire_moyen=p.prix_achat_unitaire or Decimal(0),
        prix_unitaire_min=p.prix_achat_unitaire or Decimal(0),
        prix_unitaire_max=p.prix_achat_unitaire or Decimal(0),
        prix_colis_moyen=p.prix_achat_colis or Decimal(0),
        taux_tva=p.taux_tva,
        categorie_id=None,
        famille=p.famille,
        categorie=p.categorie,
        sous_categorie=p.sous_categorie,
        regie=p.regie,
        vol_alcool=p.degre_alcool,
        premier_achat=None,
        dernier_achat=p.date_dernier_prix,
    )


# ============================================
# Historique des prix
# ============================================

@router.get(
    "/products/{produit_id}/price-history",
    summary="Historique des prix d'un produit",
)
def get_price_history(
    produit_id: int,
    limit: int = Query(100, ge=1, le=500, description="Nombre max d'entrées"),
    service: MetroService = Depends(get_metro_service),
):
    """
    Retourne l'historique des prix d'un produit.
    Utile pour visualiser l'évolution des prix dans le temps.
    """
    history = service.get_price_history(produit_id, limit)
    return {
        "produit_id": produit_id,
        "count": len(history),
        "history": history,
    }


@router.get(
    "/products/ean/{ean}/price-history",
    summary="Historique des prix par EAN",
)
def get_price_history_by_ean(
    ean: str,
    limit: int = Query(100, ge=1, le=500, description="Nombre max d'entrées"),
    service: MetroService = Depends(get_metro_service),
):
    """
    Retourne l'historique des prix d'un produit par son EAN.
    """
    history = service.get_price_history_by_ean(ean, limit)
    return {
        "ean": ean,
        "count": len(history),
        "history": history,
    }


# ============================================
# Endpoints Factures
# ============================================

@router.get(
    "/factures",
    response_model=MetroFactureListResponse,
    summary="Liste des factures METRO",
)
def list_factures(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    date_debut: Optional[date] = Query(None, description="Date de début"),
    date_fin: Optional[date] = Query(None, description="Date de fin"),
    service: MetroService = Depends(get_metro_service),
):
    """Liste paginée des factures METRO."""
    factures, total = service.get_factures(
        page=page,
        per_page=per_page,
        date_debut=date_debut,
        date_fin=date_fin,
    )

    pages = (total + per_page - 1) // per_page

    return MetroFactureListResponse(
        items=[
            MetroFactureListItem(
                id=f.id,
                numero=f.numero,
                date_facture=f.date_facture,
                magasin=f.magasin,
                total_ht=f.total_ht,
                total_tva=f.total_tva,
                total_ttc=f.total_ttc,
                nb_lignes=len(f.lignes) if f.lignes else 0,
                importee_le=f.importee_le,
            )
            for f in factures
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/factures/{facture_id}",
    response_model=MetroFactureResponse,
    summary="Détail d'une facture METRO",
)
def get_facture(
    facture_id: int,
    service: MetroService = Depends(get_metro_service),
):
    """Retourne le détail d'une facture avec ses lignes."""
    facture = service.get_facture(facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Facture non trouvée"
        )

    from app.schemas.metro import MetroLigneResponse
    from app.models.metro import get_categorie

    return MetroFactureResponse(
        id=facture.id,
        numero=facture.numero,
        date_facture=facture.date_facture,
        magasin=facture.magasin,
        total_ht=facture.total_ht,
        total_tva=facture.total_tva,
        total_ttc=facture.total_ttc,
        fichier_source=facture.fichier_source,
        importee_le=facture.importee_le,
        nb_lignes=len(facture.lignes),
        lignes=[
            MetroLigneResponse(
                id=l.id,
                facture_id=l.facture_id,
                ean=l.ean,
                article_numero=l.article_numero,
                designation=l.designation,
                colisage=l.colisage,
                quantite_colis=l.quantite_colis,
                quantite_unitaire=l.quantite_unitaire,
                prix_colis=l.prix_colis,
                prix_unitaire=l.prix_unitaire,
                montant_ht=l.montant_ht,
                volume_unitaire=l.volume_unitaire,
                unite=l.unite,
                taux_tva=l.taux_tva,
                code_tva=l.code_tva,
                montant_tva=l.montant_tva,
                regie=l.regie,
                vol_alcool=l.vol_alcool,
                categorie_id=l.categorie_id,
                categorie=get_categorie(l.regie),
            )
            for l in facture.lignes
        ],
    )


# ============================================
# Endpoints Dashboard & Stats
# ============================================

@router.get(
    "/summary",
    response_model=MetroSummary,
    summary="Résumé global METRO",
)
def get_summary(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne le résumé global des données METRO."""
    return service.get_summary()


@router.get(
    "/dashboard",
    response_model=MetroDashboard,
    summary="Dashboard METRO complet",
)
def get_dashboard(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne le dashboard complet avec KPIs, catégories et top produits."""
    return service.get_dashboard()


@router.get(
    "/stats/categories",
    response_model=List[MetroCategoryStats],
    summary="Statistiques par catégorie",
)
def get_category_stats(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne les statistiques par catégorie."""
    return service.get_stats_par_categorie()


@router.get(
    "/stats/tva",
    response_model=List[MetroTvaStats],
    summary="Statistiques par taux TVA",
)
def get_tva_stats(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne les statistiques par taux de TVA."""
    return service.get_stats_par_tva()


@router.get(
    "/categories",
    summary="Liste des catégories avec compteurs",
)
def get_categories(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne la liste des catégories avec le nombre de produits."""
    return service.get_categories()


@router.get(
    "/clients",
    summary="Statistiques par client/detenteur",
)
def get_clients_stats(
    service: MetroService = Depends(get_metro_service),
):
    """Retourne les statistiques par client (NOUTAM, INCONTOURNABLE, etc.)."""
    return service.get_stats_par_client()


# ============================================
# Endpoints Import
# ============================================

@router.post(
    "/import",
    response_model=MetroImportResult,
    summary="Importer des données METRO",
)
def import_data(
    json_path: str = Query(..., description="Chemin vers le fichier JSON"),
    service: MetroService = Depends(get_metro_service),
):
    """
    Importe les données depuis un fichier metro_data.json.

    Le fichier doit être au format généré par l'ETL METRO.
    """
    result = service.importer_depuis_json(json_path)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur d'import: {result.erreurs}"
        )
    return result


@router.post(
    "/recalculate",
    summary="Recalculer les agrégats",
)
def recalculate_aggregates(
    service: MetroService = Depends(get_metro_service),
):
    """
    Force le recalcul de tous les agrégats produits.

    Utile après une modification manuelle des données.
    """
    nb_produits = service.recalculer_agregats()
    return {
        "success": True,
        "nb_produits": nb_produits,
        "message": f"{nb_produits} produits agrégés recalculés"
    }
