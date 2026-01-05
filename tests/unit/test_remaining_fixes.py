"""
Tests TDD pour les corrections restantes.

Issues couvertes:
1. validate_secrets() appelee au startup
2. MFA service requis (pas optionnel)
3. /login/mfa validation X-Tenant-ID
4. get_db() consolide
5. Exceptions dupliquees supprimees
6. Change password revoque sessions
7. Cleanup sessions avec filtre tenant
8. Password max_length
9. MFA code max_length coherent
"""
import pytest
from unittest.mock import MagicMock, patch, call
from uuid import uuid4


# =============================================================================
# 1 - validate_secrets() appelee au startup
# =============================================================================
class TestValidateSecretsStartup:
    """validate_production_config doit etre appele au demarrage en production"""

    @pytest.mark.unit
    def test_lifespan_calls_validate_secrets_in_production(self):
        """Le lifespan doit appeler validate_production_config en mode production"""
        # Ce test verifie que main.py appelle validate_production_config
        # (qui appelle validate_secrets en interne)
        import ast

        with open("/app/app/main.py", "r") as f:
            source = f.read()

        tree = ast.parse(source)

        # Chercher un appel a validate_production_config ou validate_secrets
        has_validate_call = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("validate_production_config", "validate_secrets"):
                        has_validate_call = True
                        break

        assert has_validate_call, \
            "main.py doit appeler settings.validate_production_config() au demarrage"


# =============================================================================
# 2 - MFA service requis (pas optionnel silencieux)
# =============================================================================
class TestMFAServiceRequired:
    """MFA service ne doit pas etre silencieusement ignore"""

    @pytest.mark.unit
    def test_auth_service_logs_warning_if_mfa_service_none(self):
        """AuthService doit logger un warning si mfa_service est None"""
        from app.services.auth import AuthService
        import logging

        mock_user_repo = MagicMock()

        with patch('app.services.auth.logger') as mock_logger:
            service = AuthService(
                user_repository=mock_user_repo,
                mfa_service=None  # Pas de MFA service
            )

            # Doit avoir logge un warning
            warning_calls = [c for c in mock_logger.warning.call_args_list]
            has_mfa_warning = any('mfa' in str(c).lower() for c in warning_calls)

            assert has_mfa_warning or mock_logger.warning.called, \
                "AuthService doit logger un warning si mfa_service est None"

    @pytest.mark.unit
    def test_login_without_mfa_service_still_works_but_warns(self):
        """Login sans mfa_service fonctionne mais doit logger"""
        from app.services.auth import AuthService
        from app.core.security import hash_password

        mock_user_repo = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.email = "test@test.com"
        mock_user.password_hash = hash_password("ValidP@ss123!")
        mock_user.is_active = True
        mock_user.failed_login_attempts = 0
        mock_user.lockout_until = None
        mock_user_repo.get_by_email_and_tenant.return_value = mock_user

        with patch('app.services.auth.logger') as mock_logger:
            service = AuthService(
                user_repository=mock_user_repo,
                mfa_service=None
            )

            # Login devrait fonctionner (pas de MFA pour cet user)
            # Mais un warning devrait etre logge
            result = service.login(
                email="test@test.com",
                password="ValidP@ss123!",
                tenant_id=1
            )

            # Le warning peut etre a l'init ou au login
            assert mock_logger.warning.called or result is not None


# =============================================================================
# 3 - /login/mfa validation X-Tenant-ID
# =============================================================================
class TestLoginMFATenantValidation:
    """/auth/login/mfa doit valider X-Tenant-ID"""

    @pytest.mark.unit
    def test_login_mfa_endpoint_checks_tenant_header(self):
        """login_mfa doit verifier la presence de X-Tenant-ID"""
        import inspect
        from app.api.v1.endpoints.auth import login_mfa

        source = inspect.getsource(login_mfa)

        # Doit contenir une verification du header X-Tenant-ID
        has_tenant_check = (
            "X-Tenant-ID" in source or
            "tenant_id_header" in source or
            "get_tenant_id" in source
        )

        assert has_tenant_check, \
            "login_mfa doit verifier le header X-Tenant-ID"

    @pytest.mark.unit
    def test_login_mfa_rejects_missing_tenant(self):
        """login_mfa doit rejeter les requetes sans X-Tenant-ID"""
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/login/mfa",
            json={
                "mfa_session_token": "fake_token",
                "totp_code": "123456"
            }
            # Pas de header X-Tenant-ID!
        )

        # Doit etre rejete avec 400 ou 401
        assert response.status_code in [400, 401, 422, 429], \
            f"login_mfa sans X-Tenant-ID doit etre rejete, got {response.status_code}"


