/**
 * CatalogPage - Catalogue Produits METRO (v3)
 *
 * Interface améliorée avec:
 * - Données depuis l'API backend PostgreSQL
 * - Tri cliquable sur colonnes
 * - Filtres visuels en chips
 * - Suggestions rapides
 * - Colisage et prix unitaires réels
 */
import { useState, useMemo, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'
import apiClient from '@/api/client'
import {
  Package,
  Search,
  Wine,
  Beer,
  ShoppingCart,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  X,
  TrendingUp,
  Star,
  Filter,
  RotateCcw,
  Sparkles,
  ArrowUpDown,
  Eye,
  HelpCircle,
  Loader2,
} from 'lucide-react'

// ============================================================================
// TYPES - API Response
// ============================================================================

interface MetroProduitAPI {
  id: number
  ean: string
  article_numero: string | null
  designation: string
  colisage_moyen: number
  unite: string
  volume_unitaire: string | null
  quantite_colis_totale: string
  quantite_unitaire_totale: string
  montant_total_ht: string
  montant_total_tva: string
  montant_total: string
  nb_achats: number
  prix_unitaire_moyen: string
  prix_unitaire_min: string
  prix_unitaire_max: string
  prix_colis_moyen: string
  taux_tva: string
  categorie_id: number | null
  famille: string
  categorie: string
  sous_categorie: string | null
  regie: string | null
  vol_alcool: string | null
  premier_achat: string | null
  dernier_achat: string | null
}

interface MetroSummaryAPI {
  nb_factures: number
  nb_produits: number
  nb_lignes: number
  total_ht: string
  total_tva: string
  total_ttc: string
  date_premiere_facture: string | null
  date_derniere_facture: string | null
}

interface MetroProduitListAPI {
  items: MetroProduitAPI[]
  total: number
  page: number
  per_page: number
  pages: number
}

// Internal type (converted from API)
interface MetroProduit {
  id: number
  ean: string
  designation: string
  colisage: number
  prix_unitaire: number
  prix_colis: number
  quantite_totale: number
  montant_total: number
  montant_tva: number
  taux_tva: number
  nb_achats: number
  regie: string | null
  vol_alcool: number | null
  categorie: string
  famille: string
}

type SortKey = 'designation' | 'prix_unitaire' | 'quantite_totale' | 'montant_total' | 'taux_tva' | 'nb_achats'
type SortDirection = 'asc' | 'desc'

// ============================================================================
// HELPERS
// ============================================================================

function convertApiProduct(p: MetroProduitAPI): MetroProduit {
  return {
    id: p.id,
    ean: p.ean,
    designation: p.designation,
    colisage: p.colisage_moyen,
    prix_unitaire: parseFloat(p.prix_unitaire_moyen) || 0,
    prix_colis: parseFloat(p.prix_colis_moyen) || 0,
    quantite_totale: parseFloat(p.quantite_unitaire_totale) || 0,
    montant_total: parseFloat(p.montant_total_ht) || 0,
    montant_tva: parseFloat(p.montant_total_tva) || 0,
    taux_tva: parseFloat(p.taux_tva) || 20,
    nb_achats: p.nb_achats,
    regie: p.regie,
    vol_alcool: p.vol_alcool ? parseFloat(p.vol_alcool) : null,
    categorie: p.categorie,
    famille: p.famille,
  }
}

function getCategorie(regie: string | null): string {
  switch (regie) {
    case 'S': return 'Spiritueux'
    case 'B': return 'Bières'
    case 'T': return 'Vins'
    case 'M': return 'Alcools'
    default: return 'Epicerie'
  }
}

function formatCurrency(value: number | null): string {
  if (value === null) return '—'
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value)
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('fr-FR').format(value)
}

// ============================================================================
// CATEGORY CONFIG
// ============================================================================

