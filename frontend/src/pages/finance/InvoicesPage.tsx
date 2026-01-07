import { useState, useEffect, useMemo } from 'react';
import {
  Search,
  FileText,
  ChevronDown,
  ChevronRight,
  Calendar,
  Wine,
  Beer,
  Package,
  ChevronLeft,
  Loader2,
  Building2,
  Filter,
  TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  Input,
  Select,
  Badge,
  Card,
  CardContent,
  EmptyState,
  StatCard,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatDate } from '../../lib/utils';

import apiClient from '@/api/client';

// ============================================================================
// TYPES API
// ============================================================================

interface UnifiedFactureItem {
  id: number
  source: string // METRO, TAIYAT, EUROCIEL
  numero: string
  date_facture: string
  fournisseur: string
  total_ht: number | null
  total_tva: number | null
  total_ttc: number
  nb_lignes: number
  type_document: string
}

interface UnifiedFacturesResponse {
  items: UnifiedFactureItem[]
  total: number
  page: number
  per_page: number
  pages: number
  summary: {
    total_factures: number
    total_ht: number
    total_tva: number
    total_ttc: number
    par_fournisseur: Record<string, {
      nb_factures: number
      total_ht: number
      total_tva: number
      total_ttc: number
    }>
  }
}

interface FactureDetailLigne {
  ean?: string
  designation: string
  quantite?: number
  quantite_colis?: number
  quantite_unitaire?: number
  colis?: number
  prix_unitaire?: number
  montant_ht?: number
  montant_ttc?: number
  taux_tva?: number
  regie?: string | null
  vol_alcool?: number | null
  categorie?: string
  provenance?: string
  poids?: number
}

interface FactureDetail {
  source: string
  id: number
  numero: string
  date_facture: string
  magasin?: string
  client_nom?: string
  total_ht: number
  total_tva: number
  total_ttc: number
  lignes: FactureDetailLigne[]
}

// ============================================================================
// CONSTANTS
// ============================================================================

const sourceOptions = [
  { value: '', label: 'Tous les fournisseurs' },
  { value: 'METRO', label: 'METRO' },
  { value: 'TAIYAT', label: 'TAIYAT' },
  { value: 'EUROCIEL', label: 'EUROCIEL' },
];

const SOURCE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  METRO: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
  TAIYAT: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  EUROCIEL: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
};

// ============================================================================
// HELPERS
// ============================================================================

function formatCurrency(amount: number | null): string {
  if (amount === null || amount === undefined) return '—'
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount)
}

function SourceBadge({ source }: { source: string }) {
  const colors = SOURCE_COLORS[source] || { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/30' }
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium', colors.bg, colors.text)}>
      <Building2 className="w-3 h-3" />
      {source}
    </span>
  )
}

