import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { adminApi } from '@/api/admin'
import { formatRelativeTime } from '@/lib/utils'
import {
  Shield,
  Users,
  Monitor,
  AlertTriangle,
  Activity,
  Clock,
  MapPin,
} from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuthStore()

  const { data: sessions } = useQuery({
    queryKey: ['user-sessions'],
    queryFn: () => adminApi.getUserSessions(),
  })

  const activeSessions = sessions?.filter((s) => s.is_active) || []
  const currentSession = sessions?.find((s) => s.is_current)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">
          Bonjour, {user?.first_name} !
        </h1>
        <p className="text-dark-400 mt-1">
          Bienvenue sur votre tableau de bord MassaCorp
        </p>
      </div>

      {/* Security Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Shield className="w-6 h-6 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-dark-400">Statut du compte</p>
              <p className="text-lg font-semibold text-green-500">Sécurisé</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-primary-500/10 flex items-center justify-center">
              <Monitor className="w-6 h-6 text-primary-500" />
            </div>
            <div>
              <p className="text-sm text-dark-400">Sessions actives</p>
              <p className="text-lg font-semibold">{activeSessions.length}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div
              className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                user?.has_mfa
                  ? 'bg-green-500/10'
                  : 'bg-yellow-500/10'
              }`}
            >
              <Shield
                className={`w-6 h-6 ${
                  user?.has_mfa ? 'text-green-500' : 'text-yellow-500'
                }`}
              />
            </div>
            <div>
              <p className="text-sm text-dark-400">2FA</p>
              <p
                className={`text-lg font-semibold ${
                  user?.has_mfa ? 'text-green-500' : 'text-yellow-500'
                }`}
              >
                {user?.has_mfa ? 'Activé' : 'Désactivé'}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-dark-700 flex items-center justify-center">
              <Activity className="w-6 h-6 text-dark-400" />
            </div>
            <div>
              <p className="text-sm text-dark-400">Dernière activité</p>
              <p className="text-lg font-semibold">
                {currentSession
                  ? formatRelativeTime(currentSession.last_seen_at)
                  : '-'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* MFA Warning */}
      {!user?.has_mfa && (
        <div className="card border-yellow-500/20 bg-yellow-500/5">
          <div className="flex items-start gap-4">
            <AlertTriangle className="w-6 h-6 text-yellow-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-yellow-500">
                Authentification à deux facteurs non activée
              </h3>
              <p className="text-sm text-dark-400 mt-1">
                Protégez votre compte en activant l'authentification à deux
                facteurs. Cela ajoute une couche de sécurité supplémentaire.
              </p>
              <a
                href="/profile/mfa"
                className="inline-flex items-center gap-2 mt-3 text-sm font-medium text-yellow-500 hover:text-yellow-400"
              >
                Activer maintenant →
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Current Session */}
      {currentSession && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Session actuelle</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-dark-400" />
              <div>
                <p className="text-sm text-dark-400">Adresse IP</p>
                <p className="font-medium">{currentSession.ip_address}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Monitor className="w-5 h-5 text-dark-400" />
              <div>
                <p className="text-sm text-dark-400">Appareil</p>
                <p className="font-medium truncate max-w-[200px]">
                  {currentSession.user_agent.split(' ')[0]}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-dark-400" />
              <div>
                <p className="text-sm text-dark-400">Connecté depuis</p>
                <p className="font-medium">
                  {formatRelativeTime(currentSession.created_at)}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Actions rapides</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <a
            href="/profile/security"
            className="flex items-center gap-3 p-3 rounded-lg bg-dark-700 hover:bg-dark-600 transition-colors"
          >
            <Shield className="w-5 h-5 text-primary-500" />
            <span className="text-sm font-medium">Sécurité</span>
          </a>
          <a
            href="/profile/mfa"
            className="flex items-center gap-3 p-3 rounded-lg bg-dark-700 hover:bg-dark-600 transition-colors"
          >
            <Shield className="w-5 h-5 text-primary-500" />
            <span className="text-sm font-medium">Configurer 2FA</span>
          </a>
          <a
            href="/admin/sessions"
            className="flex items-center gap-3 p-3 rounded-lg bg-dark-700 hover:bg-dark-600 transition-colors"
          >
            <Monitor className="w-5 h-5 text-primary-500" />
            <span className="text-sm font-medium">Mes sessions</span>
          </a>
          <a
            href="/profile"
            className="flex items-center gap-3 p-3 rounded-lg bg-dark-700 hover:bg-dark-600 transition-colors"
          >
            <Users className="w-5 h-5 text-primary-500" />
            <span className="text-sm font-medium">Mon profil</span>
          </a>
        </div>
      </div>
    </div>
  )
}
