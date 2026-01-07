"""
Endpoints OTHER pour MassaCorp API
Gestion des produits fournisseurs divers (Cash & Carry, etc.)

Endpoints:
- GET /other/products: Liste des produits OTHER
- GET /other/products/{id}: Detail d'un produit
- GET /other/summary: Resume global OTHER
- POST /other/products: Creer un produit
- PUT /other/products/{id}: Modifier un produit
- DELETE /other/products/{id}: Supprimer un produit
"""
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.dependencies import get_current_user, get_db_authenticated
from app.models import User


router = APIRouter(prefix="/other", tags=["OTHER"])


# ============================================
# Pydantic Schemas
# ============================================

class OtherProduitResponse(BaseModel):
    id: int
    designation: str
    designation_clean: str | None
    famille: str | None
    categorie: str | None
    sous_categorie: str | None
    colisage: int
    unite: str | None
    contenance: str | None
    prix_unitaire: float
    prix_colis: float | None
    fournisseur_nom: str | None
    fournisseur_type: str | None
    notes: str | None
    actif: bool


class OtherProduitListResponse(BaseModel):
    items: List[OtherProduitResponse]
    total: int
    page: int
    per_page: int
    pages: int


class OtherSummary(BaseModel):
    nb_produits: int
    nb_produits_actifs: int
    nb_fournisseurs: int
    total_valeur_catalogue: float


class OtherProduitCreate(BaseModel):
    designation: str
    famille: str | None = None
    categorie: str | None = None
    sous_categorie: str | None = None
    colisage: int = 1
    unite: str | None = "U"
    contenance: str | None = None
    prix_unitaire: float = 0
    prix_colis: float | None = None
    fournisseur_nom: str | None = None
    fournisseur_type: str | None = "CASH_CARRY"
    notes: str | None = None


class OtherProduitUpdate(BaseModel):
    designation: str | None = None
    famille: str | None = None
    categorie: str | None = None
    sous_categorie: str | None = None
    colisage: int | None = None
    unite: str | None = None
    contenance: str | None = None
    prix_unitaire: float | None = None
    prix_colis: float | None = None
    fournisseur_nom: str | None = None
    fournisseur_type: str | None = None
    notes: str | None = None
    actif: bool | None = None


# ============================================
# Endpoints Produits
# ============================================

