"""
API Endpoints Finance Domain.
Gestion des comptes, transactions, factures.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_db_authenticated, get_current_user
from app.models.user import User
from app.services.metro import MetroService
from app.services.taiyat import TaiyatService
from app.services.eurociel import EurocielService
from app.models.finance.account import FinanceAccountType
from app.models.finance.transaction import FinanceTransactionDirection
from app.models.finance.invoice import FinanceInvoiceStatus
from app.repositories.finance.entity import FinanceEntityRepository, FinanceEntityMemberRepository
from app.repositories.finance.account import FinanceAccountRepository, FinanceAccountBalanceRepository
from app.repositories.finance.transaction import FinanceTransactionRepository, FinanceTransactionLineRepository
from app.repositories.finance.invoice import FinanceInvoiceRepository, FinanceInvoiceLineRepository, FinancePaymentRepository
from app.repositories.finance.vendor import FinanceVendorRepository
from app.services.finance.entity import FinanceEntityService, EntityNotFoundError, EntityCodeExistsError
from app.services.finance.account import FinanceAccountService, AccountNotFoundError, DuplicateIBANError
from app.services.finance.transaction import FinanceTransactionService, TransactionNotFoundError
from app.services.finance.invoice import FinanceInvoiceService, InvoiceNotFoundError, DuplicateInvoiceError
from app.services.finance.vendor import FinanceVendorService, VendorNotFoundError, VendorCodeExistsError

router = APIRouter(prefix="/finance", tags=["Finance"])


# =============================================================================
# Schemas
# =============================================================================

class EntityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    currency: str = Field(default="EUR", max_length=3)
    siret: Optional[str] = Field(None, max_length=14)
    address: Optional[str] = None

    class Config:
        extra = "forbid"


class EntityResponse(BaseModel):
    id: int
    name: str
    code: str
    currency: str
    is_active: bool
    siret: Optional[str]
    address: Optional[str]

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    entity_id: int
    label: str = Field(..., min_length=1, max_length=200)
    type: FinanceAccountType
    currency: str = Field(default="EUR", max_length=3)
    bank_name: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    initial_balance: int = Field(default=0, description="Solde initial en centimes")
    color: Optional[str] = None

    class Config:
        extra = "forbid"


class AccountResponse(BaseModel):
    id: int
    entity_id: int
    label: str
    type: FinanceAccountType
    currency: str
    bank_name: Optional[str]
    iban: Optional[str]
    bic: Optional[str]
    is_active: bool
    current_balance: int
    initial_balance: int
    color: Optional[str]

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    entity_id: int
    account_id: int
    direction: FinanceTransactionDirection
    amount: int = Field(..., gt=0, description="Montant en centimes (positif)")
    label: str = Field(..., min_length=1, max_length=500)
    date_operation: date
    date_valeur: Optional[date] = None
    reference: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class TransactionResponse(BaseModel):
    id: int
    entity_id: int
    account_id: int
    direction: FinanceTransactionDirection
    status: str
    amount: int
    label: str
    date_operation: date
    date_valeur: Optional[date]
    reference: Optional[str]
    is_categorized: bool
    is_reconciled: bool

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


# =============================================================================
# Dependencies
# =============================================================================

def get_entity_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinanceEntityService:
    """Fournit le service entity avec isolation tenant."""
    entity_repo = FinanceEntityRepository(db, current_user.tenant_id)
    member_repo = FinanceEntityMemberRepository(db)
    return FinanceEntityService(entity_repo, member_repo)


def get_account_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinanceAccountService:
    """Fournit le service account avec isolation tenant."""
    account_repo = FinanceAccountRepository(db, current_user.tenant_id)
    balance_repo = FinanceAccountBalanceRepository(db)
    return FinanceAccountService(account_repo, balance_repo)


def get_transaction_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinanceTransactionService:
    """Fournit le service transaction avec isolation tenant."""
    tx_repo = FinanceTransactionRepository(db, current_user.tenant_id)
    line_repo = FinanceTransactionLineRepository(db)
    account_repo = FinanceAccountRepository(db, current_user.tenant_id)
    return FinanceTransactionService(tx_repo, line_repo, account_repo)


def get_invoice_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinanceInvoiceService:
    """Fournit le service invoice avec isolation tenant."""
    invoice_repo = FinanceInvoiceRepository(db, current_user.tenant_id)
    line_repo = FinanceInvoiceLineRepository(db)
    payment_repo = FinancePaymentRepository(db)
    return FinanceInvoiceService(invoice_repo, line_repo, payment_repo)


# =============================================================================
# Entities Endpoints
# =============================================================================

@router.get("/entities", response_model=List[EntityResponse], summary="Liste des entites")
def list_entities(
    service: FinanceEntityService = Depends(get_entity_service)
):
    """Recupere toutes les entites actives du tenant."""
    return service.get_active_entities()


@router.post("/entities", response_model=EntityResponse, status_code=201, summary="Creer une entite")
def create_entity(
    data: EntityCreate,
    service: FinanceEntityService = Depends(get_entity_service)
):
    """Cree une nouvelle entite financiere."""
    try:
        return service.create_entity(**data.model_dump())
    except EntityCodeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/entities/{entity_id}", response_model=EntityResponse, summary="Detail d'une entite")
def get_entity(
    entity_id: int,
    service: FinanceEntityService = Depends(get_entity_service)
):
    """Recupere une entite par ID."""
    try:
        return service.get_entity(entity_id)
    except EntityNotFoundError:
        raise HTTPException(status_code=404, detail="Entite non trouvee")


# =============================================================================
# Accounts Endpoints
# =============================================================================

@router.get("/accounts", response_model=List[AccountResponse], summary="Liste des comptes")
def list_accounts(
    entity_id: int = Query(..., description="ID de l'entite"),
    active_only: bool = Query(True, description="Uniquement les comptes actifs"),
    service: FinanceAccountService = Depends(get_account_service)
):
    """Recupere les comptes d'une entite."""
    if active_only:
        return service.get_active_accounts(entity_id)
    return service.get_accounts_by_entity(entity_id)


