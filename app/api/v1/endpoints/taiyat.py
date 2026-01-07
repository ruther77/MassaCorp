"""
Endpoints TAIYAT pour MassaCorp API
Gestion des produits et factures fournisseur TAI YAT DISTRIBUTION

Endpoints:
- GET /taiyat/summary: Résumé des données
- GET /taiyat/clients: Statistiques par client
- GET /taiyat/provenances: Statistiques par pays d'origine
- GET /taiyat/factures: Liste des factures
- GET /taiyat/factures/{id}: Détail d'une facture
- GET /taiyat/top-produits: Produits les plus achetés
- POST /taiyat/import: Import des données ETL
"""
from typing import Optional, List, Dict, Any
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db_authenticated
from app.models import User
from app.services.taiyat import TaiyatService


router = APIRouter(prefix="/taiyat", tags=["TAIYAT"])


def get_taiyat_service(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
) -> TaiyatService:
    """Dependency pour obtenir le service TAIYAT"""
    return TaiyatService(db=db, tenant_id=current_user.tenant_id)


# ============================================
# Endpoints Statistiques
# ============================================

@router.get(
    "/summary",
    summary="Résumé des données TAIYAT",
)
def get_summary(
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne le résumé global des données TAIYAT."""
    return service.get_summary()


@router.get(
    "/clients",
    summary="Statistiques par client",
)
def get_clients_stats(
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne les statistiques par client (NOUTAM, INCONTOURNABLE)."""
    return service.get_stats_par_client()


@router.get(
    "/provenances",
    summary="Statistiques par pays d'origine",
)
def get_provenances_stats(
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne les statistiques par pays d'origine."""
    return service.get_stats_par_provenance()


@router.get(
    "/top-produits",
    summary="Top produits achetés",
)
def get_top_produits(
    limit: int = Query(20, ge=1, le=100, description="Nombre de produits"),
    service: TaiyatService = Depends(get_taiyat_service),
) -> List[Dict[str, Any]]:
    """Retourne les produits les plus achetés par montant."""
    return service.get_top_produits(limit=limit)


# ============================================
# Endpoints Produits (agrégés)
# ============================================

@router.get(
    "/products",
    summary="Liste des produits TAIYAT agrégés",
)
def list_products(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(50, ge=1, le=1000, description="Produits par page"),
    q: Optional[str] = Query(None, description="Recherche par désignation"),
    provenance: Optional[str] = Query(None, description="Filtrer par provenance"),
    sort_by: str = Query("montant_total", description="Champ de tri"),
    sort_order: str = Query("desc", description="Ordre de tri (asc/desc)"),
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne la liste paginée des produits TAIYAT agrégés."""
    return service.get_products(
        page=page,
        per_page=per_page,
        search=q,
        provenance=provenance,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# ============================================
# Endpoints Factures
# ============================================

@router.get(
    "/factures",
    summary="Liste des factures TAIYAT",
)
def list_factures(
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Factures par page"),
    client: Optional[str] = Query(None, description="Filtrer par client"),
    date_debut: Optional[date] = Query(None, description="Date début"),
    date_fin: Optional[date] = Query(None, description="Date fin"),
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne la liste paginée des factures TAIYAT."""
    return service.get_factures(
        page=page,
        per_page=per_page,
        client=client,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.get(
    "/factures/{facture_id}",
    summary="Détail d'une facture",
)
def get_facture_detail(
    facture_id: int,
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne le détail d'une facture avec ses lignes."""
    facture = service.get_facture_detail(facture_id)
    if not facture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture {facture_id} non trouvée"
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
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """
    Importe une liste de factures extraites par ETL.

    Chaque facture doit contenir:
    - numero_facture: str
    - date_facture: str (YYYY-MM-DD)
    - client_nom: str
    - lignes: list
    """
    result = service.importer_depuis_etl(factures)
    # Recalculer les agrégats après import
    nb_produits = service.recalculer_agregats()
    result["nb_produits_agreges"] = nb_produits
    return result


@router.post(
    "/recalculer-agregats",
    summary="Recalculer les agrégats produits",
)
def recalculer_agregats(
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """
    Recalcule les agrégats produits à partir des lignes de factures.
    Utile après modifications ou pour mise à jour manuelle.
    """
    nb_produits = service.recalculer_agregats()
    return {
        "success": True,
        "message": f"{nb_produits} produits agrégés",
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
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """
    Retourne la liste des produits sans code EAN.
    Ces produits peuvent être enrichis manuellement avec leur EAN.
    """
    products = service.get_products_without_ean()
    return {
        "items": products,
        "total": len(products),
    }


@router.get(
    "/products/{product_id}",
    summary="Détail d'un produit",
)
def get_product_detail(
    product_id: int,
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """Retourne le détail d'un produit agrégé."""
    product = service.get_produit_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produit {product_id} non trouvé"
        )
    return product


@router.put(
    "/products/{product_id}/ean",
    summary="Mettre à jour l'EAN d'un produit",
)
def update_product_ean(
    product_id: int,
    ean: Optional[str] = Query(None, min_length=8, max_length=14, description="Code EAN (8-14 caractères)"),
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """
    Met à jour le code EAN d'un produit TAIYAT.

    L'EAN peut être:
    - Un code EAN-8, EAN-13 ou UPC valide (8-14 caractères)
    - None pour supprimer l'EAN existant
    """
    try:
        product = service.set_product_ean(product_id, ean)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produit {product_id} non trouvé"
            )
        return {
            "success": True,
            "message": f"EAN mis à jour pour le produit {product_id}",
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
    service: TaiyatService = Depends(get_taiyat_service),
) -> Dict[str, Any]:
    """
    Synchronise les produits TAIYAT vers la table unifiée dim_produit.

    Pour chaque produit agrégé:
    - Si EAN renseigné: crée ou met à jour dans dim_produit
    - Si EAN absent: crée avec un identifiant généré (TAIY-XXXXXXXXXX)

    Cette opération permet d'unifier les produits TAIYAT avec ceux de METRO
    dans le référentiel produit commun.
    """
    stats = service.sync_to_dim_produit()
    return {
        "success": True,
        "message": f"{stats['created']} créés, {stats['updated']} mis à jour",
        "created": stats["created"],
        "updated": stats["updated"],
        "skipped": stats["skipped"],
    }