@router.get(
    "/products",
    response_model=OtherProduitListResponse,
    summary="Liste des produits OTHER",
    description="Retourne la liste paginee des produits fournisseurs divers"
)
def list_products(
    page: int = Query(1, ge=1, description="Numero de page"),
    per_page: int = Query(50, ge=1, le=1000, description="Produits par page"),
    q: Optional[str] = Query(None, description="Recherche par nom"),
    famille: Optional[str] = Query(None, description="Filtrer par famille"),
    categorie: Optional[str] = Query(None, description="Filtrer par categorie"),
    fournisseur: Optional[str] = Query(None, description="Filtrer par fournisseur"),
    actif_only: bool = Query(True, description="Produits actifs seulement"),
    sort_by: str = Query("designation", description="Colonne de tri"),
    sort_order: str = Query("asc", description="Ordre de tri (asc/desc)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Liste paginee des produits OTHER."""
    # Build query
    conditions = ["tenant_id = :tenant_id"]
    params = {"tenant_id": current_user.tenant_id}

    if actif_only:
        conditions.append("actif = true")

    if q:
        conditions.append("(LOWER(designation) LIKE :search OR LOWER(designation_clean) LIKE :search)")
        params["search"] = f"%{q.lower()}%"

    if famille:
        conditions.append("LOWER(famille) = :famille")
        params["famille"] = famille.lower()

    if categorie:
        conditions.append("LOWER(categorie) = :categorie")
        params["categorie"] = categorie.lower()

    if fournisseur:
        conditions.append("LOWER(fournisseur_nom) LIKE :fournisseur")
        params["fournisseur"] = f"%{fournisseur.lower()}%"

    where_clause = " AND ".join(conditions)

    # Validate sort column
    valid_sorts = ["designation", "prix_unitaire", "prix_colis", "famille", "categorie", "fournisseur_nom"]
    if sort_by not in valid_sorts:
        sort_by = "designation"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    # Count total
    count_query = text(f"SELECT COUNT(*) FROM dwh.other_produit_agregat WHERE {where_clause}")
    total = db.execute(count_query, params).scalar()

    # Get paginated results
    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset

    query = text(f"""
        SELECT id, designation, designation_clean, famille, categorie, sous_categorie,
               colisage, unite, contenance, prix_unitaire, prix_colis,
               fournisseur_nom, fournisseur_type, notes, actif
        FROM dwh.other_produit_agregat
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_dir}
        LIMIT :limit OFFSET :offset
    """)

    results = db.execute(query, params).fetchall()

    items = [
        OtherProduitResponse(
            id=r[0],
            designation=r[1],
            designation_clean=r[2],
            famille=r[3],
            categorie=r[4],
            sous_categorie=r[5],
            colisage=r[6] or 1,
            unite=r[7],
            contenance=r[8],
            prix_unitaire=float(r[9] or 0),
            prix_colis=float(r[10]) if r[10] else None,
            fournisseur_nom=r[11],
            fournisseur_type=r[12],
            notes=r[13],
            actif=r[14] if r[14] is not None else True,
        )
        for r in results
    ]

    pages = (total + per_page - 1) // per_page if total > 0 else 1

    return OtherProduitListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get(
    "/products/{produit_id}",
    response_model=OtherProduitResponse,
    summary="Detail d'un produit OTHER",
)
def get_product(
    produit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Retourne le detail d'un produit OTHER."""
    query = text("""
        SELECT id, designation, designation_clean, famille, categorie, sous_categorie,
               colisage, unite, contenance, prix_unitaire, prix_colis,
               fournisseur_nom, fournisseur_type, notes, actif
        FROM dwh.other_produit_agregat
        WHERE id = :id AND tenant_id = :tenant_id
    """)

    result = db.execute(query, {"id": produit_id, "tenant_id": current_user.tenant_id}).fetchone()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit non trouve"
        )

    r = result
    return OtherProduitResponse(
        id=r[0],
        designation=r[1],
        designation_clean=r[2],
        famille=r[3],
        categorie=r[4],
        sous_categorie=r[5],
        colisage=r[6] or 1,
        unite=r[7],
        contenance=r[8],
        prix_unitaire=float(r[9] or 0),
        prix_colis=float(r[10]) if r[10] else None,
        fournisseur_nom=r[11],
        fournisseur_type=r[12],
        notes=r[13],
        actif=r[14] if r[14] is not None else True,
    )


@router.get(
    "/summary",
    response_model=OtherSummary,
    summary="Resume global OTHER",
)
def get_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Retourne le resume global des produits OTHER."""
    query = text("""
        SELECT
            COUNT(*) as nb_produits,
            COUNT(*) FILTER (WHERE actif = true) as nb_produits_actifs,
            COUNT(DISTINCT fournisseur_nom) as nb_fournisseurs,
            COALESCE(SUM(prix_unitaire * colisage), 0) as total_valeur
        FROM dwh.other_produit_agregat
        WHERE tenant_id = :tenant_id
    """)

    result = db.execute(query, {"tenant_id": current_user.tenant_id}).fetchone()

    return OtherSummary(
        nb_produits=result[0] or 0,
        nb_produits_actifs=result[1] or 0,
        nb_fournisseurs=result[2] or 0,
        total_valeur_catalogue=float(result[3] or 0),
    )


# ============================================
# Endpoints CRUD
# ============================================

@router.post(
    "/products",
    response_model=OtherProduitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Creer un produit OTHER",
)
def create_product(
    data: OtherProduitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Cree un nouveau produit OTHER."""
    query = text("""
        INSERT INTO dwh.other_produit_agregat (
            tenant_id, designation, designation_clean, famille, categorie, sous_categorie,
            colisage, unite, contenance, prix_unitaire, prix_colis,
            fournisseur_nom, fournisseur_type, notes, actif
        ) VALUES (
            :tenant_id, :designation, :designation_clean, :famille, :categorie, :sous_categorie,
            :colisage, :unite, :contenance, :prix_unitaire, :prix_colis,
            :fournisseur_nom, :fournisseur_type, :notes, true
        ) RETURNING id
    """)

    result = db.execute(query, {
        "tenant_id": current_user.tenant_id,
        "designation": data.designation,
        "designation_clean": data.designation.upper().strip(),
        "famille": data.famille,
        "categorie": data.categorie,
        "sous_categorie": data.sous_categorie,
        "colisage": data.colisage,
        "unite": data.unite,
        "contenance": data.contenance,
        "prix_unitaire": data.prix_unitaire,
        "prix_colis": data.prix_colis,
        "fournisseur_nom": data.fournisseur_nom,
        "fournisseur_type": data.fournisseur_type,
        "notes": data.notes,
    })

    new_id = result.scalar()
    db.commit()

    return get_product(new_id, current_user, db)


@router.put(
    "/products/{produit_id}",
    response_model=OtherProduitResponse,
    summary="Modifier un produit OTHER",
)
def update_product(
    produit_id: int,
    data: OtherProduitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Modifie un produit OTHER existant."""
    # Check exists
    existing = get_product(produit_id, current_user, db)

    # Build update
    updates = []
    params = {"id": produit_id, "tenant_id": current_user.tenant_id}

    if data.designation is not None:
        updates.append("designation = :designation")
        updates.append("designation_clean = :designation_clean")
        params["designation"] = data.designation
        params["designation_clean"] = data.designation.upper().strip()

    if data.famille is not None:
        updates.append("famille = :famille")
        params["famille"] = data.famille

    if data.categorie is not None:
        updates.append("categorie = :categorie")
        params["categorie"] = data.categorie

    if data.sous_categorie is not None:
        updates.append("sous_categorie = :sous_categorie")
        params["sous_categorie"] = data.sous_categorie

    if data.colisage is not None:
        updates.append("colisage = :colisage")
        params["colisage"] = data.colisage

    if data.unite is not None:
        updates.append("unite = :unite")
        params["unite"] = data.unite

    if data.contenance is not None:
        updates.append("contenance = :contenance")
        params["contenance"] = data.contenance

    if data.prix_unitaire is not None:
        updates.append("prix_unitaire = :prix_unitaire")
        params["prix_unitaire"] = data.prix_unitaire

    if data.prix_colis is not None:
        updates.append("prix_colis = :prix_colis")
        params["prix_colis"] = data.prix_colis

    if data.fournisseur_nom is not None:
        updates.append("fournisseur_nom = :fournisseur_nom")
        params["fournisseur_nom"] = data.fournisseur_nom

    if data.fournisseur_type is not None:
        updates.append("fournisseur_type = :fournisseur_type")
        params["fournisseur_type"] = data.fournisseur_type

    if data.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = data.notes

    if data.actif is not None:
        updates.append("actif = :actif")
        params["actif"] = data.actif

    if updates:
        updates.append("updated_at = NOW()")
        query = text(f"""
            UPDATE dwh.other_produit_agregat
            SET {', '.join(updates)}
            WHERE id = :id AND tenant_id = :tenant_id
        """)
        db.execute(query, params)
        db.commit()

    return get_product(produit_id, current_user, db)


@router.delete(
    "/products/{produit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un produit OTHER",
)
def delete_product(
    produit_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
):
    """Supprime un produit OTHER (soft delete via actif=false)."""
    # Check exists
    get_product(produit_id, current_user, db)

    query = text("""
        UPDATE dwh.other_produit_agregat
        SET actif = false, updated_at = NOW()
        WHERE id = :id AND tenant_id = :tenant_id
    """)

    db.execute(query, {"id": produit_id, "tenant_id": current_user.tenant_id})
    db.commit()

    return None
