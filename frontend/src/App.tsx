import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

// Layouts
import AuthLayout from '@/components/layout/AuthLayout'
import DashboardLayout from '@/components/layout/DashboardLayout'

// Auth pages
import LoginPage from '@/pages/auth/LoginPage'
import RegisterPage from '@/pages/auth/RegisterPage'
import ForgotPasswordPage from '@/pages/auth/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/auth/ResetPasswordPage'
import MFAVerifyPage from '@/pages/auth/MFAVerifyPage'
import OAuthCallbackPage from '@/pages/auth/OAuthCallbackPage'

// Dashboard pages
import DashboardPage from '@/pages/dashboard/DashboardPage'

// Admin pages
import UsersPage from '@/pages/admin/UsersPage'
import SessionsPage from '@/pages/admin/SessionsPage'
import AuditLogsPage from '@/pages/admin/AuditLogsPage'

// Profile pages
import ProfilePage from '@/pages/profile/ProfilePage'
import SecurityPage from '@/pages/profile/SecurityPage'
import MFASetupPage from '@/pages/profile/MFASetupPage'

// Analytics pages
import AnalyticsDashboard from '@/pages/analytics/AnalyticsDashboard'

// Catalog pages
import CatalogPage from '@/pages/catalog/CatalogPage'

// Epicerie pages
import {
  EpicerieDashboard,
  VentePOSPage,
  FournisseursPage,
} from '@/pages/epicerie'

// Finance pages
import {
  FinanceDashboard,
  InvoicesPage,
  InvoiceDetailPage,
  InvoiceFormPage,
  TreasuryPage,
  BudgetPage,
  DueDatesPage,
  TransactionsPage,
  AccountsPage,
  ReconciliationPage,
  RulesPage,
  ImportsPage,
} from '@/pages/finance'

// Restaurant pages
import {
  RestaurantDashboard,
  IngredientsPage,
  PlatsPage,
  StockPage,
  ConsumptionsPage,
  ChargesPage,
  RapprochementPage,
} from '@/pages/restaurant'


// Protected Route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Public Route wrapper (redirect if authenticated)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />
        <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
        <Route path="/reset-password" element={<PublicRoute><ResetPasswordPage /></PublicRoute>} />
        <Route path="/mfa/verify" element={<MFAVerifyPage />} />
        <Route path="/auth/callback/:provider" element={<OAuthCallbackPage />} />
      </Route>

      {/* Protected routes */}
      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />

        {/* Admin */}
        <Route path="/admin/users" element={<UsersPage />} />
        <Route path="/admin/sessions" element={<SessionsPage />} />
        <Route path="/admin/audit-logs" element={<AuditLogsPage />} />

        {/* Profile */}
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/profile/security" element={<SecurityPage />} />
        <Route path="/profile/mfa" element={<MFASetupPage />} />

        {/* Analytics */}
        <Route path="/analytics" element={<AnalyticsDashboard />} />

        {/* Catalog - old route redirect */}
        <Route path="/catalog" element={<CatalogPage />} />

        {/* Epicerie */}
        <Route path="/epicerie" element={<EpicerieDashboard />} />
        <Route path="/epicerie/catalogue" element={<CatalogPage />} />
        <Route path="/epicerie/pos" element={<VentePOSPage />} />
        <Route path="/epicerie/fournisseurs" element={<FournisseursPage />} />

        {/* Finance */}
        <Route path="/finance" element={<FinanceDashboard />} />
        <Route path="/finance/factures" element={<InvoicesPage />} />
        <Route path="/finance/factures/new" element={<InvoiceFormPage />} />
        <Route path="/finance/factures/:id" element={<InvoiceDetailPage />} />
        <Route path="/finance/factures/:id/edit" element={<InvoiceFormPage />} />
        <Route path="/finance/tresorerie" element={<TreasuryPage />} />
        <Route path="/finance/budget" element={<BudgetPage />} />
        <Route path="/finance/echeances" element={<DueDatesPage />} />
        <Route path="/finance/transactions" element={<TransactionsPage />} />
        <Route path="/finance/comptes" element={<AccountsPage />} />
        <Route path="/finance/rapprochement" element={<ReconciliationPage />} />
        <Route path="/finance/regles" element={<RulesPage />} />
        <Route path="/finance/imports" element={<ImportsPage />} />

        {/* Restaurant */}
        <Route path="/restaurant" element={<RestaurantDashboard />} />
        <Route path="/restaurant/ingredients" element={<IngredientsPage />} />
        <Route path="/restaurant/plats" element={<PlatsPage />} />
        <Route path="/restaurant/stock" element={<StockPage />} />
        <Route path="/restaurant/ventes" element={<ConsumptionsPage />} />
        <Route path="/restaurant/charges" element={<ChargesPage />} />
        <Route path="/restaurant/rapprochement" element={<RapprochementPage />} />
      </Route>

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