@router.post("/accounts", response_model=AccountResponse, status_code=201, summary="Creer un compte")
def create_account(
    data: AccountCreate,
    service: FinanceAccountService = Depends(get_account_service)
):
    """Cree un nouveau compte bancaire."""
    try:
        payload = data.model_dump()
        payload["account_type"] = payload.pop("type")
        return service.create_account(**payload)
    except DuplicateIBANError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/accounts/{account_id}", response_model=AccountResponse, summary="Detail d'un compte")
def get_account(
    account_id: int,
    service: FinanceAccountService = Depends(get_account_service)
):
    """Recupere un compte par ID."""
    try:
        return service.get_account(account_id)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="Compte non trouve")


@router.get("/accounts/{account_id}/balances", summary="Historique des soldes")
def get_account_balances(
    account_id: int,
    limit: int = Query(30, ge=1, le=365),
    service: FinanceAccountService = Depends(get_account_service)
):
    """Recupere l'historique des soldes d'un compte."""
    try:
        service.get_account(account_id)  # Verifier existence
        return service.get_balance_history(account_id, limit)
    except AccountNotFoundError:
        raise HTTPException(status_code=404, detail="Compte non trouve")


# =============================================================================
# Transactions Endpoints
# =============================================================================

@router.get("/transactions", summary="Liste des transactions")
def list_transactions(
    entity_id: int = Query(..., description="ID de l'entite"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Recupere les transactions d'une entite avec pagination."""
    result = service.get_transactions_by_entity(entity_id, page, page_size)
    return {
        "items": [TransactionResponse.model_validate(t) for t in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "has_next": result.has_next,
        "has_prev": result.has_prev,
    }


@router.post("/transactions", response_model=TransactionResponse, status_code=201, summary="Creer une transaction")
def create_transaction(
    data: TransactionCreate,
    service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Cree une nouvelle transaction."""
    return service.create_transaction(**data.model_dump())


@router.get("/transactions/search", summary="Recherche de transactions")
def search_transactions(
    entity_id: int = Query(..., description="ID de l'entite"),
    label: Optional[str] = Query(None, description="Recherche dans le libelle"),
    direction: Optional[FinanceTransactionDirection] = None,
    min_amount: Optional[int] = Query(None, ge=0),
    max_amount: Optional[int] = Query(None, ge=0),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Recherche avancee de transactions."""
    result = service.search_transactions(
        entity_id=entity_id,
        label=label,
        direction=direction,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size
    )
    return {
        "items": [TransactionResponse.model_validate(t) for t in result.items],
        "total": result.total,
        "page": result.page,
        "page_size": result.page_size,
        "total_pages": result.total_pages,
        "has_next": result.has_next,
        "has_prev": result.has_prev,
    }


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse, summary="Detail d'une transaction")
def get_transaction(
    transaction_id: int,
    service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Recupere une transaction par ID."""
    try:
        return service.get_transaction(transaction_id)
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction non trouvee")


@router.post("/transactions/{transaction_id}/cancel", response_model=TransactionResponse, summary="Annuler une transaction")
def cancel_transaction(
    transaction_id: int,
    service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Annule une transaction et revert le solde."""
    try:
        return service.cancel_transaction(transaction_id)
    except TransactionNotFoundError:
        raise HTTPException(status_code=404, detail="Transaction non trouvee")


# =============================================================================
# Dashboard Endpoint
# =============================================================================

@router.get("/dashboard", summary="Dashboard finance")
def get_dashboard(
    entity_id: int = Query(..., description="ID de l'entite"),
    account_service: FinanceAccountService = Depends(get_account_service),
    invoice_service: FinanceInvoiceService = Depends(get_invoice_service),
    transaction_service: FinanceTransactionService = Depends(get_transaction_service)
):
    """Recupere les KPIs du dashboard finance."""
    # Soldes
    total_balance = account_service.get_total_balance(entity_id)
    bank_balance = account_service.get_balance_by_type(entity_id, FinanceAccountType.BANQUE)
    cash_balance = account_service.get_balance_by_type(entity_id, FinanceAccountType.CAISSE)

    # Factures
    pending_invoices = invoice_service.get_total_pending(entity_id)
    overdue_invoices = invoice_service.get_total_overdue(entity_id)

    # Transactions non categorisees
    uncategorized = transaction_service.get_uncategorized_transactions(entity_id)

    return {
        "balances": {
            "total": total_balance,
            "bank": bank_balance,
            "cash": cash_balance,
        },
        "invoices": {
            "pending_amount": pending_invoices,
            "overdue_amount": overdue_invoices,
        },
        "transactions": {
            "uncategorized_count": len(uncategorized),
        },
    }


# =============================================================================
# Vendor Schemas
# =============================================================================

class VendorCreate(BaseModel):
    entity_id: int
    name: str = Field(..., min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    siret: Optional[str] = Field(None, max_length=14)
    tva_intra: Optional[str] = Field(None, max_length=20)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=10)
    city: Optional[str] = Field(None, max_length=100)
    country: str = Field(default="FR", max_length=2)
    iban: Optional[str] = Field(None, max_length=34)
    bic: Optional[str] = Field(None, max_length=11)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    siret: Optional[str] = Field(None, max_length=14)
    tva_intra: Optional[str] = Field(None, max_length=20)
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None
    postal_code: Optional[str] = Field(None, max_length=10)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=2)
    iban: Optional[str] = Field(None, max_length=34)
    bic: Optional[str] = Field(None, max_length=11)
    payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class VendorResponse(BaseModel):
    id: int
    entity_id: int
    name: str
    code: Optional[str]
    is_active: bool
    siret: Optional[str]
    tva_intra: Optional[str]
    contact_name: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    address: Optional[str]
    postal_code: Optional[str]
    city: Optional[str]
    country: str
    iban: Optional[str]
    bic: Optional[str]
    payment_terms_days: int
    notes: Optional[str]

    class Config:
        from_attributes = True


# =============================================================================
# Vendor Dependencies
# =============================================================================

def get_vendor_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> FinanceVendorService:
    """Fournit le service vendor avec isolation tenant."""
    vendor_repo = FinanceVendorRepository(db, current_user.tenant_id)
    return FinanceVendorService(vendor_repo)


# =============================================================================
# Vendors Endpoints
# =============================================================================

@router.get("/vendors", response_model=List[VendorResponse], summary="Liste des fournisseurs")
def list_vendors(
    entity_id: int = Query(..., description="ID de l'entite"),
    active_only: bool = Query(True, description="Uniquement les fournisseurs actifs"),
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Recupere les fournisseurs d'une entite."""
    if active_only:
        return service.get_active_vendors(entity_id)
    return service.get_vendors_by_entity(entity_id)


@router.post("/vendors", response_model=VendorResponse, status_code=201, summary="Creer un fournisseur")
def create_vendor(
    data: VendorCreate,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Cree un nouveau fournisseur."""
    try:
        return service.create_vendor(**data.model_dump())
    except VendorCodeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/vendors/search", response_model=List[VendorResponse], summary="Recherche fournisseurs")
def search_vendors(
    entity_id: int = Query(..., description="ID de l'entite"),
    name: str = Query(..., min_length=1, description="Nom a rechercher"),
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Recherche des fournisseurs par nom."""
    return service.search_vendors(entity_id, name)


@router.get("/vendors/{vendor_id}", response_model=VendorResponse, summary="Detail d'un fournisseur")
def get_vendor(
    vendor_id: int,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Recupere un fournisseur par ID."""
    try:
        return service.get_vendor(vendor_id)
    except VendorNotFoundError:
        raise HTTPException(status_code=404, detail="Fournisseur non trouve")


@router.put("/vendors/{vendor_id}", response_model=VendorResponse, summary="Modifier un fournisseur")
def update_vendor(
    vendor_id: int,
    data: VendorUpdate,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Met a jour un fournisseur."""
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        return service.update_vendor(vendor_id, **update_data)
    except VendorNotFoundError:
        raise HTTPException(status_code=404, detail="Fournisseur non trouve")
    except VendorCodeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/vendors/{vendor_id}/deactivate", response_model=VendorResponse, summary="Desactiver un fournisseur")
def deactivate_vendor(
    vendor_id: int,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Desactive un fournisseur."""
    try:
        return service.deactivate_vendor(vendor_id)
    except VendorNotFoundError:
        raise HTTPException(status_code=404, detail="Fournisseur non trouve")


@router.post("/vendors/{vendor_id}/activate", response_model=VendorResponse, summary="Reactiver un fournisseur")
def activate_vendor(
    vendor_id: int,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Reactive un fournisseur."""
    try:
        return service.activate_vendor(vendor_id)
    except VendorNotFoundError:
        raise HTTPException(status_code=404, detail="Fournisseur non trouve")


@router.delete("/vendors/{vendor_id}", status_code=204, summary="Supprimer un fournisseur")
def delete_vendor(
    vendor_id: int,
    service: FinanceVendorService = Depends(get_vendor_service)
):
    """Supprime un fournisseur."""
    try:
        service.delete_vendor(vendor_id)
    except VendorNotFoundError:
        raise HTTPException(status_code=404, detail="Fournisseur non trouve")


# =============================================================================
# Factures Fournisseurs Unifiées (METRO, TAIYAT, EUROCIEL)
# =============================================================================

class UnifiedFactureItem(BaseModel):
    """Facture unifiée tous fournisseurs."""
    id: int
    source: str  # METRO, TAIYAT, EUROCIEL
    numero: str
    date_facture: date
    fournisseur: str  # Nom du fournisseur (magasin METRO, client TAIYAT/EUROCIEL)
    total_ht: Optional[float] = None
    total_tva: Optional[float] = None
    total_ttc: float
    nb_lignes: int
    type_document: str = "FA"  # FA=Facture, AV=Avoir

    class Config:
        from_attributes = True


class UnifiedFacturesResponse(BaseModel):
    """Réponse paginée des factures unifiées."""
    items: List[UnifiedFactureItem]
    total: int
    page: int
    per_page: int
    pages: int
    summary: Dict[str, Any]


class UnifiedFacturesSummary(BaseModel):
    """Résumé global des factures fournisseurs."""
    total_factures: int
    total_ht: float
    total_tva: float
    total_ttc: float
    par_fournisseur: Dict[str, Dict[str, Any]]


def get_supplier_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_authenticated),
) -> Dict[str, Any]:
    """Fournit les services METRO, TAIYAT, EUROCIEL."""
    return {
        "metro": MetroService(db=db, tenant_id=current_user.tenant_id),
        "taiyat": TaiyatService(db=db, tenant_id=current_user.tenant_id),
        "eurociel": EurocielService(db=db, tenant_id=current_user.tenant_id),
    }


@router.get("/factures-fournisseurs", response_model=UnifiedFacturesResponse, summary="Factures tous fournisseurs")
def list_all_supplier_invoices(
    page: int = Query(1, ge=1, description="Page"),
    per_page: int = Query(20, ge=1, le=10000, description="Factures par page"),
    source: Optional[str] = Query(None, description="Filtrer par source (METRO, TAIYAT, EUROCIEL)"),
    search: Optional[str] = Query(None, description="Recherche par numéro ou fournisseur"),
    date_debut: Optional[date] = Query(None, description="Date début"),
    date_fin: Optional[date] = Query(None, description="Date fin"),
    sort_by: str = Query("date_facture", description="Tri par champ"),
    sort_order: str = Query("desc", description="Ordre (asc/desc)"),
    services: Dict = Depends(get_supplier_services),
):
    """
    Retourne toutes les factures fournisseurs unifiées (METRO, TAIYAT, EUROCIEL).

    Les factures sont fusionnées dans un format commun avec:
    - source: identifiant du fournisseur d'origine
    - fournisseur: nom du magasin/client
    - Montants HT/TVA/TTC normalisés
    """
    all_factures: List[UnifiedFactureItem] = []
    summary_data = {
        "METRO": {"nb_factures": 0, "total_ht": 0, "total_tva": 0, "total_ttc": 0},
        "TAIYAT": {"nb_factures": 0, "total_ht": 0, "total_tva": 0, "total_ttc": 0},
        "EUROCIEL": {"nb_factures": 0, "total_ht": 0, "total_tva": 0, "total_ttc": 0},
    }

    # === METRO ===
    if source is None or source.upper() == "METRO":
        try:
            # METRO returns Tuple[List[MetroFacture], int]
            metro_factures, metro_total = services["metro"].get_factures(
                page=1, per_page=10000,
                date_debut=date_debut, date_fin=date_fin
            )
            for f in metro_factures:
                total_ht = float(f.total_ht or 0)
                total_tva = float(f.total_tva or 0)
                total_ttc = float(f.total_ttc or 0)
                # Get nb_lignes from relationship or attribute
                nb_lignes = len(f.lignes) if hasattr(f, 'lignes') and f.lignes else 0

                all_factures.append(UnifiedFactureItem(
                    id=f.id,
                    source="METRO",
                    numero=f.numero,
                    date_facture=f.date_facture,
                    fournisseur=f.magasin or "METRO",
                    total_ht=total_ht,
                    total_tva=total_tva,
                    total_ttc=total_ttc,
                    nb_lignes=nb_lignes,
                    type_document="FA",
                ))
                summary_data["METRO"]["nb_factures"] += 1
                summary_data["METRO"]["total_ht"] += total_ht
                summary_data["METRO"]["total_tva"] += total_tva
                summary_data["METRO"]["total_ttc"] += total_ttc
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error loading METRO factures: {e}")

    # === TAIYAT ===
    if source is None or source.upper() == "TAIYAT":
        try:
            taiyat_data = services["taiyat"].get_factures(
                page=1, per_page=10000,
                date_debut=date_debut, date_fin=date_fin
            )
            for f in taiyat_data.get("items", []):
                total_ht = float(f.get("total_ht", 0) or 0)
                total_tva = float(f.get("total_tva", 0) or 0)
                total_ttc = float(f.get("total_ttc", 0) or 0)

                all_factures.append(UnifiedFactureItem(
                    id=f["id"],
                    source="TAIYAT",
                    numero=f["numero"],
                    date_facture=f["date_facture"],
                    fournisseur=f.get("client_nom", "TAIYAT"),
                    total_ht=total_ht,
                    total_tva=total_tva,
                    total_ttc=total_ttc,
                    nb_lignes=f.get("nb_lignes", 0),
                    type_document="FA",
                ))
                summary_data["TAIYAT"]["nb_factures"] += 1
                summary_data["TAIYAT"]["total_ht"] += total_ht
                summary_data["TAIYAT"]["total_tva"] += total_tva
                summary_data["TAIYAT"]["total_ttc"] += total_ttc
        except Exception:
            pass

    # === EUROCIEL ===
    if source is None or source.upper() == "EUROCIEL":
        try:
            eurociel_data = services["eurociel"].get_factures(
                page=1, per_page=10000,
                date_debut=date_debut, date_fin=date_fin
            )
            for f in eurociel_data.get("items", []):
                total_ht = float(f.get("total_ht", 0) or 0)
                total_tva = float(f.get("total_tva", 0) or 0)
                total_ttc = float(f.get("total_ttc", 0) or 0)
                type_doc = f.get("type_document", "FA")

                all_factures.append(UnifiedFactureItem(
                    id=f["id"],
                    source="EUROCIEL",
                    numero=f["numero"],
                    date_facture=f["date_facture"],
                    fournisseur=f.get("client_nom", "EUROCIEL"),
                    total_ht=total_ht,
                    total_tva=total_tva,
                    total_ttc=total_ttc,
                    nb_lignes=f.get("nb_lignes", 0),
                    type_document=type_doc,
                ))
                summary_data["EUROCIEL"]["nb_factures"] += 1
                summary_data["EUROCIEL"]["total_ht"] += total_ht
                summary_data["EUROCIEL"]["total_tva"] += total_tva
                summary_data["EUROCIEL"]["total_ttc"] += total_ttc
        except Exception:
            pass

    # Filtrage par recherche
    if search:
        search_lower = search.lower()
        all_factures = [
            f for f in all_factures
            if search_lower in f.numero.lower() or search_lower in f.fournisseur.lower()
        ]

    # Tri
    reverse = sort_order.lower() == "desc"
    if sort_by == "date_facture":
        all_factures.sort(key=lambda x: x.date_facture, reverse=reverse)
    elif sort_by == "total_ttc":
        all_factures.sort(key=lambda x: x.total_ttc, reverse=reverse)
    elif sort_by == "numero":
        all_factures.sort(key=lambda x: x.numero, reverse=reverse)
    elif sort_by == "fournisseur":
        all_factures.sort(key=lambda x: x.fournisseur, reverse=reverse)
    elif sort_by == "source":
        all_factures.sort(key=lambda x: x.source, reverse=reverse)

    # Pagination
    total = len(all_factures)
    pages = (total + per_page - 1) // per_page if total > 0 else 1
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_factures[start:end]

    # Summary global
    summary = {
        "total_factures": sum(s["nb_factures"] for s in summary_data.values()),
        "total_ht": round(sum(s["total_ht"] for s in summary_data.values()), 2),
        "total_tva": round(sum(s["total_tva"] for s in summary_data.values()), 2),
        "total_ttc": round(sum(s["total_ttc"] for s in summary_data.values()), 2),
        "par_fournisseur": summary_data,
    }

    return UnifiedFacturesResponse(
        items=paginated,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        summary=summary,
    )


@router.get("/factures-fournisseurs/summary", summary="Résumé factures fournisseurs")
def get_supplier_invoices_summary(
    services: Dict = Depends(get_supplier_services),
) -> UnifiedFacturesSummary:
    """
    Retourne un résumé des factures de tous les fournisseurs.
    """
    summary_data = {
        "METRO": {"nb_factures": 0, "total_ht": 0.0, "total_tva": 0.0, "total_ttc": 0.0},
        "TAIYAT": {"nb_factures": 0, "total_ht": 0.0, "total_tva": 0.0, "total_ttc": 0.0},
        "EUROCIEL": {"nb_factures": 0, "total_ht": 0.0, "total_tva": 0.0, "total_ttc": 0.0},
    }

    # METRO
    try:
        metro_summary = services["metro"].get_summary()
        summary_data["METRO"] = {
            "nb_factures": metro_summary.get("nb_factures", 0),
            "total_ht": float(metro_summary.get("total_ht", 0) or 0),
            "total_tva": float(metro_summary.get("total_tva", 0) or 0),
            "total_ttc": float(metro_summary.get("total_ttc", 0) or 0),
        }
    except Exception:
        pass

    # TAIYAT
    try:
        taiyat_summary = services["taiyat"].get_summary()
        summary_data["TAIYAT"] = {
            "nb_factures": taiyat_summary.get("nb_factures", 0),
            "total_ht": float(taiyat_summary.get("total_ht", 0) or 0),
            "total_tva": float(taiyat_summary.get("total_tva", 0) or 0),
            "total_ttc": float(taiyat_summary.get("total_ttc", 0) or 0),
        }
    except Exception:
        pass

    # EUROCIEL
    try:
        eurociel_summary = services["eurociel"].get_summary()
        summary_data["EUROCIEL"] = {
            "nb_factures": eurociel_summary.get("nb_factures", 0),
            "total_ht": float(eurociel_summary.get("total_ht", 0) or 0),
            "total_tva": float(eurociel_summary.get("total_tva", 0) or 0),
            "total_ttc": float(eurociel_summary.get("total_ttc", 0) or 0),
        }
    except Exception:
        pass

    return UnifiedFacturesSummary(
        total_factures=sum(s["nb_factures"] for s in summary_data.values()),
        total_ht=round(sum(s["total_ht"] for s in summary_data.values()), 2),
        total_tva=round(sum(s["total_tva"] for s in summary_data.values()), 2),
        total_ttc=round(sum(s["total_ttc"] for s in summary_data.values()), 2),
        par_fournisseur=summary_data,
    )


@router.get("/factures-fournisseurs/{source}/{facture_id}", summary="Détail facture fournisseur")
def get_supplier_invoice_detail(
    source: str,
    facture_id: int,
    services: Dict = Depends(get_supplier_services),
) -> Dict[str, Any]:
    """
    Retourne le détail d'une facture fournisseur avec ses lignes.

    - source: METRO, TAIYAT ou EUROCIEL
    - facture_id: ID de la facture
    """
    source_upper = source.upper()

    if source_upper == "METRO":
        # METRO returns MetroFacture model
        facture = services["metro"].get_facture(facture_id)
        if not facture:
            raise HTTPException(status_code=404, detail="Facture METRO non trouvée")
        return {
            "source": "METRO",
            "id": facture.id,
            "numero": facture.numero,
            "date_facture": facture.date_facture.isoformat() if facture.date_facture else None,
            "magasin": facture.magasin,
            "total_ht": float(facture.total_ht or 0),
            "total_tva": float(facture.total_tva or 0),
            "total_ttc": float(facture.total_ttc or 0),
            "lignes": [
                {
                    "ean": l.ean,
                    "designation": l.designation,
                    "colisage": l.colisage,
                    "quantite_colis": float(l.quantite_colis or 0),
                    "quantite_unitaire": float(l.quantite_unitaire or 0),
                    "prix_unitaire": float(l.prix_unitaire or 0),
                    "montant_ht": float(l.montant_ht or 0),
                    "taux_tva": float(l.taux_tva or 20),
                    "regie": l.regie,
                    "vol_alcool": float(l.vol_alcool) if l.vol_alcool else None,
                }
                for l in facture.lignes
            ],
        }

    elif source_upper == "TAIYAT":
        detail = services["taiyat"].get_facture_detail(facture_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Facture TAIYAT non trouvée")
        return {"source": "TAIYAT", **detail}

    elif source_upper == "EUROCIEL":
        detail = services["eurociel"].get_facture_detail(facture_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Facture EUROCIEL non trouvée")
        return {"source": "EUROCIEL", **detail}

    else:
        raise HTTPException(status_code=400, detail=f"Source inconnue: {source}")
