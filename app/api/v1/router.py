"""
Router principal API v1 pour MassaCorp
Combine tous les endpoints v1

Endpoints disponibles:
- /auth: Authentification (login, logout, refresh, register)
- /oauth: Authentification sociale (Google, Facebook, GitHub)
- /users: Gestion des utilisateurs (CRUD)
- /sessions: Gestion des sessions (liste, termination)
- /mfa: Authentification multi-facteur (Phase 3)
- /api-keys: Gestion des API Keys (M2M auth)
- /password-reset: Reinitialisation de mot de passe
- /gdpr: Conformite GDPR (export, suppression, inventaire)
- /analytics: Data Warehouse - Requetes analytiques
- /catalog: Catalogue produits avec stock
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    oauth,
    users,
    sessions,
    mfa,
    api_keys,
    password_reset,
    gdpr,
    analytics,
    catalog,
    metro,
)


# Router principal v1
api_router = APIRouter()

# Inclusion des routers d'endpoints
api_router.include_router(auth.router)
api_router.include_router(oauth.router)
api_router.include_router(users.router)
api_router.include_router(sessions.router)
api_router.include_router(mfa.router)
api_router.include_router(api_keys.router)
api_router.include_router(password_reset.router)
api_router.include_router(gdpr.router)
api_router.include_router(analytics.router)
api_router.include_router(catalog.router)
api_router.include_router(metro.router)
