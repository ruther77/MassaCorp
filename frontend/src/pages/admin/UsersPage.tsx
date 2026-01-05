import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '@/api/admin'
import { formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  Search,
  Shield,
  ShieldOff,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

export default function UsersPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page],
    queryFn: () => adminApi.getUsers(page, 20),
  })

  const users = data?.items || []
  const totalPages = data?.pages || 1

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Utilisateurs</h1>
          <p className="text-dark-400 mt-1">
            Gérez les utilisateurs de la plateforme
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher un utilisateur..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Utilisateur
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  2FA
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Rôle
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Créé le
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-dark-400">
                    Aucun utilisateur trouvé
                  </td>
                </tr>
              ) : (
                users
                  .filter(
                    (user) =>
                      user.email.toLowerCase().includes(search.toLowerCase()) ||
                      user.first_name
                        .toLowerCase()
                        .includes(search.toLowerCase()) ||
                      user.last_name.toLowerCase().includes(search.toLowerCase())
                  )
                  .map((user) => (
                    <tr
                      key={user.id}
                      className="border-b border-dark-700/50 hover:bg-dark-700/30"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-primary-600 flex items-center justify-center text-sm font-medium">
                            {user.first_name[0]}
                            {user.last_name[0]}
                          </div>
                          <div>
                            <p className="font-medium">
                              {user.first_name} {user.last_name}
                            </p>
                            <p className="text-sm text-dark-400">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                            user.is_active
                              ? 'bg-green-500/10 text-green-500'
                              : 'bg-red-500/10 text-red-500'
                          )}
                        >
                          {user.is_active ? 'Actif' : 'Inactif'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {user.mfa_enabled || user.has_mfa ? (
                          <Shield className="w-5 h-5 text-green-500" />
                        ) : (
                          <ShieldOff className="w-5 h-5 text-dark-500" />
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                            user.is_superuser
                              ? 'bg-purple-500/10 text-purple-500'
                              : 'bg-dark-600 text-dark-300'
                          )}
                        >
                          {user.is_superuser ? 'Admin' : 'Utilisateur'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-sm text-dark-400">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button className="p-2 hover:bg-dark-700 rounded-lg transition-colors">
                          <MoreVertical className="w-4 h-4 text-dark-400" />
                        </button>
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
            <p className="text-sm text-dark-400">
              Page {page} sur {totalPages}
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost p-2 disabled:opacity-50"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
