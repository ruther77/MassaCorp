"""
API Endpoints Epicerie Domain.
Gestion des commandes fournisseurs.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.epicerie import SupplyOrder, SupplyOrderLine, SupplyOrderStatus
from app.repositories.epicerie.supply_order import SupplyOrderRepository, SupplyOrderLineRepository
from app.repositories.finance.vendor import FinanceVendorRepository
from app.schemas.epicerie import (
    SupplyOrderCreate,
    SupplyOrderUpdate,
    SupplyOrderRead,
    SupplyOrderDetail,
    SupplyOrderStats,
    SupplyOrderLineCreate,
    SupplyOrderLineUpdate,
    SupplyOrderLineRead,
    ConfirmOrderRequest,
    ReceiveOrderRequest,
    CancelOrderRequest,
    VendorSummary,
)
from app.schemas.base import paginated_response

router = APIRouter(prefix="/epicerie", tags=["Epicerie"])


# =============================================================================
# Helpers
# =============================================================================

def _order_to_read(order: SupplyOrder) -> dict:
    """Convertit un SupplyOrder en dict pour SupplyOrderRead."""
    vendor_summary = None
    if order.vendor:
        vendor_summary = {
            "id": order.vendor.id,
            "name": order.vendor.name,
            "code": order.vendor.code
        }

    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "vendor_id": order.vendor_id,
        "reference": order.reference,
        "date_commande": order.date_commande,
        "date_livraison_prevue": order.date_livraison_prevue,
        "date_livraison_reelle": order.date_livraison_reelle,
        "statut": order.statut,
        "montant_ht": order.montant_ht,
        "montant_tva": order.montant_tva,
        "montant_ttc": order.montant_ttc,
        "nb_lignes": order.nb_lignes,
        "nb_produits": order.nb_produits,
        "notes": order.notes,
        "created_by": order.created_by,
        "is_pending": order.is_pending,
        "is_delivered": order.is_delivered,
        "is_cancelled": order.is_cancelled,
        "is_late": order.is_late,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "vendor": vendor_summary,
    }


def _line_to_read(line: SupplyOrderLine) -> dict:
    """Convertit une SupplyOrderLine en dict pour SupplyOrderLineRead."""
    return {
        "id": line.id,
        "order_id": line.order_id,
        "produit_id": line.produit_id,
        "designation": line.designation,
        "quantity": line.quantity,
        "prix_unitaire": line.prix_unitaire,
        "received_quantity": line.received_quantity,
        "notes": line.notes,
        "montant_ligne": line.montant_ligne,
        "is_fully_received": line.is_fully_received,
        "is_partially_received": line.is_partially_received,
        "created_at": line.created_at,
        "updated_at": line.updated_at,
    }


# =============================================================================
# Commandes fournisseurs
# =============================================================================

@router.get("/orders", summary="Liste des commandes fournisseurs")
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    vendor_id: Optional[int] = Query(None),
    statut: Optional[SupplyOrderStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste paginee des commandes fournisseurs.
    Filtrable par vendor_id et statut.
    """
    repo = SupplyOrderRepository(db, current_user.tenant_id)

    if vendor_id:
        result = repo.get_by_vendor(vendor_id, page, page_size)
    elif statut:
        result = repo.get_by_status(statut, page, page_size)
    else:
        result = repo.get_all_with_vendor(page, page_size)

    items = [_order_to_read(order) for order in result.items]
    return paginated_response(items, result.page, result.page_size, result.total)


@router.get("/orders/late", summary="Commandes en retard de livraison")
def list_late_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste des commandes dont la livraison est en retard."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    orders = repo.get_late_deliveries()
    return {"data": [_order_to_read(order) for order in orders]}


@router.get("/orders/{order_id}", summary="Detail d'une commande")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recupere le detail complet d'une commande avec ses lignes."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get_with_lines(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    data = _order_to_read(order)
    data["lines"] = [_line_to_read(line) for line in order.lines]
    return {"data": data}


