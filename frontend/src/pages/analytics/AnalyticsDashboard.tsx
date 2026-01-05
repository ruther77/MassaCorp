import { useState, useMemo, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '@/api/analytics'
import { useAuthStore } from '@/stores/authStore'
import SmartFilters, { FilterConfig, FilterSuggestion, FilterPreset } from '@/components/ui/SmartFilters'
import {
  Package,
  ShoppingCart,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  DollarSign,
  Utensils,
  BarChart3,
  RefreshCw,
  Layers,
  Calendar,
  Tag,
  Percent,
} from 'lucide-react'

function formatCurrency(value: string | number): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  }).format(num)
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('fr-FR').format(value)
}

function formatPercent(value: number | null): string {
  if (value === null) return '-'
  return `${value.toFixed(1)}%`
}

interface KPICardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  color?: 'green' | 'blue' | 'orange' | 'red' | 'purple'
}

function KPICard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  color = 'blue',
}: KPICardProps) {
  const colorClasses = {
    green: 'bg-green-500/10 text-green-500',
    blue: 'bg-primary-500/10 text-primary-500',
    orange: 'bg-orange-500/10 text-orange-500',
    red: 'bg-red-500/10 text-red-500',
    purple: 'bg-purple-500/10 text-purple-500',
  }

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-dark-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-dark-400 mt-1">{subtitle}</p>
          )}
          {trend && trendValue && (
            <div
              className={`flex items-center gap-1 mt-2 text-sm ${
                trend === 'up'
                  ? 'text-green-500'
                  : trend === 'down'
                    ? 'text-red-500'
                    : 'text-dark-400'
              }`}
            >
              {trend === 'up' ? (
                <TrendingUp className="w-4 h-4" />
              ) : trend === 'down' ? (
                <TrendingDown className="w-4 h-4" />
              ) : null}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        <div
          className={`w-12 h-12 rounded-lg flex items-center justify-center ${colorClasses[color]}`}
        >
          {icon}
        </div>
      </div>
    </div>
  )
}