function CategoryBadge({ regie, vol }: { regie: string | null; vol: number | null }) {
  if (!regie) return null

  const config: Record<string, { color: string; bg: string; icon: React.ReactNode }> = {
    S: { color: 'text-amber-400', bg: 'bg-amber-500/20', icon: <Wine className="w-3 h-3" /> },
    B: { color: 'text-yellow-400', bg: 'bg-yellow-500/20', icon: <Beer className="w-3 h-3" /> },
    T: { color: 'text-purple-400', bg: 'bg-purple-500/20', icon: <Wine className="w-3 h-3" /> },
  }

  const c = config[regie] || { color: 'text-slate-400', bg: 'bg-slate-500/20', icon: <Package className="w-3 h-3" /> }

  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs', c.bg, c.color)}>
      {c.icon}
      {regie}{vol ? ` ${vol}%` : ''}
    </span>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function InvoicesPage() {
  // State
  const [factures, setFactures] = useState<UnifiedFactureItem[]>([])
  const [summary, setSummary] = useState<UnifiedFacturesResponse['summary'] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [searchValue, setSearchValue] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 20

  // Expanded facture detail
  const [expandedFacture, setExpandedFacture] = useState<string | null>(null)
  const [expandedFactureData, setExpandedFactureData] = useState<FactureDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Load data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const params: Record<string, string | number> = {
          page: 1,
          per_page: 10000, // Load all for client-side filtering
        }
        if (sourceFilter) {
          params.source = sourceFilter
        }

        const res = await apiClient.get<UnifiedFacturesResponse>('/finance/factures-fournisseurs', { params })
        setFactures(res.data.items)
        setSummary(res.data.summary)
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Erreur lors du chargement des factures'
        setError(message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [sourceFilter])

  // Handle expand facture
  const handleExpandFacture = async (facture: UnifiedFactureItem) => {
    const key = `${facture.source}-${facture.id}`
    if (expandedFacture === key) {
      setExpandedFacture(null)
      setExpandedFactureData(null)
      return
    }

    setExpandedFacture(key)
    setLoadingDetail(true)
    try {
      const res = await apiClient.get<FactureDetail>(
        `/finance/factures-fournisseurs/${facture.source}/${facture.id}`
      )
      setExpandedFactureData(res.data)
    } catch {
      setExpandedFactureData(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  // Filter and paginate
  const filteredFactures = useMemo(() => {
    if (!searchValue) return factures

    const search = searchValue.toLowerCase()
    return factures.filter(f =>
      f.numero.toLowerCase().includes(search) ||
      f.fournisseur.toLowerCase().includes(search) ||
      f.source.toLowerCase().includes(search)
    )
  }, [factures, searchValue])

  const totalPages = Math.ceil(filteredFactures.length / pageSize)
  const paginatedFactures = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredFactures.slice(start, start + pageSize)
  }, [filteredFactures, currentPage])

  // Reset page on filter change
  useEffect(() => {
    setCurrentPage(1)
  }, [searchValue, sourceFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        <span className="ml-2 text-slate-300">Chargement des factures fournisseurs...</span>
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        type="error"
        title="Erreur de chargement"
        description={error}
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Factures Fournisseurs"
        subtitle="Factures METRO, TAIYAT et EUROCIEL"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Factures' },
        ]}
      />

      {/* Stats globales */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Total Factures"
            value={summary.total_factures}
            icon={<FileText className="w-5 h-5" />}
          />
          <StatCard
            title="Total HT"
            value={formatCurrency(summary.total_ht)}
            icon={<TrendingUp className="w-5 h-5" />}
          />
          <StatCard
            title="Total TVA"
            value={formatCurrency(summary.total_tva)}
          />
          <StatCard
            title="Total TTC"
            value={formatCurrency(summary.total_ttc)}
          />
        </div>
      )}

      {/* Stats par fournisseur */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Object.entries(summary.par_fournisseur).map(([source, stats]) => {
            const colors = SOURCE_COLORS[source] || { bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/30' }
            return (
              <Card key={source} className={cn('border', colors.border)}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-3">
                    <SourceBadge source={source} />
                    <span className={cn('text-2xl font-bold', colors.text)}>
                      {stats.nb_factures}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-dark-400">HT:</span>
                      <span className="ml-2 text-white">{formatCurrency(stats.total_ht)}</span>
                    </div>
                    <div>
                      <span className="text-dark-400">TTC:</span>
                      <span className="ml-2 text-white">{formatCurrency(stats.total_ttc)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Filtres */}
      <Card padding="sm">
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[250px]">
              <Input
                placeholder="Rechercher par numéro, fournisseur..."
                leftIcon={<Search className="w-4 h-4" />}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
              />
            </div>
            <Select
              options={sourceOptions}
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="w-48"
            />
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <Filter className="w-4 h-4" />
              {filteredFactures.length} factures
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liste des factures */}
      <div className="space-y-2">
        {paginatedFactures.length === 0 ? (
          <EmptyState
            type="empty"
            title="Aucune facture"
            description="Aucune facture ne correspond à vos critères de recherche."
          />
        ) : (
          paginatedFactures.map((facture) => {
            const key = `${facture.source}-${facture.id}`
            const isExpanded = expandedFacture === key

            return (
              <div key={key} className="bg-dark-800 rounded-xl border border-dark-700 overflow-hidden">
                <button
                  onClick={() => handleExpandFacture(facture)}
                  className="w-full flex items-center justify-between p-4 hover:bg-dark-700/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-dark-400" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-dark-400" />
                    )}
                    <SourceBadge source={facture.source} />
                    <div className="text-left">
                      <p className="font-medium text-white">{facture.numero}</p>
                      <p className="text-sm text-dark-400">
                        <Calendar className="w-3 h-3 inline mr-1" />
                        {formatDate(facture.date_facture)} - {facture.fournisseur}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-white">{formatCurrency(facture.total_ttc)}</p>
                    <p className="text-xs text-dark-400">
                      {facture.nb_lignes} article{facture.nb_lignes > 1 ? 's' : ''}
                      {facture.type_document === 'AV' && (
                        <Badge variant="warning" size="sm" className="ml-2">Avoir</Badge>
                      )}
                    </p>
                  </div>
                </button>

                {/* Détail facture */}
                {isExpanded && (
                  <div className="border-t border-dark-700 p-4 bg-dark-800/50">
                    {loadingDetail ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                        <span className="ml-2 text-slate-400">Chargement des lignes...</span>
                      </div>
                    ) : expandedFactureData ? (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="text-dark-400 border-b border-dark-700">
                              {expandedFactureData.source === 'METRO' && (
                                <th className="text-left pb-2 font-medium">EAN</th>
                              )}
                              <th className="text-left pb-2 font-medium">Désignation</th>
                              {expandedFactureData.source === 'METRO' && (
                                <th className="text-center pb-2 font-medium">Cat.</th>
                              )}
                              {expandedFactureData.source === 'TAIYAT' && (
                                <th className="text-center pb-2 font-medium">Origine</th>
                              )}
                              <th className="text-center pb-2 font-medium">Qté</th>
                              <th className="text-right pb-2 font-medium">P.U.</th>
                              <th className="text-right pb-2 font-medium">Montant</th>
                            </tr>
                          </thead>
                          <tbody>
                            {expandedFactureData.lignes.map((ligne, idx) => (
                              <tr key={idx} className="border-b border-dark-700/50">
                                {expandedFactureData.source === 'METRO' && (
                                  <td className="py-2 text-dark-300 font-mono text-xs">{ligne.ean || '-'}</td>
                                )}
                                <td className="py-2 text-white">{ligne.designation}</td>
                                {expandedFactureData.source === 'METRO' && (
                                  <td className="py-2 text-center">
                                    <CategoryBadge regie={ligne.regie || null} vol={ligne.vol_alcool || null} />
                                  </td>
                                )}
                                {expandedFactureData.source === 'TAIYAT' && (
                                  <td className="py-2 text-center text-dark-300 text-xs">{ligne.provenance || '-'}</td>
                                )}
                                <td className="py-2 text-center text-dark-300">
                                  {ligne.quantite || ligne.quantite_unitaire || ligne.colis || '-'}
                                </td>
                                <td className="py-2 text-right text-dark-300">
                                  {formatCurrency(ligne.prix_unitaire || null)}
                                </td>
                                <td className="py-2 text-right font-medium text-white">
                                  {formatCurrency(ligne.montant_ht || ligne.montant_ttc || null)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot>
                            <tr className="font-bold">
                              <td colSpan={expandedFactureData.source === 'METRO' ? 5 : 4} className="pt-3 text-right text-dark-300">Total HT:</td>
                              <td className="pt-3 text-right text-white">{formatCurrency(expandedFactureData.total_ht)}</td>
                            </tr>
                            <tr>
                              <td colSpan={expandedFactureData.source === 'METRO' ? 5 : 4} className="text-right text-dark-400 text-xs">TVA:</td>
                              <td className="text-right text-dark-400 text-xs">{formatCurrency(expandedFactureData.total_tva)}</td>
                            </tr>
                            <tr className="font-bold text-lg">
                              <td colSpan={expandedFactureData.source === 'METRO' ? 5 : 4} className="pt-1 text-right text-dark-300">Total TTC:</td>
                              <td className="pt-1 text-right text-emerald-400">{formatCurrency(expandedFactureData.total_ttc)}</td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    ) : (
                      <div className="text-center py-4 text-slate-400">
                        Impossible de charger le détail
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 text-sm">
          <div className="text-slate-400">
            Page {currentPage} sur {totalPages} ({filteredFactures.length} factures)
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className={cn(
                'p-2 rounded-lg transition-colors',
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
                'p-2 rounded-lg transition-colors',
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
    </div>
  );
}