@router.post("/orders", status_code=status.HTTP_201_CREATED, summary="Creer une commande")
def create_order(
    order_data: SupplyOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cree une nouvelle commande fournisseur avec ses lignes.
    Calcule automatiquement les montants.
    """
    # Verifier que le fournisseur existe
    vendor_repo = FinanceVendorRepository(db, current_user.tenant_id)
    vendor = vendor_repo.get(order_data.vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournisseur non trouve"
        )

    # Creer la commande
    order_repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = order_repo.create({
        "vendor_id": order_data.vendor_id,
        "reference": order_data.reference,
        "date_commande": order_data.date_commande,
        "date_livraison_prevue": order_data.date_livraison_prevue,
        "notes": order_data.notes,
        "created_by": current_user.id,
        "statut": SupplyOrderStatus.EN_ATTENTE,
    })

    # Creer les lignes
    line_repo = SupplyOrderLineRepository(db)
    for line_data in order_data.lines:
        line_repo.create({
            "order_id": order.id,
            "produit_id": line_data.produit_id,
            "designation": line_data.designation,
            "quantity": line_data.quantity,
            "prix_unitaire": line_data.prix_unitaire,
            "notes": line_data.notes,
        })

    # Recalculer les totaux
    db.refresh(order)
    order.recalculate_totals()
    db.commit()
    db.refresh(order)

    # Recharger avec les lignes
    order = order_repo.get_with_lines(order.id)
    data = _order_to_read(order)
    data["lines"] = [_line_to_read(line) for line in order.lines]

    return {"data": data}


@router.put("/orders/{order_id}", summary="Modifier une commande")
def update_order(
    order_id: int,
    order_data: SupplyOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met a jour une commande fournisseur."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    # Ne pas modifier les commandes livrees ou annulees
    if order.statut in (SupplyOrderStatus.LIVREE, SupplyOrderStatus.ANNULEE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de modifier une commande {order.statut.value}"
        )

    update_data = order_data.model_dump(exclude_unset=True)
    repo.update(order_id, update_data)
    db.commit()

    order = repo.get_with_lines(order_id)
    data = _order_to_read(order)
    data["lines"] = [_line_to_read(line) for line in order.lines]

    return {"data": data}


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une commande")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Supprime une commande fournisseur.
    Seules les commandes en attente peuvent etre supprimees.
    """
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut != SupplyOrderStatus.EN_ATTENTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les commandes en attente peuvent etre supprimees"
        )

    repo.delete(order_id)
    db.commit()


# =============================================================================
# Actions sur commandes
# =============================================================================

@router.post("/orders/{order_id}/confirm", summary="Confirmer une commande")
def confirm_order(
    order_id: int,
    request: ConfirmOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirme une commande en attente."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut != SupplyOrderStatus.EN_ATTENTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les commandes en attente peuvent etre confirmees"
        )

    update_data = {"statut": SupplyOrderStatus.CONFIRMEE}
    if request.date_livraison_prevue:
        update_data["date_livraison_prevue"] = request.date_livraison_prevue

    repo.update(order_id, update_data)
    db.commit()

    order = repo.get_with_lines(order_id)
    return {"data": _order_to_read(order)}


@router.post("/orders/{order_id}/ship", summary="Marquer comme expediee")
def ship_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marque une commande confirmee comme expediee."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut != SupplyOrderStatus.CONFIRMEE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les commandes confirmees peuvent etre expediees"
        )

    repo.update(order_id, {"statut": SupplyOrderStatus.EXPEDIEE})
    db.commit()

    order = repo.get_with_lines(order_id)
    return {"data": _order_to_read(order)}


