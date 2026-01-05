import { useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { authApi } from '@/api/auth'
import { cn } from '@/lib/utils'
import {
  Shield,
  LayoutDashboard,
  Users,
  Monitor,
  FileText,
  User,
  Lock,
  Smartphone,
  LogOut,
  Menu,
  X,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Package,
  Wallet,
  Receipt,
  Landmark,
  PiggyBank,
  CalendarClock,
} from 'lucide-react'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  admin?: boolean
  children?: NavItem[]
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Catalogue', href: '/catalog', icon: Package },
  {
    name: 'Finance',
    href: '/finance',
    icon: Wallet,
    children: [
      { name: 'Vue d\'ensemble', href: '/finance', icon: Wallet },
      { name: 'Factures', href: '/finance/factures', icon: Receipt },
      { name: 'Trésorerie', href: '/finance/tresorerie', icon: Landmark },
      { name: 'Budget', href: '/finance/budget', icon: PiggyBank },
      { name: 'Échéances', href: '/finance/echeances', icon: CalendarClock },
    ]
  },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
]

const adminNavigation: NavItem[] = [
  { name: 'Utilisateurs', href: '/admin/users', icon: Users },
  { name: 'Sessions', href: '/admin/sessions', icon: Monitor },
  { name: 'Audit Logs', href: '/admin/audit-logs', icon: FileText },
]

const profileNavigation: NavItem[] = [
  { name: 'Mon Profil', href: '/profile', icon: User },
  { name: 'Sécurité', href: '/profile/security', icon: Lock },
  { name: 'Authentification 2FA', href: '/profile/mfa', icon: Smartphone },
]

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [expandedMenus, setExpandedMenus] = useState<string[]>(['Finance'])
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } finally {
      logout()
      navigate('/login')
    }
  }

  const toggleMenu = (name: string) => {
    setExpandedMenus(prev =>
      prev.includes(name)
        ? prev.filter(n => n !== name)
        : [...prev, name]
    )
  }

  const isActiveRoute = (href: string) => {
    if (href === '/finance') {
      return location.pathname === '/finance'
    }
    return location.pathname.startsWith(href)
  }

  const NavItemSimple = ({ item }: { item: NavItem }) => (
    <NavLink
      to={item.href}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
          isActive
            ? 'bg-primary-600 text-white'
            : 'text-dark-300 hover:text-white hover:bg-dark-800'
        )
      }
      onClick={() => setSidebarOpen(false)}
    >
      <item.icon className="w-5 h-5" />
      {item.name}
    </NavLink>
  )

  const NavItemWithChildren = ({ item }: { item: NavItem }) => {
    const isExpanded = expandedMenus.includes(item.name)
    const hasActiveChild = item.children?.some(child => isActiveRoute(child.href))

    return (
      <div>
        <button
          onClick={() => toggleMenu(item.name)}
          className={cn(
            'flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm font-medium transition-colors',
            hasActiveChild
              ? 'text-primary-400'
              : 'text-dark-300 hover:text-white hover:bg-dark-800'
          )}
        >
          <div className="flex items-center gap-3">
            <item.icon className="w-5 h-5" />
            {item.name}
          </div>
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
        {isExpanded && item.children && (
          <div className="ml-4 mt-1 space-y-1 border-l border-dark-700 pl-3">
            {item.children.map(child => (
              <NavLink
                key={child.href}
                to={child.href}
                end={child.href === '/finance'}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                    isActive
                      ? 'bg-primary-600/20 text-primary-400'
                      : 'text-dark-400 hover:text-white hover:bg-dark-800'
                  )
                }
                onClick={() => setSidebarOpen(false)}
              >
                <child.icon className="w-4 h-4" />
                {child.name}
              </NavLink>
            ))}
          </div>
        )}
      </div>
    )
  }

  const NavItem = ({ item }: { item: NavItem }) => {
    if (item.children) {
      return <NavItemWithChildren item={item} />
    }
    return <NavItemSimple item={item} />
  }

  return (
    <div className="min-h-screen bg-dark-900">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed top-0 left-0 z-50 h-full w-64 bg-dark-800 border-r border-dark-700 transform transition-transform lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between p-4 border-b border-dark-700">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-primary-500" />
              <span className="text-lg font-bold">MassaCorp</span>
            </div>
            <button
              className="lg:hidden text-dark-400 hover:text-white"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto scrollbar-thin">
            {/* Main Navigation */}
            <div className="space-y-1">
              {navigation.map((item) => (
                <NavItem key={item.href} item={item} />
              ))}
            </div>

            {/* Admin Section */}
            {user?.is_superuser && (
              <div className="pt-6">
                <p className="px-3 text-xs font-semibold text-dark-500 uppercase tracking-wider mb-2">
                  Administration
                </p>
                <div className="space-y-1">
                  {adminNavigation.map((item) => (
                    <NavItemSimple key={item.href} item={item} />
                  ))}
                </div>
              </div>
            )}

            {/* Profile Section */}
            <div className="pt-6">
              <p className="px-3 text-xs font-semibold text-dark-500 uppercase tracking-wider mb-2">
                Mon compte
              </p>
              <div className="space-y-1">
                {profileNavigation.map((item) => (
                  <NavItemSimple key={item.href} item={item} />
                ))}
              </div>
            </div>
          </nav>

          {/* User menu */}
          <div className="p-4 border-t border-dark-700">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium text-red-400 hover:text-red-300 hover:bg-dark-700 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              Déconnexion
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-dark-800/80 backdrop-blur-sm border-b border-dark-700">
          <div className="flex items-center justify-between px-4 py-3">
            <button
              className="lg:hidden text-dark-400 hover:text-white"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="w-6 h-6" />
            </button>

            <div className="flex-1" />

            {/* User dropdown */}
            <div className="relative">
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-dark-700 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-sm font-medium">
                  {user?.first_name?.[0]}
                  {user?.last_name?.[0]}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-medium">
                    {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-xs text-dark-400">{user?.email}</p>
                </div>
                <ChevronDown className="w-4 h-4 text-dark-400" />
              </button>

              {profileOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setProfileOpen(false)}
                  />
                  <div className="absolute right-0 mt-2 w-56 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-50">
                    <div className="p-2">
                      {profileNavigation.map((item) => (
                        <NavLink
                          key={item.href}
                          to={item.href}
                          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-dark-300 hover:text-white hover:bg-dark-700"
                          onClick={() => setProfileOpen(false)}
                        >
                          <item.icon className="w-4 h-4" />
                          {item.name}
                        </NavLink>
                      ))}
                      <hr className="my-2 border-dark-700" />
                      <button
                        onClick={handleLogout}
                        className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-red-400 hover:text-red-300 hover:bg-dark-700"
                      >
                        <LogOut className="w-4 h-4" />
                        Déconnexion
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