export default function AnalyticsDashboard() {
  const { user } = useAuthStore()

  // Filter state
  const [filterValues, setFilterValues] = useState<Record<string, unknown>>({})
  const [searchValue, setSearchValue] = useState('')

  const {
    data: kpis,
    isLoading: isLoadingKPIs,
    refetch: refetchKPIs,
  } = useQuery({
    queryKey: ['analytics-dashboard'],
    queryFn: () => analyticsApi.getDashboardKPIs(),
    refetchInterval: 60000, // Refresh every minute
  })

  const { data: categories } = useQuery({
    queryKey: ['analytics-categories'],
    queryFn: () => analyticsApi.getCategories(),
  })

  const { data: topPlats } = useQuery({
    queryKey: ['analytics-top-plats'],
    queryFn: () => analyticsApi.getTopPlats(5),
  })

  const { data: topProduits } = useQuery({
    queryKey: ['analytics-top-produits'],
    queryFn: () => analyticsApi.getTopProduits(5),
  })

  // Build filter configuration dynamically from categories
  const filterConfig: FilterConfig[] = useMemo(() => {
    const familleOptions = categories
      ? [...new Set(categories.map((c) => c.famille))].map((f) => ({
          value: f,
          label: f,
          count: categories.filter((c) => c.famille === f).length,
        }))
      : []

    return [
      {
        key: 'periode',
        label: 'Periode',
        type: 'date' as const,
        icon: Calendar,
        presets: [
          { label: '7 derniers jours', value: 'last7days' },
          { label: '30 derniers jours', value: 'last30days' },
          { label: 'Ce mois', value: 'thisMonth' },
          { label: 'Trimestre', value: 'thisQuarter' },
        ],
      },
      {
        key: 'famille',
        label: 'Famille',
        type: 'select' as const,
        icon: Tag,
        options: familleOptions,
      },
      {
        key: 'marge',
        label: 'Marge',
        type: 'select' as const,
        icon: Percent,
        options: [
          { value: 'low', label: '< 20%' },
          { value: 'medium', label: '20-40%' },
          { value: 'high', label: '> 40%' },
        ],
      },
      {
        key: 'stock',
        label: 'Stock',
        type: 'select' as const,
        icon: Package,
        options: [
          { value: 'rupture', label: 'En rupture' },
          { value: 'low', label: 'Stock bas' },
          { value: 'ok', label: 'Stock OK' },
        ],
      },
    ]
  }, [categories])

  // Dynamic suggestions based on KPIs
  const suggestions: FilterSuggestion[] = useMemo(() => {
    const sugg: FilterSuggestion[] = []

    if (kpis?.nb_produits_rupture && kpis.nb_produits_rupture > 0) {
      sugg.push({
        label: `${kpis.nb_produits_rupture} produits en rupture`,
        filters: { stock: 'rupture' },
      })
    }

    if (kpis?.food_cost_moyen && kpis.food_cost_moyen > 35) {
      sugg.push({
        label: 'Food cost eleve',
        filters: { marge: 'low' },
      })
    }

    sugg.push({
      label: 'Performance 30j',
      filters: { periode: 'last30days' },
    })

    return sugg
  }, [kpis])

  // Presets for quick filtering
  const presets: FilterPreset[] = useMemo(() => [
    {
      label: 'Vue mensuelle',
      description: 'Performance du mois en cours',
      icon: Calendar,
      filters: { periode: 'thisMonth' },
    },
    {
      label: 'Produits critiques',
      description: 'Stock bas + marge faible',
      icon: AlertTriangle,
      filters: { stock: 'low', marge: 'low' },
    },
    {
      label: 'Top performers',
      description: 'Produits haute marge',
      icon: TrendingUp,
      filters: { marge: 'high', stock: 'ok' },
    },
  ], [])

  // Filter handlers
  const handleFilterChange = useCallback((key: string, value: unknown) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleResetFilters = useCallback(() => {
    setFilterValues({})
    setSearchValue('')
  }, [])

  if (isLoadingKPIs) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-8 h-8 animate-spin text-primary-500" />
      </div>
    )
  }

  const valeurStock = parseFloat(kpis?.valeur_stock_total || '0')
  const ca30j = parseFloat(kpis?.ca_30j || '0')
  const marge30j = parseFloat(kpis?.marge_brute_30j || '0')
  const depensesMois = parseFloat(kpis?.depenses_mois || '0')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-dark-400 mt-1">
            Tableau de bord Data Warehouse - {user?.tenant_name || 'Tenant'}
          </p>
        </div>
        <button
          onClick={() => refetchKPIs()}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Actualiser
        </button>
      </div>

      {/* Smart Filters */}
      <SmartFilters
        filters={filterConfig}
        values={filterValues}
        onChange={handleFilterChange}
        onReset={handleResetFilters}
        suggestions={suggestions}
        presets={presets}
        searchable
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Rechercher produits, categories..."
      />

      {/* KPIs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Valeur Stock"
          value={formatCurrency(valeurStock)}
          subtitle={`${kpis?.nb_produits_rupture || 0} produits en rupture`}
          icon={<Package className="w-6 h-6" />}
          color={kpis?.nb_produits_rupture ? 'orange' : 'green'}
        />

        <KPICard
          title="CA 30 derniers jours"
          value={formatCurrency(ca30j)}
          subtitle={`${formatNumber(kpis?.nb_plats_vendus_30j || 0)} plats vendus`}
          icon={<ShoppingCart className="w-6 h-6" />}
          color="blue"
        />

        <KPICard
          title="Marge brute 30j"
          value={formatCurrency(marge30j)}
          subtitle={
            kpis?.food_cost_moyen
              ? `Food cost: ${formatPercent(kpis.food_cost_moyen)}`
              : undefined
          }
          icon={<TrendingUp className="w-6 h-6" />}
          color="green"
        />

        <KPICard
          title="Depenses du mois"
          value={formatCurrency(depensesMois)}
          icon={<DollarSign className="w-6 h-6" />}
          color="purple"
        />
      </div>

      {/* Additional KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KPICard
          title="Categories"
          value={kpis?.nb_categories || 0}
          subtitle="Categories actives"
          icon={<Layers className="w-6 h-6" />}
          color="blue"
        />

        <KPICard
          title="Rotation Stock"
          value={
            kpis?.rotation_moyenne
              ? `${kpis.rotation_moyenne.toFixed(1)} jours`
              : '-'
          }
          subtitle="Couverture moyenne"
          icon={<RefreshCw className="w-6 h-6" />}
          color="green"
        />

        {kpis?.nb_produits_rupture ? (
          <div className="card border-red-500/20 bg-red-500/5">
            <div className="flex items-center gap-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
              <div>
                <p className="font-semibold text-red-500">
                  {kpis.nb_produits_rupture} produit
                  {kpis.nb_produits_rupture > 1 ? 's' : ''} en rupture
                </p>
                <p className="text-sm text-dark-400">
                  Action requise pour le reapprovisionnement
                </p>
              </div>
            </div>
          </div>
        ) : (
          <KPICard
            title="Stock"
            value="OK"
            subtitle="Aucune rupture detectee"
            icon={<Package className="w-6 h-6" />}
            color="green"
          />
        )}
      </div>

      {/* Charts and Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Plats */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Utensils className="w-5 h-5 text-primary-500" />
              Top 5 Plats (par marge)
            </h2>
          </div>
          {topPlats && topPlats.length > 0 ? (
            <div className="space-y-3">
              {topPlats.map((plat, index) => (
                <div
                  key={plat.plat}
                  className="flex items-center justify-between p-3 bg-dark-700 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-primary-500/20 text-primary-500 flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{plat.plat}</p>
                      <p className="text-sm text-dark-400">
                        {plat.categorie || 'Non categorise'}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-green-500">
                      {formatCurrency(plat.marge_brute)}
                    </p>
                    <p className="text-sm text-dark-400">
                      {formatNumber(plat.nb_vendus)} vendus
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-dark-400 text-center py-8">
              Aucune donnee de vente disponible
            </p>
          )}
        </div>

        {/* Top Produits */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-500" />
              Top 5 Produits (par CA)
            </h2>
          </div>
          {topProduits && topProduits.length > 0 ? (
            <div className="space-y-3">
              {topProduits.map((produit, index) => (
                <div
                  key={produit.produit}
                  className="flex items-center justify-between p-3 bg-dark-700 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-purple-500/20 text-purple-500 flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{produit.produit}</p>
                      <p className="text-sm text-dark-400">
                        {produit.categorie}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">
                      {formatCurrency(produit.ca_total)}
                    </p>
                    <p className="text-sm text-dark-400">
                      Marge: {formatPercent(produit.marge_pct)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-dark-400 text-center py-8">
              Aucune donnee de produit disponible
            </p>
          )}
        </div>
      </div>

      {/* Categories par famille */}
      {categories && categories.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary-500" />
            Categories par famille
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {Object.entries(
              categories.reduce(
                (acc, cat) => {
                  const famille = cat.famille
                  if (!acc[famille]) {
                    acc[famille] = []
                  }
                  acc[famille].push(cat)
                  return acc
                },
                {} as Record<string, typeof categories>
              )
            ).map(([famille, cats]) => (
              <div
                key={famille}
                className="p-3 bg-dark-700 rounded-lg text-center"
              >
                <p className="font-semibold text-primary-500">{famille}</p>
                <p className="text-2xl font-bold mt-1">{cats.length}</p>
                <p className="text-xs text-dark-400">categories</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