@router.post("/orders/{order_id}/receive", summary="Recevoir une commande")
def receive_order(
    order_id: int,
    request: ReceiveOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marque une commande comme livree.
    Optionnellement met a jour les quantites recues par ligne.
    """
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get_with_lines(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut not in (SupplyOrderStatus.CONFIRMEE, SupplyOrderStatus.EXPEDIEE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seules les commandes confirmees ou expediees peuvent etre recues"
        )

    # Mettre a jour les quantites recues si fournies
    if request.lines:
        line_repo = SupplyOrderLineRepository(db)
        for line_update in request.lines:
            line_id = line_update.get("line_id")
            received_qty = line_update.get("received_quantity")
            if line_id and received_qty is not None:
                line_repo.update(line_id, {"received_quantity": Decimal(str(received_qty))})
    else:
        # Reception complete par defaut
        line_repo = SupplyOrderLineRepository(db)
        for line in order.lines:
            line_repo.update(line.id, {"received_quantity": line.quantity})

    repo.update(order_id, {
        "statut": SupplyOrderStatus.LIVREE,
        "date_livraison_reelle": request.date_livraison_reelle
    })
    db.commit()

    order = repo.get_with_lines(order_id)
    data = _order_to_read(order)
    data["lines"] = [_line_to_read(line) for line in order.lines]

    return {"data": data}


@router.post("/orders/{order_id}/cancel", summary="Annuler une commande")
def cancel_order(
    order_id: int,
    request: CancelOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Annule une commande non livree."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut == SupplyOrderStatus.LIVREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'annuler une commande deja livree"
        )

    if order.statut == SupplyOrderStatus.ANNULEE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La commande est deja annulee"
        )

    update_data = {"statut": SupplyOrderStatus.ANNULEE}
    if request.raison:
        update_data["notes"] = f"[ANNULEE] {request.raison}\n{order.notes or ''}"

    repo.update(order_id, update_data)
    db.commit()

    order = repo.get_with_lines(order_id)
    return {"data": _order_to_read(order)}


# =============================================================================
# Lignes de commande
# =============================================================================

@router.post("/orders/{order_id}/lines", status_code=status.HTTP_201_CREATED, summary="Ajouter une ligne")
def add_order_line(
    order_id: int,
    line_data: SupplyOrderLineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ajoute une ligne a une commande existante."""
    order_repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = order_repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut not in (SupplyOrderStatus.EN_ATTENTE, SupplyOrderStatus.CONFIRMEE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'ajouter des lignes a cette commande"
        )

    line_repo = SupplyOrderLineRepository(db)
    line = line_repo.create({
        "order_id": order_id,
        "produit_id": line_data.produit_id,
        "designation": line_data.designation,
        "quantity": line_data.quantity,
        "prix_unitaire": line_data.prix_unitaire,
        "notes": line_data.notes,
    })

    # Recalculer les totaux
    db.refresh(order)
    order.recalculate_totals()
    db.commit()

    return {"data": _line_to_read(line)}


@router.put("/orders/{order_id}/lines/{line_id}", summary="Modifier une ligne")
def update_order_line(
    order_id: int,
    line_id: int,
    line_data: SupplyOrderLineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met a jour une ligne de commande."""
    order_repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = order_repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    line_repo = SupplyOrderLineRepository(db)
    line = line_repo.get(line_id)

    if not line or line.order_id != order_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ligne non trouvee"
        )

    update_data = line_data.model_dump(exclude_unset=True)
    line_repo.update(line_id, update_data)

    # Recalculer les totaux
    db.refresh(order)
    order.recalculate_totals()
    db.commit()

    line = line_repo.get(line_id)
    return {"data": _line_to_read(line)}


@router.delete("/orders/{order_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer une ligne")
def delete_order_line(
    order_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime une ligne de commande."""
    order_repo = SupplyOrderRepository(db, current_user.tenant_id)
    order = order_repo.get(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Commande non trouvee"
        )

    if order.statut not in (SupplyOrderStatus.EN_ATTENTE, SupplyOrderStatus.CONFIRMEE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de supprimer des lignes de cette commande"
        )

    line_repo = SupplyOrderLineRepository(db)
    line = line_repo.get(line_id)

    if not line or line.order_id != order_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ligne non trouvee"
        )

    line_repo.delete(line_id)

    # Recalculer les totaux
    db.refresh(order)
    order.recalculate_totals()
    db.commit()


# =============================================================================
# Statistiques
# =============================================================================

@router.get("/orders/stats/by-vendor/{vendor_id}", summary="Stats par fournisseur")
def get_vendor_stats(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Statistiques des commandes pour un fournisseur."""
    repo = SupplyOrderRepository(db, current_user.tenant_id)
    stats = repo.get_stats_by_vendor(vendor_id)
    return {"data": stats}
