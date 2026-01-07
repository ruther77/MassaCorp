"""
Endpoints EUROCIEL pour MassaCorp API
Gestion des produits et factures fournisseur EUROCIEL

Fournisseur: EUROCIEL (grossiste alimentaire africain/tropical)
SIRET: 510154313
TVA: FR55510154313

Endpoints:
- GET /eurociel/summary: Resume des donnees
- GET /eurociel/clients: Statistiques par client
- GET /eurociel/categories: Statistiques par categorie
- GET /eurociel/factures: Liste des factures
- GET /eurociel/factures/{id}: Detail d'une facture
- GET /eurociel/top-produits: Produits les plus achetes
- POST /eurociel/import: Import des donnees ETL
"""
from typing import Optional, List, Dict, Any
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db_authenticated
from app.models import User
from app.services.eurociel import EurocielService


router = APIRouter(prefix="/eurociel", tags=["EUROCIEL"])


def get_eurociel_service(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
) -> EurocielService:
    """Dependency pour obtenir le service EUROCIEL"""
    return EurocielService(db=db, tenant_id=current_user.tenant_id)


# ============================================
# Endpoints Statistiques
# ============================================

@router.get(
    "/summary",
    summary="Resume des donnees EUROCIEL",
)
def get_summary(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne le resume global des donnees EUROCIEL."""
    return service.get_summary()


@router.get(
    "/clients",
    summary="Statistiques par client",
)
def get_clients_stats(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne les statistiques par client (NOUTAM, INCONTOURNABLE)."""
    return service.get_stats_par_client()


@router.get(
    "/categories",
    summary="Statistiques par categorie",
)
def get_categories_stats(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne les statistiques par categorie de produit."""
    return service.get_stats_par_categorie()


@router.get(
    "/top-produits",
    summary="Top produits achetes",
)
def get_top_produits(
    limit: int = Query(20, ge=1, le=100, description="Nombre de produits"),
    service: EurocielService = Depends(get_eurociel_service),
) -> List[Dict[str, Any]]:
    """Retourne les produits les plus achetes par montant."""
    return service.get_top_produits(limit=limit)


# ============================================
# Endpoints Produits (agreges)
# ============================================

@router.get(
    "/products",
    summary="Liste des produits EUROCIEL agreges",
)
def list_products(
    page: int = Query(1, ge=1, description="Numero de page"),
    per_page: int = Query(50, ge=1, le=1000, description="Produits par page"),
    q: Optional[str] = Query(None, description="Recherche par designation"),
    categorie: Optional[str] = Query(None, description="Filtrer par categorie"),
    sort_by: str = Query("montant_total", description="Champ de tri"),
    sort_order: str = Query("desc", description="Ordre de tri (asc/desc)"),
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne la liste paginee des produits EUROCIEL agreges."""
    return service.get_products(
        page=page,
        per_page=per_page,
        search=q,
        categorie=categorie,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# ============================================
# Endpoints Factures
# ============================================

@router.get(
    "/factures",
    summary="Liste des factures EUROCIEL",
)
def list_factures(
    page: int = Query(1, ge=1, description="Numero de page"),
    per_page: int = Query(20, ge=1, le=100, description="Factures par page"),
    client: Optional[str] = Query(None, description="Filtrer par client"),
    type_document: Optional[str] = Query(None, description="FA=Facture, AV=Avoir"),
    date_debut: Optional[date] = Query(None, description="Date debut"),
    date_fin: Optional[date] = Query(None, description="Date fin"),
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne la liste paginee des factures EUROCIEL."""
    return service.get_factures(
        page=page,
        per_page=per_page,
        client=client,
        type_document=type_document,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.get(
    "/factures/{facture_id}",
    summary="Detail d'une facture",
)
def get_facture_detail(
    facture_id: int,
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne le detail d'une facture avec ses lignes."""
    facture = service.get_facture_detail(facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture {facture_id} non trouvee"
        )
    return facture


# ============================================
# Endpoints Import
# ============================================

@router.post(
    "/import",
    summary="Importer des factures",
)
def import_factures(
    factures: List[Dict[str, Any]],
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Importe une liste de factures extraites par ETL.

    Chaque facture doit contenir:
    - numero_facture: str
    - type_document: str (FA ou AV)
    - date_facture: str (YYYY-MM-DD)
    - client_nom: str
    - lignes: list
    """
    result = service.importer_depuis_etl(factures)
    # Recalculer les agregats apres import
    nb_produits = service.recalculer_agregats()
    result["nb_produits_agreges"] = nb_produits
    return result


@router.post(
    "/recalculer-agregats",
    summary="Recalculer les agregats produits",
)
def recalculer_agregats(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Recalcule les agregats produits a partir des lignes de factures.
    Utile apres modifications ou pour mise a jour manuelle.
    """
    nb_produits = service.recalculer_agregats()
    return {
        "success": True,
        "message": f"{nb_produits} produits agreges",
        "nb_produits": nb_produits
    }


# ============================================
# Endpoints Gestion EAN
# ============================================

@router.get(
    "/products/without-ean",
    summary="Produits sans EAN",
)
def get_products_without_ean(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Retourne la liste des produits sans code EAN.
    Ces produits peuvent etre enrichis manuellement avec leur EAN.
    """
    products = service.get_products_without_ean()
    return {
        "items": products,
        "total": len(products),
    }


@router.get(
    "/products/{product_id}",
    summary="Detail d'un produit",
)
def get_product_detail(
    product_id: int,
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """Retourne le detail d'un produit agrege."""
    product = service.get_produit_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit {product_id} non trouve"
        )
    return product


@router.put(
    "/products/{product_id}/ean",
    summary="Mettre a jour l'EAN d'un produit",
)
def update_product_ean(
    product_id: int,
    ean: Optional[str] = Query(None, min_length=8, max_length=14, description="Code EAN (8-14 caracteres)"),
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Met a jour le code EAN d'un produit EUROCIEL.

    L'EAN peut etre:
    - Un code EAN-8, EAN-13 ou UPC valide (8-14 caracteres)
    - None pour supprimer l'EAN existant
    """
    try:
        product = service.set_product_ean(product_id, ean)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produit {product_id} non trouve"
            )
        return {
            "success": True,
            "message": f"EAN mis a jour pour le produit {product_id}",
            "product_id": product_id,
            "ean": ean,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================
# Endpoints Synchronisation dim_produit
# ============================================

@router.post(
    "/sync-dim-produit",
    summary="Synchroniser vers dim_produit",
)
def sync_to_dim_produit(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Synchronise les produits EUROCIEL vers la table unifiee dim_produit.

    Pour chaque produit agrege:
    - Si EAN renseigne: cree ou met a jour dans dim_produit
    - Si EAN absent: cree avec un identifiant genere (EURO-XXXXXXXXXX)

    Cette operation permet d'unifier les produits EUROCIEL avec ceux de METRO/TAIYAT
    dans le referentiel produit commun.
    """
    stats = service.sync_to_dim_produit()
    return {
        "success": True,
        "message": f"{stats['created']} crees, {stats['updated']} mis a jour",
        "created": stats["created"],
        "updated": stats["updated"],
        "skipped": stats["skipped"],
    }


# ============================================
# Endpoints Catalogue Produits
# ============================================

@router.get(
    "/catalogue",
    summary="Liste des produits du catalogue",
)
def get_catalogue(
    page: int = Query(1, ge=1, description="Page"),
    per_page: int = Query(50, ge=1, le=500, description="Produits par page"),
    categorie: Optional[str] = Query(None, description="Filtrer par categorie"),
    origine: Optional[str] = Query(None, description="Filtrer par origine"),
    search: Optional[str] = Query(None, description="Recherche dans designation"),
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Retourne les produits du catalogue EUROCIEL.

    Le catalogue contient toutes les references disponibles chez EUROCIEL,
    meme celles non encore achetees.
    """
    return service.get_catalogue_produits(
        page=page,
        per_page=per_page,
        categorie=categorie,
        origine=origine,
        search=search
    )


@router.get(
    "/catalogue/stats",
    summary="Statistiques du catalogue",
)
def get_catalogue_stats(
    service: EurocielService = Depends(get_eurociel_service),
) -> Dict[str, Any]:
    """
    Retourne les statistiques du catalogue EUROCIEL:
    - Nombre total de references
    - Repartition par categorie
    - Repartition par origine
    """
    return service.get_catalogue_stats()


@router.get(
    "/catalogue/categories",
    summary="Categories du catalogue",
)
def get_catalogue_categories(
    service: EurocielService = Depends(get_eurociel_service),
) -> List[str]:
    """Retourne la liste des categories du catalogue."""
    return service.get_catalogue_categories()


@router.get(
    "/catalogue/origines",
    summary="Origines du catalogue",
)
def get_catalogue_origines(
    service: EurocielService = Depends(get_eurociel_service),
) -> List[str]:
    """Retourne la liste des pays d'origine du catalogue."""
    return service.get_catalogue_origines()
