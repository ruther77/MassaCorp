"""
Modeles SQLAlchemy pour MassaCorp API
Export tous les modeles pour faciliter les imports

Modules disponibles:
- base: Classes de base et mixins (Base, TimestampMixin, TenantMixin, etc.)
- tenant: Model Tenant pour l'isolation multi-tenant
- user: Model User pour l'authentification
- audit: Models d'audit (AuditLog, LoginAttempt)
- session: Models de session (Session, RefreshToken, RevokedToken)
- mfa: Models MFA (MFASecret, MFARecoveryCode)
- password_reset: Model PasswordResetToken pour la reinitialisation de mot de passe
- rbac: Models RBAC (Role, Permission, UserRole, RolePermission)
"""
from app.models.base import Base, TimestampMixin, TenantMixin, SoftDeleteMixin, utc_now
from app.models.tenant import Tenant
from app.models.user import User
from app.models.audit import AuditLog, LoginAttempt
from app.models.session import Session, RefreshToken, RevokedToken
from app.models.mfa import MFASecret, MFARecoveryCode
from app.models.password_reset import PasswordResetToken
from app.models.api_key import APIKey, APIKeyUsage, APIKeyScopes
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.oauth import OAuthAccount
from app.models.metro import MetroFacture, MetroLigne, MetroProduitAgregat, get_categorie, METRO_CATEGORIES
from app.models.taiyat import TaiyatFacture, TaiyatLigne, TaiyatProduitAgregat, categoriser_produit, TAIYAT_TVA_CODES
from app.models.eurociel import EurocielFacture, EurocielLigne, EurocielProduitAgregat, EurocielCatalogueProduit, categoriser_produit_eurociel, EUROCIEL_TVA_CODES

# Models Finance
from app.models.finance import (
    FinanceEntity,
    FinanceEntityMember,
    FinanceCategory,
    FinanceCategoryType,
    FinanceCostCenter,
    FinanceAccount,
    FinanceAccountBalance,
    FinanceAccountType,
    FinanceTransaction,
    FinanceTransactionLine,
    FinanceTransactionDirection,
    FinanceTransactionStatus,
    FinanceVendor,
    FinanceInvoice,
    FinanceInvoiceLine,
    FinancePayment,
    FinanceInvoiceStatus,
    FinanceBankStatement,
    FinanceBankStatementLine,
    FinanceReconciliation,
    FinanceReconciliationStatus,
)

# Models Restaurant
from app.models.restaurant import (
    RestaurantIngredient,
    RestaurantUnit,
    RestaurantIngredientCategory,
    RestaurantPlat,
    RestaurantPlatCategory,
    RestaurantPlatIngredient,
    RestaurantEpicerieLink,
    RestaurantStock,
    RestaurantStockMovement,
    RestaurantStockMovementType,
    RestaurantConsumption,
    RestaurantConsumptionType,
    RestaurantCharge,
    RestaurantChargeType,
    RestaurantChargeFrequency,
)

# Models Epicerie
from app.models.epicerie import (
    SupplyOrder,
    SupplyOrderLine,
    SupplyOrderStatus,
)

# Alias pour compatibilite avec les tests - UserSession pointe vers Session
UserSession = Session

__all__ = [
    # Base et mixins
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    "utc_now",
    # Models principaux
    "Tenant",
    "User",
    # Models d'audit et securite
    "AuditLog",
    "LoginAttempt",
    # Models de session et tokens
    "Session",
    "UserSession",  # Alias pour Session
    "RefreshToken",
    "RevokedToken",
    # Models MFA
    "MFASecret",
    "MFARecoveryCode",
    # Models password reset
    "PasswordResetToken",
    # Models API Keys
    "APIKey",
    "APIKeyUsage",
    "APIKeyScopes",
    # Models RBAC
    "Permission",
    "Role",
    "RolePermission",
    "UserRole",
    # Models OAuth
    "OAuthAccount",
    # Models METRO
    "MetroFacture",
    "MetroLigne",
    "MetroProduitAgregat",
    "get_categorie",
    "METRO_CATEGORIES",
    # Models TAIYAT
    "TaiyatFacture",
    "TaiyatLigne",
    "TaiyatProduitAgregat",
    "categoriser_produit",
    "TAIYAT_TVA_CODES",
    # Models EUROCIEL
    "EurocielFacture",
    "EurocielLigne",
    "EurocielProduitAgregat",
    "EurocielCatalogueProduit",
    "categoriser_produit_eurociel",
    "EUROCIEL_TVA_CODES",
    # Models Finance
    "FinanceEntity",
    "FinanceEntityMember",
    "FinanceCategory",
    "FinanceCategoryType",
    "FinanceCostCenter",
    "FinanceAccount",
    "FinanceAccountBalance",
    "FinanceAccountType",
    "FinanceTransaction",
    "FinanceTransactionLine",
    "FinanceTransactionDirection",
    "FinanceTransactionStatus",
    "FinanceVendor",
    "FinanceInvoice",
    "FinanceInvoiceLine",
    "FinancePayment",
    "FinanceInvoiceStatus",
    "FinanceBankStatement",
    "FinanceBankStatementLine",
    "FinanceReconciliation",
    "FinanceReconciliationStatus",
    # Models Restaurant
    "RestaurantIngredient",
    "RestaurantUnit",
    "RestaurantIngredientCategory",
    "RestaurantPlat",
    "RestaurantPlatCategory",
    "RestaurantPlatIngredient",
    "RestaurantEpicerieLink",
    "RestaurantStock",
    "RestaurantStockMovement",
    "RestaurantStockMovementType",
    "RestaurantConsumption",
    "RestaurantConsumptionType",
    "RestaurantCharge",
    "RestaurantChargeType",
    "RestaurantChargeFrequency",
    # Models Epicerie
    "SupplyOrder",
    "SupplyOrderLine",
    "SupplyOrderStatus",
]