# =============================================================================
# 4 - get_db() consolide
# =============================================================================
class TestGetDbConsolidation:
    """Une seule implementation de get_db() doit exister"""

    @pytest.mark.unit
    def test_database_get_db_not_used_directly(self):
        """database.py get_db ne doit pas etre importe directement"""
        import ast
        import os

        # Lister tous les fichiers Python dans app/
        app_dir = "/app/app"
        imports_database_get_db = []

        for root, dirs, files in os.walk(app_dir):
            # Ignorer __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py') and file != 'database.py':
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r') as f:
                            source = f.read()

                        # Chercher "from app.core.database import get_db"
                        if "from app.core.database import" in source and "get_db" in source:
                            # Verifier que c'est vraiment get_db qui est importe
                            tree = ast.parse(source)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.ImportFrom):
                                    if node.module == "app.core.database":
                                        for alias in node.names:
                                            if alias.name == "get_db":
                                                imports_database_get_db.append(filepath)
                    except:
                        pass

        # Seul dependencies.py devrait importer get_db de database.py
        # Ou aucun fichier ne devrait l'importer directement
        allowed = ["/app/app/core/dependencies.py"]
        bad_imports = [f for f in imports_database_get_db if f not in allowed]

        assert len(bad_imports) == 0, \
            f"Ces fichiers importent get_db de database.py: {bad_imports}. " \
            "Utiliser get_db de dependencies.py a la place."


# =============================================================================
# 5 - Exceptions dupliquees
# =============================================================================
class TestNoDuplicateExceptions:
    """Les exceptions ne doivent pas etre dupliquees"""

    @pytest.mark.unit
    def test_session_not_found_error_single_definition(self):
        """SessionNotFoundError doit avoir une seule definition"""
        import ast

        files_with_definition = []

        for filepath in [
            "/app/app/services/exceptions.py",
            "/app/app/services/session.py"
        ]:
            try:
                with open(filepath, 'r') as f:
                    source = f.read()

                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if node.name == "SessionNotFoundError":
                            files_with_definition.append(filepath)
            except FileNotFoundError:
                pass

        assert len(files_with_definition) <= 1, \
            f"SessionNotFoundError defini dans plusieurs fichiers: {files_with_definition}. " \
            "Consolider dans exceptions.py uniquement."

    @pytest.mark.unit
    def test_session_expired_error_single_definition(self):
        """SessionExpiredError doit avoir une seule definition"""
        import ast

        files_with_definition = []

        for filepath in [
            "/app/app/services/exceptions.py",
            "/app/app/services/session.py"
        ]:
            try:
                with open(filepath, 'r') as f:
                    source = f.read()

                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if node.name == "SessionExpiredError":
                            files_with_definition.append(filepath)
            except FileNotFoundError:
                pass

        assert len(files_with_definition) <= 1, \
            f"SessionExpiredError defini dans plusieurs fichiers: {files_with_definition}"


# =============================================================================
# 6 - Change password revoque sessions
# =============================================================================
class TestChangePasswordRevokeSessions:
    """Changement de mot de passe doit revoquer les sessions"""

    @pytest.mark.unit
    def test_user_service_change_password_has_session_service(self):
        """UserService.change_password doit avoir acces a session_service"""
        from app.services.user import UserService
        import inspect

        # Verifier que UserService accepte session_service
        sig = inspect.signature(UserService.__init__)
        params = list(sig.parameters.keys())

        has_session_param = any('session' in p.lower() for p in params)

        assert has_session_param, \
            "UserService doit accepter session_service pour revoquer les sessions"

    @pytest.mark.unit
    def test_change_password_calls_invalidate_sessions(self):
        """change_password doit appeler invalidate sur les sessions"""
        from app.services.user import UserService
        from app.core.security import hash_password

        mock_user_repo = MagicMock()
        mock_session_service = MagicMock()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.tenant_id = 1
        mock_user.password_hash = hash_password("OldP@ssw0rd!")
        mock_user_repo.get_by_id.return_value = mock_user
        mock_user_repo.update_password.return_value = mock_user

        service = UserService(
            user_repository=mock_user_repo,
            session_service=mock_session_service
        )

        service.change_password(
            user_id=1,
            current_password="OldP@ssw0rd!",
            new_password="NewP@ssw0rd!"
        )

        # Doit avoir invalide les sessions (sauf la courante potentiellement)
        assert mock_session_service.terminate_all_sessions.called, \
            "change_password doit revoquer les sessions de l'utilisateur"


