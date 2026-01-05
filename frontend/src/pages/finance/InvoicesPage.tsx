import { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  Download,
  Upload,
  FileText,
  Eye,
  MoreVertical,
  Trash2,
  Edit,
  CheckCircle,
  ShoppingCart,
  ChevronDown,
  ChevronRight,
  Calendar,
  Wine,
  Beer,
  Package,
  ChevronLeft,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useInvoices, useInvoiceStats, useDeleteInvoice, useUpdateInvoiceStatus } from '../../hooks/useFinance';
import {
  Button,
  Input,
  Select,
  Table,
  Pagination,
  Badge,
  Card,
  CardContent,
  Dropdown,
  DropdownItem,
  DropdownSeparator,
  EmptyState,
  DeleteConfirm,
  StatCard,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { useFilter, usePagination, useSort, useModal, useToast } from '../../hooks';
import { formatDate } from '../../lib/utils';
import type { Invoice, InvoiceFilters, InvoiceStatus, InvoiceType } from '../../types/finance';

import apiClient from '@/api/client';

// ============================================================================
// TYPES METRO API
// ============================================================================

interface MetroLigneAPI {
  id: number
  facture_id: number
  ean: string
  article_numero: string | null
  designation: string
  colisage: number
  quantite_colis: string
  quantite_unitaire: string
  prix_colis: string
  prix_unitaire: string
  montant_ht: string
  volume_unitaire: string | null
  unite: string
  taux_tva: string
  code_tva: string | null
  montant_tva: string
  regie: string | null
  vol_alcool: string | null
  categorie_id: number | null
  categorie: string
}

interface MetroFactureAPI {
  id: number
  numero: string
  date_facture: string
  magasin: string
  total_ht: string
  total_tva: string
  total_ttc: string
  fichier_source: string | null
  importee_le: string
  nb_lignes: number
  lignes: MetroLigneAPI[]
}

interface MetroFactureListItemAPI {
  id: number
  numero: string
  date_facture: string
  magasin: string
  total_ht: string
  total_tva: string
  total_ttc: string
  nb_lignes: number
  importee_le: string
}

interface MetroFactureListAPI {
  items: MetroFactureListItemAPI[]
  total: number
  page: number
  per_page: number
  pages: number
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

// Internal types
interface MetroLigne {
  ean: string
  article_numero: string | null
  designation: string
  colisage: number
  quantite: number
  prix_unitaire: number
  montant: number
  taux_tva: number
  regie: string | null
  vol_alcool: number | null
}

interface MetroFacture {
  id: number
  numero: string
  date: string
  magasin: string
  total_ht: number
  total_tva: number
  total_ttc: number
  nb_lignes: number
  lignes: MetroLigne[]
}

interface MetroSummary {
  nb_factures: number
  nb_lignes: number
  total_ht: number
  total_tva: number
  total_ttc: number
}

// ============================================================================
// CONSTANTS
// ============================================================================

const statusOptions = [
  { value: '', label: 'Tous les statuts' },
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'validee', label: 'Validée' },
  { value: 'envoyee', label: 'Envoyée' },
  { value: 'partiellement_payee', label: 'Partiellement payée' },
  { value: 'payee', label: 'Payée' },
  { value: 'en_litige', label: 'En litige' },
  { value: 'annulee', label: 'Annulée' },
];

const typeOptions = [
  { value: '', label: 'Tous les types' },
  { value: 'achat', label: 'Achat' },
  { value: 'vente', label: 'Vente' },
  { value: 'avoir_achat', label: 'Avoir achat' },
  { value: 'avoir_vente', label: 'Avoir vente' },
];

// ============================================================================
// HELPERS
// ============================================================================

function formatCurrency(amount: number | null): string {
  if (amount === null) return '—'
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount)
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
// METRO INVOICES COMPONENT
// ============================================================================

function MetroInvoicesTab() {
  const [factures, setFactures] = useState<MetroFacture[]>([])
  const [summary, setSummary] = useState<MetroSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchValue, setSearchValue] = useState('')
  const [expandedFacture, setExpandedFacture] = useState<string | null>(null)
  const [expandedFactureData, setExpandedFactureData] = useState<MetroFacture | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 15

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      setError(null)
      try {
        const [facturesRes, summaryRes] = await Promise.all([
          apiClient.get<MetroFactureListAPI>('/metro/factures', { params: { per_page: 1000 } }),
          apiClient.get<MetroSummaryAPI>('/metro/summary'),
        ])

        // Convert API response to internal format
        const convertedFactures: MetroFacture[] = facturesRes.data.items.map(f => ({
          id: f.id,
          numero: f.numero,
          date: f.date_facture,
          magasin: f.magasin,
          total_ht: parseFloat(f.total_ht) || 0,
          total_tva: parseFloat(f.total_tva) || 0,
          total_ttc: parseFloat(f.total_ttc) || 0,
          nb_lignes: f.nb_lignes,
          lignes: [], // Lines loaded on demand
        }))

        setFactures(convertedFactures)
        setSummary({
          nb_factures: summaryRes.data.nb_factures,
          nb_lignes: summaryRes.data.nb_lignes,
          total_ht: parseFloat(summaryRes.data.total_ht) || 0,
          total_tva: parseFloat(summaryRes.data.total_tva) || 0,
          total_ttc: parseFloat(summaryRes.data.total_ttc) || 0,
        })
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Erreur lors du chargement des données'
        setError(message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  // Load facture detail when expanded
  const handleExpandFacture = async (factureId: number, numero: string) => {
    if (expandedFacture === numero) {
      setExpandedFacture(null)
      setExpandedFactureData(null)
      return
    }

    setExpandedFacture(numero)
    try {
      const res = await apiClient.get<MetroFactureAPI>(`/metro/factures/${factureId}`)
      const f = res.data
      setExpandedFactureData({
        id: f.id,
        numero: f.numero,
        date: f.date_facture,
        magasin: f.magasin,
        total_ht: parseFloat(f.total_ht) || 0,
        total_tva: parseFloat(f.total_tva) || 0,
        total_ttc: parseFloat(f.total_ttc) || 0,
        nb_lignes: f.nb_lignes,
        lignes: f.lignes.map(l => ({
          ean: l.ean,
          article_numero: l.article_numero,
          designation: l.designation,
          colisage: l.colisage,
          quantite: parseFloat(l.quantite_unitaire) || 0,
          prix_unitaire: parseFloat(l.prix_unitaire) || 0,
          montant: parseFloat(l.montant_ht) || 0,
          taux_tva: parseFloat(l.taux_tva) || 20,
          regie: l.regie,
          vol_alcool: l.vol_alcool ? parseFloat(l.vol_alcool) : null,
        })),
      })
    } catch {
      // Keep expanded but show empty
      setExpandedFactureData(null)
    }
  }

  const filteredFactures = useMemo(() => {
    if (!searchValue) return factures

    const search = searchValue.toLowerCase()
    return factures.filter(f =>
      f.numero.toLowerCase().includes(search) ||
      f.magasin.toLowerCase().includes(search)
    )
  }, [factures, searchValue])

  const totalPages = Math.ceil(filteredFactures.length / pageSize)
  const paginatedFactures = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredFactures.slice(start, start + pageSize)
  }, [filteredFactures, currentPage])

  useEffect(() => {
    setCurrentPage(1)
  }, [searchValue])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        <span className="ml-2 text-slate-300">Chargement des factures METRO...</span>
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
      {/* Stats METRO */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            title="Factures METRO"
            value={summary.nb_factures}
            icon={<ShoppingCart className="w-5 h-5" />}
          />
          <StatCard
            title="Total HT"
            value={formatCurrency(summary.total_ht)}
          />
          <StatCard
            title="Total TVA"
            value={formatCurrency(summary.total_tva)}
          />
          <StatCard
            title="Total TTC"
            value={formatCurrency(summary.total_ttc)}
          />
          <StatCard
            title="Lignes articles"
            value={summary.nb_lignes}
          />
        </div>
      )}

      {/* Search */}
      <Card padding="sm">
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <Input
                placeholder="Rechercher par numéro, magasin, article..."
                leftIcon={<Search className="w-4 h-4" />}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
              />
            </div>
            <span className="text-sm text-slate-400">
              {filteredFactures.length} factures
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Factures List */}
      <div className="space-y-2">
        {paginatedFactures.map((facture) => (
          <div key={facture.numero} className="bg-dark-800 rounded-xl border border-dark-700 overflow-hidden">
            <button
              onClick={() => handleExpandFacture(facture.id, facture.numero)}
              className="w-full flex items-center justify-between p-4 hover:bg-dark-700/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                {expandedFacture === facture.numero ? (
                  <ChevronDown className="w-5 h-5 text-dark-400" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-dark-400" />
                )}
                <div className="text-left">
                  <p className="font-medium text-white">{facture.numero}</p>
                  <p className="text-sm text-dark-400">
                    <Calendar className="w-3 h-3 inline mr-1" />
                    {formatDate(facture.date)} - {facture.magasin}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-bold text-white">{formatCurrency(facture.total_ht)}</p>
                <p className="text-xs text-dark-400">{facture.nb_lignes} articles</p>
              </div>
            </button>

            {expandedFacture === facture.numero && (
              <div className="border-t border-dark-700 p-4 bg-dark-800/50">
                {expandedFactureData ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-dark-400 border-b border-dark-700">
                          <th className="text-left pb-2 font-medium">EAN</th>
                          <th className="text-left pb-2 font-medium">Désignation</th>
                          <th className="text-center pb-2 font-medium">Cat.</th>
                          <th className="text-center pb-2 font-medium">Colis</th>
                          <th className="text-center pb-2 font-medium">Qté</th>
                          <th className="text-right pb-2 font-medium">P.U.</th>
                          <th className="text-right pb-2 font-medium">Montant</th>
                        </tr>
                      </thead>
                      <tbody>
                        {expandedFactureData.lignes.map((ligne, idx) => (
                          <tr key={idx} className="border-b border-dark-700/50">
                            <td className="py-2 text-dark-300 font-mono text-xs">{ligne.ean}</td>
                            <td className="py-2 text-white">{ligne.designation}</td>
                            <td className="py-2 text-center">
                              <CategoryBadge regie={ligne.regie} vol={ligne.vol_alcool} />
                            </td>
                            <td className="py-2 text-center">
                              {ligne.colisage > 1 && (
                                <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 text-xs">
                                  x{ligne.colisage}
                                </span>
                              )}
                            </td>
                            <td className="py-2 text-center text-dark-300">{ligne.quantite}</td>
                            <td className="py-2 text-right text-dark-300">{formatCurrency(ligne.prix_unitaire)}</td>
                            <td className="py-2 text-right font-medium text-white">{formatCurrency(ligne.montant)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="font-bold">
                          <td colSpan={6} className="pt-3 text-right text-dark-300">Total HT:</td>
                          <td className="pt-3 text-right text-white">{formatCurrency(expandedFactureData.total_ht)}</td>
                        </tr>
                        <tr>
                          <td colSpan={6} className="text-right text-dark-400 text-xs">TVA:</td>
                          <td className="text-right text-dark-400 text-xs">{formatCurrency(expandedFactureData.total_tva)}</td>
                        </tr>
                        <tr className="font-bold text-lg">
                          <td colSpan={6} className="pt-1 text-right text-dark-300">Total TTC:</td>
                          <td className="pt-1 text-right text-emerald-400">{formatCurrency(expandedFactureData.total_ttc)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
                    <span className="ml-2 text-slate-400">Chargement des lignes...</span>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2 text-sm">
          <div className="text-slate-400">
            Page {currentPage} sur {totalPages}
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
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function InvoicesPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<'standard' | 'metro'>('standard');

  // State
  const [search, setSearch] = useState('');
  const filters = useFilter<InvoiceFilters>({
    initialFilters: {},
  });
  const pagination = usePagination({ initialPerPage: 20 });
  const sort = useSort<string>({ defaultDirection: 'desc' });
  const deleteModal = useModal<Invoice>();

  // Queries
  const { data, isLoading, error } = useInvoices(
    { ...filters.filters, search },
    pagination.page,
    pagination.perPage
  );
  const { data: stats } = useInvoiceStats(filters.filters);

  // Mutations
  const deleteMutation = useDeleteInvoice();
  const updateStatusMutation = useUpdateInvoiceStatus();

  // Handlers
  const handleDelete = async () => {
    if (!deleteModal.data) return;
    try {
      await deleteMutation.mutateAsync(deleteModal.data.facture_id);
      toast.success('Facture supprimée');
      deleteModal.close();
    } catch {
      toast.error('Erreur lors de la suppression');
    }
  };

  const handleStatusChange = async (invoice: Invoice, newStatus: InvoiceStatus) => {
    try {
      await updateStatusMutation.mutateAsync({ id: invoice.facture_id, statut: newStatus });
      toast.success('Statut mis à jour');
    } catch {
      toast.error('Erreur lors de la mise à jour');
    }
  };

  // Update pagination total
  if (data?.total && data.total !== pagination.total) {
    pagination.setTotal(data.total);
  }

  const columns = [
    {
      key: 'numero',
      header: 'N° Facture',
      sortable: true,
      render: (invoice: Invoice) => (
        <Link
          to={`/finance/factures/${invoice.facture_id}`}
          className="font-medium text-primary-500 hover:text-primary-400"
        >
          {invoice.numero}
        </Link>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (invoice: Invoice) => (
        <Badge variant={invoice.type === 'vente' ? 'success' : 'info'}>
          {invoice.type_libelle}
        </Badge>
      ),
    },
    {
      key: 'fournisseur',
      header: 'Tiers',
      render: (invoice: Invoice) => (
        <span className="text-dark-200">
          {invoice.fournisseur_nom || invoice.client_nom || '-'}
        </span>
      ),
    },
    {
      key: 'date_facture',
      header: 'Date',
      sortable: true,
      render: (invoice: Invoice) => formatDate(invoice.date_facture),
    },
    {
      key: 'date_echeance',
      header: 'Échéance',
      sortable: true,
      render: (invoice: Invoice) => {
        const isOverdue = new Date(invoice.date_echeance) < new Date() && invoice.solde_du > 0;
        return (
          <span className={isOverdue ? 'text-red-400' : ''}>
            {formatDate(invoice.date_echeance)}
          </span>
        );
      },
    },
    {
      key: 'montant_ttc',
      header: 'Montant TTC',
      sortable: true,
      align: 'right' as const,
      render: (invoice: Invoice) => (
        <span className="font-medium">{formatCurrency(invoice.montant_ttc)}</span>
      ),
    },
    {
      key: 'solde_du',
      header: 'Solde dû',
      sortable: true,
      align: 'right' as const,
      render: (invoice: Invoice) => (
        <span className={invoice.solde_du > 0 ? 'text-red-400' : 'text-green-400'}>
          {formatCurrency(invoice.solde_du)}
        </span>
      ),
    },
    {
      key: 'statut',
      header: 'Statut',
      render: (invoice: Invoice) => (
        <Badge
          variant={
            invoice.statut === 'payee' ? 'success' :
            invoice.statut === 'en_litige' ? 'danger' :
            invoice.statut === 'annulee' ? 'default' :
            'warning'
          }
          dot
        >
          {invoice.statut_libelle}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      width: '50px',
      render: (invoice: Invoice) => (
        <Dropdown
          trigger={
            <button className="p-1 hover:bg-dark-700 rounded">
              <MoreVertical className="w-4 h-4 text-dark-400" />
            </button>
          }
          position="bottom-right"
        >
          <DropdownItem
            icon={<Eye className="w-4 h-4" />}
            onClick={() => navigate(`/finance/factures/${invoice.facture_id}`)}
          >
            Voir le détail
          </DropdownItem>
          <DropdownItem
            icon={<Edit className="w-4 h-4" />}
            onClick={() => navigate(`/finance/factures/${invoice.facture_id}/edit`)}
            disabled={invoice.statut === 'payee' || invoice.statut === 'annulee'}
          >
            Modifier
          </DropdownItem>
          {invoice.statut === 'brouillon' && (
            <DropdownItem
              icon={<CheckCircle className="w-4 h-4" />}
              onClick={() => handleStatusChange(invoice, 'validee')}
            >
              Valider
            </DropdownItem>
          )}
          <DropdownSeparator />
          <DropdownItem
            icon={<Trash2 className="w-4 h-4" />}
            danger
            onClick={() => deleteModal.open(invoice)}
            disabled={invoice.statut === 'payee'}
          >
            Supprimer
          </DropdownItem>
        </Dropdown>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Factures"
        subtitle="Gérez vos factures fournisseurs et clients"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Factures' },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" leftIcon={<Upload className="w-4 h-4" />}>
              Importer
            </Button>
            <Button variant="outline" leftIcon={<Download className="w-4 h-4" />}>
              Exporter
            </Button>
            <Button leftIcon={<Plus className="w-4 h-4" />} onClick={() => navigate('/finance/factures/new')}>
              Nouvelle facture
            </Button>
          </div>
        }
      />

      {/* Tabs */}
      <div className="flex gap-2 border-b border-dark-700">
        <button
          onClick={() => setActiveTab('standard')}
          className={cn(
            'px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
            activeTab === 'standard'
              ? 'text-primary-400 border-primary-500'
              : 'text-dark-400 border-transparent hover:text-white'
          )}
        >
          <FileText className="w-4 h-4 inline mr-2" />
          Factures
        </button>
        <button
          onClick={() => setActiveTab('metro')}
          className={cn(
            'px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
            activeTab === 'metro'
              ? 'text-primary-400 border-primary-500'
              : 'text-dark-400 border-transparent hover:text-white'
          )}
        >
          <ShoppingCart className="w-4 h-4 inline mr-2" />
          METRO
        </button>
      </div>

      {/* Standard Invoices Tab */}
      {activeTab === 'standard' && (
        <>
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                title="Total factures"
                value={stats.total_factures}
                icon={<FileText className="w-5 h-5" />}
              />
              <StatCard
                title="Montant total TTC"
                value={formatCurrency(stats.total_ttc)}
              />
              <StatCard
                title="Montant payé"
                value={formatCurrency(stats.total_paye)}
                trend="up"
              />
              <StatCard
                title="Solde dû"
                value={formatCurrency(stats.total_du)}
                trend={stats.total_du > 0 ? 'down' : 'neutral'}
              />
            </div>
          )}

          {/* Filtres */}
          <Card padding="sm">
            <CardContent>
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[200px]">
                  <Input
                    placeholder="Rechercher par numéro, fournisseur..."
                    leftIcon={<Search className="w-4 h-4" />}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <Select
                  options={typeOptions}
                  value={filters.filters.type || ''}
                  onChange={(e) => filters.setFilter('type', e.target.value as InvoiceType || undefined)}
                  className="w-40"
                />
                <Select
                  options={statusOptions}
                  value={filters.filters.statut || ''}
                  onChange={(e) => filters.setFilter('statut', e.target.value as InvoiceStatus || undefined)}
                  className="w-48"
                />
                {filters.hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={filters.clearFilters}>
                    Réinitialiser
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Table */}
          {error ? (
            <EmptyState
              type="error"
              title="Erreur de chargement"
              description="Impossible de charger les factures. Veuillez réessayer."
              action={{ label: 'Réessayer', onClick: () => window.location.reload() }}
            />
          ) : (
            <>
              <Table
                data={data?.items || []}
                columns={columns}
                keyExtractor={(invoice) => invoice.facture_id}
                loading={isLoading}
                sortKey={sort.sortKey || undefined}
                sortDirection={sort.sortDirection}
                onSort={sort.setSort}
                onRowClick={(invoice) => navigate(`/finance/factures/${invoice.facture_id}`)}
                emptyMessage="Aucune facture trouvée"
              />

              {data && data.pages > 1 && (
                <Pagination
                  page={pagination.page}
                  totalPages={data.pages}
                  total={data.total}
                  perPage={pagination.perPage}
                  onPageChange={pagination.setPage}
                />
              )}
            </>
          )}
        </>
      )}

      {/* METRO Invoices Tab */}
      {activeTab === 'metro' && <MetroInvoicesTab />}

      {/* Delete confirmation */}
      <DeleteConfirm
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.close}
        onConfirm={handleDelete}
        itemName={deleteModal.data?.numero}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