const CATEGORIES = {
  'Epicerie': { color: 'slate', icon: ShoppingCart, bg: 'bg-slate-500/20', text: 'text-slate-300', border: 'border-slate-500/30' },
  'Spiritueux': { color: 'amber', icon: Wine, bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
  'Bières': { color: 'yellow', icon: Beer, bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  'Vins': { color: 'purple', icon: Wine, bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30' },
  'Alcools': { color: 'blue', icon: Package, bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
} as const

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

function CategoryBadge({ regie, vol, onClick }: { regie: string | null; vol: number | null; onClick?: () => void }) {
  const cat = getCategorie(regie)
  const config = CATEGORIES[cat as keyof typeof CATEGORIES] || CATEGORIES['Epicerie']
  const Icon = config.icon

  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium transition-all',
        config.bg, config.text,
        onClick && 'hover:scale-105 cursor-pointer'
      )}
    >
      <Icon className="w-3 h-3" />
      {cat}
      {vol ? ` ${vol}%` : ''}
    </button>
  )
}

function SortIndicator({ direction }: { direction: SortDirection | null }) {
  if (!direction) {
    return <ChevronsUpDown className="h-3.5 w-3.5 text-slate-500" />
  }
  return direction === 'asc'
    ? <ChevronUp className="h-3.5 w-3.5 text-blue-400" />
    : <ChevronDown className="h-3.5 w-3.5 text-blue-400" />
}

function SortableHeader({
  children,
  sortKey,
  currentSort,
  onSort,
  align = 'left',
}: {
  children: React.ReactNode
  sortKey: SortKey
  currentSort: { key: SortKey; direction: SortDirection } | null
  onSort: (key: SortKey) => void
  align?: 'left' | 'right' | 'center'
}) {
  const isActive = currentSort?.key === sortKey

  return (
    <th
      onClick={() => onSort(sortKey)}
      className={cn(
        'px-4 py-3 text-xs font-semibold uppercase tracking-wider cursor-pointer select-none transition-colors',
        'hover:bg-white/5 hover:text-white',
        isActive ? 'text-blue-400' : 'text-slate-300',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center'
      )}
    >
      <div className={cn(
        'flex items-center gap-1.5',
        align === 'right' && 'justify-end',
        align === 'center' && 'justify-center'
      )}>
        {children}
        <SortIndicator direction={isActive ? currentSort.direction : null} />
      </div>
    </th>
  )
}

function CategoryChip({
  category,
  count,
  isActive,
  onClick,
}: {
  category: string
  count: number
  isActive: boolean
  onClick: () => void
}) {
  const config = CATEGORIES[category as keyof typeof CATEGORIES] || CATEGORIES['Epicerie']
  const Icon = config.icon

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-all',
        'border',
        isActive
          ? `${config.bg} ${config.text} ${config.border}`
          : 'border-white/10 text-slate-400 hover:bg-white/5 hover:text-white'
      )}
    >
      <Icon className="w-4 h-4" />
      {category}
      <span className={cn(
        'px-1.5 py-0.5 rounded-md text-xs',
        isActive ? 'bg-white/20' : 'bg-white/10'
      )}>
        {count}
      </span>
    </button>
  )
}

function QuickFilter({
  label,
  icon: Icon,
  isActive,
  onClick,
}: {
  label: string
  icon: React.ComponentType<{ className?: string }>
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
        'border',
        isActive
          ? 'border-blue-500/50 bg-blue-500/20 text-blue-300'
          : 'border-white/10 text-slate-400 hover:bg-white/5 hover:text-white'
      )}
    >
      <Icon className="w-3 h-3" />
      {label}
    </button>
  )
}