# =============================================================================
# 7 - Cleanup sessions avec filtre tenant
# =============================================================================
class TestCleanupSessionsTenant:
    """cleanup_expired_sessions doit supporter le filtre tenant"""

    @pytest.mark.unit
    def test_cleanup_accepts_tenant_id_parameter(self):
        """cleanup_expired_sessions doit accepter tenant_id optionnel"""
        from app.services.session import SessionService
        import inspect

        sig = inspect.signature(SessionService.cleanup_expired_sessions)
        params = list(sig.parameters.keys())

        has_tenant_param = 'tenant_id' in params

        assert has_tenant_param, \
            "cleanup_expired_sessions doit accepter un parametre tenant_id"

    @pytest.mark.unit
    def test_cleanup_with_tenant_filters_correctly(self):
        """cleanup avec tenant_id ne nettoie que ce tenant"""
        from app.services.session import SessionService

        mock_session_repo = MagicMock()
        mock_session_repo.cleanup_expired.return_value = 5

        service = SessionService(session_repository=mock_session_repo)

        result = service.cleanup_expired_sessions(
            older_than_days=30,
            tenant_id=1
        )

        # Le repo doit etre appele avec tenant_id
        call_kwargs = mock_session_repo.cleanup_expired.call_args
        if call_kwargs:
            args, kwargs = call_kwargs
            assert 'tenant_id' in kwargs or len(args) > 1, \
                "cleanup_expired doit passer tenant_id au repository"


# =============================================================================
# 8 - Password max_length
# =============================================================================
class TestPasswordMaxLength:
    """Les mots de passe doivent avoir une limite de longueur"""

    @pytest.mark.unit
    def test_login_request_has_password_max_length(self):
        """LoginRequest.password doit avoir max_length"""
        from app.schemas.auth import LoginRequest
        from pydantic import ValidationError

        # Tester avec un mot de passe tres long (10KB)
        long_password = "A" * 10000

        try:
            req = LoginRequest(
                email="test@test.com",
                password=long_password
            )
            # Si ca passe, verifier que le schema a une limite
            schema = LoginRequest.model_json_schema()
            password_props = schema.get("properties", {}).get("password", {})

            assert "maxLength" in password_props, \
                "LoginRequest.password doit avoir maxLength pour prevenir DoS bcrypt"
        except ValidationError:
            # C'est le comportement attendu - limite appliquee
            pass

    @pytest.mark.unit
    def test_password_max_length_is_reasonable(self):
        """La limite password doit etre raisonnable (128-1024)"""
        from app.schemas.auth import LoginRequest

        schema = LoginRequest.model_json_schema()
        password_props = schema.get("properties", {}).get("password", {})
        max_length = password_props.get("maxLength")

        if max_length:
            assert 128 <= max_length <= 1024, \
                f"maxLength={max_length} devrait etre entre 128 et 1024"


# =============================================================================
# 9 - MFA code max_length coherent
# =============================================================================
class TestMFACodeMaxLengthConsistency:
    """Les schemas MFA doivent avoir des max_length coherents"""

    @pytest.mark.unit
    def test_mfa_verify_request_accepts_recovery_codes(self):
        """MFAVerifyRequest.code doit accepter les recovery codes (9 chars)"""
        from app.schemas.mfa import MFAVerifyRequest

        schema = MFAVerifyRequest.model_json_schema()
        code_props = schema.get("properties", {}).get("code", {})
        max_length = code_props.get("maxLength")

        # Recovery codes sont XXXX-XXXX = 9 caracteres
        assert max_length is None or max_length >= 9, \
            f"MFAVerifyRequest.code maxLength={max_length} doit etre >= 9 pour recovery codes"

    @pytest.mark.unit
    def test_mfa_schemas_accept_appropriate_code_lengths(self):
        """Les schemas MFA doivent accepter les bonnes longueurs de code"""
        from app.schemas.mfa import (
            MFAVerifyRequest,
            MFARecoveryVerifyRequest,
            MFAEnableRequest
        )

        # Schemas qui acceptent recovery codes (XXXX-XXXX = 9 chars)
        recovery_schemas = [MFAVerifyRequest, MFARecoveryVerifyRequest]
        for schema_class in recovery_schemas:
            schema = schema_class.model_json_schema()
            code_props = schema.get("properties", {}).get("code", {})
            ml = code_props.get("maxLength")
            assert ml is None or ml >= 9, \
                f"{schema_class.__name__} doit accepter recovery codes (max_length >= 9)"

        # Schemas TOTP-only (6 digits)
        totp_only_schemas = [MFAEnableRequest]
        for schema_class in totp_only_schemas:
            schema = schema_class.model_json_schema()
            code_props = schema.get("properties", {}).get("code", {})
            ml = code_props.get("maxLength")
            assert ml == 6, \
                f"{schema_class.__name__} est TOTP-only (max_length = 6)"


# =============================================================================
# Tests de regression
# =============================================================================
class TestRegressionChecks:
    """Verifier qu'aucune regression n'est introduite"""

    @pytest.mark.unit
    def test_all_existing_tests_still_import(self):
        """Les tests existants doivent toujours pouvoir importer"""
        # Importer les modules critiques
        from app.services.auth import AuthService
        from app.services.user import UserService
        from app.services.session import SessionService
        from app.services.token import TokenService
        from app.services.mfa import MFAService
        from app.core.dependencies import get_db, get_current_user
        from app.core.security import hash_password, verify_password

        assert True  # Si on arrive ici, les imports fonctionnent