function ProductCard({ product, onClick, rank }: { product: MetroProduit; onClick: () => void; rank?: number }) {
  return (
    <div
      onClick={onClick}
      className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3 cursor-pointer hover:bg-white/10 hover:border-white/20 transition-all"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {rank && rank <= 3 && (
              <span className={cn(
                'w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold',
                rank === 1 && 'bg-yellow-500/30 text-yellow-400',
                rank === 2 && 'bg-slate-400/30 text-slate-300',
                rank === 3 && 'bg-amber-700/30 text-amber-600'
              )}>
                {rank}
              </span>
            )}
            <h3 className="font-semibold text-white truncate">{product.designation}</h3>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-xs text-slate-500 font-mono">{product.ean}</p>
            {product.colisage > 1 && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                x{product.colisage}
              </span>
            )}
          </div>
        </div>
        <CategoryBadge regie={product.regie} vol={product.vol_alcool} />
      </div>

      <div className="grid grid-cols-4 gap-3 pt-2 border-t border-white/10">
        <div>
          <p className="text-xs text-slate-500">Prix unit.</p>
          <p className="text-sm font-mono text-white">{formatCurrency(product.prix_unitaire)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Qté</p>
          <p className="text-sm font-mono font-semibold text-emerald-400">{formatNumber(product.quantite_totale)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Total HT</p>
          <p className="text-sm font-mono font-semibold text-blue-400">{formatCurrency(product.montant_total)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">TVA</p>
          <p className={cn(
            'text-sm font-mono font-semibold',
            product.taux_tva === 20 && 'text-rose-400',
            product.taux_tva === 10 && 'text-orange-400',
            product.taux_tva === 5.5 && 'text-yellow-400',
            !product.taux_tva && 'text-slate-400'
          )}>
            {product.taux_tva ? `${product.taux_tva}%` : '—'}
          </p>
        </div>
      </div>
    </div>
  )
}

function WelcomeGuide({ onDismiss }: { onDismiss: () => void }) {
  return (
    <div className="relative rounded-xl border border-blue-500/30 bg-gradient-to-r from-blue-500/10 to-purple-500/10 p-4 mb-6">
      <button
        onClick={onDismiss}
        className="absolute top-3 right-3 p-1 text-slate-400 hover:text-white rounded-lg hover:bg-white/10"
      >
        <X className="w-4 h-4" />
      </button>
      <div className="flex items-start gap-4">
        <div className="p-2 rounded-lg bg-blue-500/20">
          <HelpCircle className="w-5 h-5 text-blue-400" />
        </div>
        <div className="space-y-2">
          <h3 className="font-semibold text-white">Bienvenue dans le catalogue METRO</h3>
          <ul className="text-sm text-slate-300 space-y-1">
            <li className="flex items-center gap-2">
              <ArrowUpDown className="w-3.5 h-3.5 text-blue-400" />
              <span>Cliquez sur les <strong>en-têtes de colonnes</strong> pour trier</span>
            </li>
            <li className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-purple-400" />
              <span>Utilisez les <strong>chips catégories</strong> pour filtrer</span>
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Essayez les <strong>filtres rapides</strong> pour des vues pré-configurées</span>
            </li>
            <li className="flex items-center gap-2">
              <Eye className="w-3.5 h-3.5 text-emerald-400" />
              <span>Cliquez sur une <strong>ligne</strong> pour voir les détails</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

function TopInsights({ products }: { products: MetroProduit[] }) {
  const top3 = products.slice(0, 3)
  const totalValue = products.reduce((sum, p) => sum + p.montant_total, 0)
  const top3Value = top3.reduce((sum, p) => sum + p.montant_total, 0)
  const top3Pct = totalValue > 0 ? ((top3Value / totalValue) * 100).toFixed(1) : '0'

  return (
    <div className="rounded-xl border border-white/10 bg-gradient-to-r from-amber-500/5 to-yellow-500/5 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Star className="w-4 h-4 text-amber-400" />
        <span className="text-sm font-semibold text-white">Top 3 produits</span>
        <span className="text-xs text-slate-400">({top3Pct}% du CA)</span>
      </div>
      <div className="space-y-2">
        {top3.map((p, idx) => (
          <div key={p.ean} className="flex items-center gap-3">
            <span className={cn(
              'w-5 h-5 flex items-center justify-center rounded-full text-xs font-bold shrink-0',
              idx === 0 && 'bg-yellow-500/30 text-yellow-400',
              idx === 1 && 'bg-slate-400/30 text-slate-300',
              idx === 2 && 'bg-amber-700/30 text-amber-600'
            )}>
              {idx + 1}
            </span>
            <span className="flex-1 text-sm text-slate-200 truncate">{p.designation}</span>
            <span className="text-sm font-mono font-semibold text-blue-400">{formatCurrency(p.montant_total)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function CatalogPage() {
  // State
  const [products, setProducts] = useState<MetroProduit[]>([])
  const [summary, setSummary] = useState<MetroSummaryAPI | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchValue, setSearchValue] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [sortConfig, setSortConfig] = useState<{ key: SortKey; direction: SortDirection } | null>({
    key: 'montant_total',
    direction: 'desc'
  })
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedProduct, setSelectedProduct] = useState<MetroProduit | null>(null)
  const [showGuide, setShowGuide] = useState(() => {
    return localStorage.getItem('catalog-guide-dismissed') !== 'true'
  })
  const [quickFilter, setQuickFilter] = useState<string | null>(null)
  const pageSize = 20

  // Load data from API
  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // Fetch all products (pagination will be client-side for sorting/filtering flexibility)
      const [productsRes, summaryRes] = await Promise.all([
        apiClient.get<MetroProduitListAPI>('/metro/products', { params: { per_page: 1000 } }),
        apiClient.get<MetroSummaryAPI>('/metro/summary'),
      ])

      setProducts(productsRes.data.items.map(convertApiProduct))
      setSummary(summaryRes.data)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Erreur lors du chargement des données'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    products.forEach(p => {
      counts[p.categorie] = (counts[p.categorie] || 0) + 1
    })
    return counts
  }, [products])

  // Filtered products
  const filteredProducts = useMemo(() => {
    let result = products

    // Search
    if (searchValue) {
      const search = searchValue.toLowerCase()
      result = result.filter(p =>
        p.designation.toLowerCase().includes(search) ||
        p.ean.includes(search)
      )
    }

    // Category
    if (categoryFilter) {
      result = result.filter(p => p.categorie === categoryFilter)
    }

    // Quick filters
    if (quickFilter === 'top-sales') {
      result = [...result].sort((a, b) => b.montant_total - a.montant_total).slice(0, 50)
    } else if (quickFilter === 'frequent') {
      result = result.filter(p => p.nb_achats >= 5)
    } else if (quickFilter === 'alcohol') {
      result = result.filter(p => p.regie !== null)
    } else if (quickFilter === 'expensive') {
      result = result.filter(p => p.prix_unitaire >= 20)
    }

    return result
  }, [products, searchValue, categoryFilter, quickFilter])

  // Sorted products
  const sortedProducts = useMemo(() => {
    if (!sortConfig) return filteredProducts

    return [...filteredProducts].sort((a, b) => {
      const aVal = a[sortConfig.key]
      const bVal = b[sortConfig.key]

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        const comparison = aVal.localeCompare(bVal, 'fr', { sensitivity: 'base' })
        return sortConfig.direction === 'desc' ? -comparison : comparison
      }

      const comparison = (aVal as number) - (bVal as number)
      return sortConfig.direction === 'desc' ? -comparison : comparison
    })
  }, [filteredProducts, sortConfig])

  // Pagination
  const totalPages = Math.ceil(sortedProducts.length / pageSize)
  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return sortedProducts.slice(start, start + pageSize)
  }, [sortedProducts, currentPage])

  // Reset page on filter change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchValue, categoryFilter, quickFilter, sortConfig])

  // Handlers
  const handleSort = useCallback((key: SortKey) => {
    setSortConfig(prev => {
      if (prev?.key !== key) return { key, direction: 'desc' }
      if (prev.direction === 'desc') return { key, direction: 'asc' }
      return null
    })
  }, [])

  const handleRefresh = useCallback(() => {
    loadData()
  }, [loadData])

  const handleDismissGuide = useCallback(() => {
    setShowGuide(false)
    localStorage.setItem('catalog-guide-dismissed', 'true')
  }, [])

  const handleReset = useCallback(() => {
    setSearchValue('')
    setCategoryFilter(null)
    setQuickFilter(null)
    setSortConfig({ key: 'montant_total', direction: 'desc' })
  }, [])

  const hasFilters = searchValue || categoryFilter || quickFilter

  // Loading
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-64 bg-white/10 rounded-lg animate-pulse" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-white/5 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="h-12 bg-white/5 rounded-xl animate-pulse" />
        <div className="h-96 bg-white/5 rounded-xl animate-pulse" />
      </div>
    )
  }

  // Error
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-red-400">{error}</p>
        <button
          onClick={handleRefresh}
          className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
        >
          Réessayer
        </button>
      </div>
    )
  }

  const activeFiltersCount = [searchValue, categoryFilter, quickFilter].filter(Boolean).length

  return (
    <div className="space-y-6">
      {/* Guide */}
      {showGuide && <WelcomeGuide onDismiss={handleDismissGuide} />}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Package className="w-7 h-7 text-blue-500" />
            Catalogue Produits METRO
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {formatNumber(summary?.nb_produits || products.length)} produits · {summary?.nb_factures || 0} factures · {formatCurrency(parseFloat(summary?.total_ht || '0'))} HT
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          Actualiser
        </button>
      </div>

      {/* KPIs + Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-2xl font-bold text-white">{formatNumber(summary?.nb_produits || products.length)}</p>
            <p className="text-xs text-slate-400">Produits uniques</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-2xl font-bold text-emerald-400">{formatCurrency(parseFloat(summary?.total_ht || '0'))}</p>
            <p className="text-xs text-slate-400">Total HT</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-2xl font-bold text-rose-400">{formatCurrency(parseFloat(summary?.total_tva || '0'))}</p>
            <p className="text-xs text-slate-400">Total TVA</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-2xl font-bold text-blue-400">{summary?.nb_factures || 0}</p>
            <p className="text-xs text-slate-400">Factures</p>
          </div>
        </div>
        <TopInsights products={sortedProducts} />
      </div>

      {/* Search + Quick Filters */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              placeholder="Rechercher par nom ou EAN..."
              className="w-full pl-10 pr-10 py-2.5 text-sm rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
            />
            {searchValue && (
              <button
                onClick={() => setSearchValue('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Filtres rapides:
            </span>
            <QuickFilter
              label="Top 50 ventes"
              icon={TrendingUp}
              isActive={quickFilter === 'top-sales'}
              onClick={() => setQuickFilter(quickFilter === 'top-sales' ? null : 'top-sales')}
            />
            <QuickFilter
              label="Fréquents (5+)"
              icon={Star}
              isActive={quickFilter === 'frequent'}
              onClick={() => setQuickFilter(quickFilter === 'frequent' ? null : 'frequent')}
            />
            <QuickFilter
              label="Alcools"
              icon={Wine}
              isActive={quickFilter === 'alcohol'}
              onClick={() => setQuickFilter(quickFilter === 'alcohol' ? null : 'alcohol')}
            />
            <QuickFilter
              label="Premium (20€+)"
              icon={Star}
              isActive={quickFilter === 'expensive'}
              onClick={() => setQuickFilter(quickFilter === 'expensive' ? null : 'expensive')}
            />
          </div>

          {hasFilters && (
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Réinitialiser ({activeFiltersCount})
            </button>
          )}
        </div>

        {/* Category Chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <CategoryChip
            category="Tous"
            count={products.length}
            isActive={categoryFilter === null}
            onClick={() => setCategoryFilter(null)}
          />
          {Object.entries(categoryCounts)
            .sort((a, b) => b[1] - a[1])
            .map(([cat, count]) => (
              <CategoryChip
                key={cat}
                category={cat}
                count={count}
                isActive={categoryFilter === cat}
                onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
              />
            ))}
        </div>
      </div>

      {/* Results summary */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">
          {formatNumber(sortedProducts.length)} résultats
          {sortConfig && (
            <span className="text-slate-500">
              {' '}· trié par {
                sortConfig.key === 'montant_total' ? 'montant' :
                sortConfig.key === 'quantite_totale' ? 'quantité' :
                sortConfig.key === 'prix_unitaire' ? 'prix unitaire' :
                sortConfig.key === 'nb_achats' ? 'achats' :
                sortConfig.key === 'taux_tva' ? 'TVA' :
                'nom'
              } ({sortConfig.direction === 'desc' ? 'décroissant' : 'croissant'})
            </span>
          )}
        </span>
        {totalPages > 1 && (
          <span className="text-slate-500">
            Page {currentPage} / {totalPages}
          </span>
        )}
      </div>

      {/* Table Desktop */}
      <div className="hidden md:block overflow-x-auto rounded-xl border border-white/10 bg-white/5">
        <table className="w-full text-sm">
          <thead className="bg-white/5 border-b border-white/10">
            <tr>
              <th className="w-10 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400">
                #
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-300">
                EAN
              </th>
              <SortableHeader sortKey="designation" currentSort={sortConfig} onSort={handleSort}>
                Produit
              </SortableHeader>
              <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-300">
                Catégorie
              </th>
              <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-slate-300">
                Colis
              </th>
              <SortableHeader sortKey="prix_unitaire" currentSort={sortConfig} onSort={handleSort} align="right">
                Prix unit.
              </SortableHeader>
              <SortableHeader sortKey="quantite_totale" currentSort={sortConfig} onSort={handleSort} align="right">
                Quantité
              </SortableHeader>
              <SortableHeader sortKey="montant_total" currentSort={sortConfig} onSort={handleSort} align="right">
                Total HT
              </SortableHeader>
              <SortableHeader sortKey="taux_tva" currentSort={sortConfig} onSort={handleSort} align="center">
                TVA
              </SortableHeader>
              <SortableHeader sortKey="nb_achats" currentSort={sortConfig} onSort={handleSort} align="center">
                Achats
              </SortableHeader>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {paginatedProducts.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-12 text-center text-slate-400">
                  Aucun produit trouvé
                </td>
              </tr>
            ) : (
              paginatedProducts.map((product, idx) => {
                const globalRank = (currentPage - 1) * pageSize + idx + 1
                return (
                  <tr
                    key={product.ean + idx}
                    onClick={() => setSelectedProduct(product)}
                    className="hover:bg-white/5 cursor-pointer transition-colors group"
                  >
                    <td className="px-4 py-3">
                      {globalRank <= 3 && !hasFilters ? (
                        <span className={cn(
                          'w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold',
                          globalRank === 1 && 'bg-yellow-500/30 text-yellow-400',
                          globalRank === 2 && 'bg-slate-400/30 text-slate-300',
                          globalRank === 3 && 'bg-amber-700/30 text-amber-600'
                        )}>
                          {globalRank}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-xs">{globalRank}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-slate-400">{product.ean}</span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium text-white truncate max-w-xs group-hover:text-blue-300 transition-colors">
                        {product.designation}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <CategoryBadge
                        regie={product.regie}
                        vol={product.vol_alcool}
                        onClick={() => setCategoryFilter(product.categorie)}
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      {product.colisage > 1 ? (
                        <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 text-xs font-medium">
                          x{product.colisage}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-mono text-slate-200">{formatCurrency(product.prix_unitaire)}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-medium text-emerald-400">{formatNumber(product.quantite_totale)}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="font-bold text-blue-400">{formatCurrency(product.montant_total)}</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium',
                        product.taux_tva === 20 && 'bg-rose-500/20 text-rose-400',
                        product.taux_tva === 10 && 'bg-orange-500/20 text-orange-400',
                        product.taux_tva === 5.5 && 'bg-yellow-500/20 text-yellow-400',
                        product.taux_tva === 2.1 && 'bg-emerald-500/20 text-emerald-400',
                        !product.taux_tva && 'bg-slate-500/20 text-slate-400'
                      )}>
                        {product.taux_tva ? `${product.taux_tva}%` : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300">
                        {product.nb_achats}x
                      </span>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Cards Mobile */}
      <div className="md:hidden space-y-3">
        {paginatedProducts.map((product, idx) => (
          <ProductCard
            key={product.ean + idx}
            product={product}
            onClick={() => setSelectedProduct(product)}
            rank={!hasFilters ? (currentPage - 1) * pageSize + idx + 1 : undefined}
          />
        ))}
        {paginatedProducts.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            Aucun produit trouvé
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 text-sm">
          <div className="text-slate-400">
            {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, sortedProducts.length)} sur {sortedProducts.length}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className={cn(
                'px-3 py-1.5 rounded-lg transition-colors',
                currentPage === 1
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'text-slate-300 hover:bg-white/10'
              )}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-1 mx-2">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let page: number
                if (totalPages <= 5) {
                  page = i + 1
                } else if (currentPage <= 3) {
                  page = i + 1
                } else if (currentPage >= totalPages - 2) {
                  page = totalPages - 4 + i
                } else {
                  page = currentPage - 2 + i
                }

                return (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={cn(
                      'w-8 h-8 rounded-lg text-sm font-medium transition-colors',
                      page === currentPage
                        ? 'bg-blue-500 text-white'
                        : 'text-slate-300 hover:bg-white/10'
                    )}
                  >
                    {page}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className={cn(
                'px-3 py-1.5 rounded-lg transition-colors',
                currentPage === totalPages
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'text-slate-300 hover:bg-white/10'
              )}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end md:items-center justify-center"
          onClick={() => setSelectedProduct(null)}
        >
          <div
            className="bg-slate-800 rounded-t-2xl md:rounded-2xl w-full md:max-w-lg max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="p-6 space-y-4">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white">{selectedProduct.designation}</h2>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-sm text-slate-400 font-mono">{selectedProduct.ean}</p>
                    {selectedProduct.colisage > 1 && (
                      <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300">
                        Colisage: x{selectedProduct.colisage}
                      </span>
                    )}
                  </div>
                </div>
                <CategoryBadge regie={selectedProduct.regie} vol={selectedProduct.vol_alcool} />
              </div>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/10">
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Prix unitaire</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(selectedProduct.prix_unitaire)}</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Prix colis</p>
                  <p className="text-2xl font-bold text-slate-300">{formatCurrency(selectedProduct.prix_colis)}</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Quantité (unités)</p>
                  <p className="text-2xl font-bold text-emerald-400">{formatNumber(selectedProduct.quantite_totale)}</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Nombre d'achats</p>
                  <p className="text-2xl font-bold text-purple-400">{selectedProduct.nb_achats}x</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Montant HT</p>
                  <p className="text-2xl font-bold text-blue-400">{formatCurrency(selectedProduct.montant_total)}</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Taux TVA</p>
                  <p className="text-2xl font-bold text-orange-400">{selectedProduct.taux_tva || 0}%</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Montant TVA</p>
                  <p className="text-2xl font-bold text-rose-400">{formatCurrency(selectedProduct.montant_tva)}</p>
                </div>
                <div className="rounded-xl bg-white/5 p-4">
                  <p className="text-xs text-slate-400">Total TTC</p>
                  <p className="text-2xl font-bold text-emerald-400">{formatCurrency(selectedProduct.montant_total + selectedProduct.montant_tva)}</p>
                </div>
              </div>

              <button
                onClick={() => setSelectedProduct(null)}
                className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl transition-colors"
              >
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
