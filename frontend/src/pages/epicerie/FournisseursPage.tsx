import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Truck,
  Plus,
  Clock,
  CheckCircle,
  AlertTriangle,
  Package,
  Calendar,
  Phone,
  Mail,
  MapPin,
  Edit2,
  Trash2,
  Search,
  Filter,
  RefreshCw,
  XCircle,
  Send,
  Users,
  Euro,
  Receipt,
  ChevronRight,
  Fish,
  Store,
} from 'lucide-react';
import apiClient from '@/api/client';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Select,
  Badge,
  Modal,
  ModalFooter,
  EmptyState,
} from '@/components/ui';
import { PageHeader } from '@/components/ui/Breadcrumb';
import { formatCurrency } from '@/lib/utils';
import { supplyOrdersApi } from '@/api/epicerie';
import { vendorsApi } from '@/api/finance';
import type { SupplyOrder, SupplyOrderStatus, SupplyOrderDetail } from '@/types/epicerie';
import type { Vendor, VendorCreate } from '@/types/finance';
import { cn } from '@/lib/utils';

// Types METRO
interface MetroClientStats {
  nom: string;
  nb_factures: number;
  total_ht: number;
  pct_ca: number;
}

interface MetroSummary {
  nb_factures: number;
  nb_produits: number;
  nb_lignes: number;
  total_ht: string;
  total_tva: string;
  total_ttc: string;
}

interface MetroStats {
  nom: string;
  code: string;
  nb_factures: number;
  nb_produits: number;
  nb_lignes: number;
  total_ht: number;
  total_ttc: number;
  clients: MetroClientStats[];
}

interface MetroFacture {
  id: number;
  numero: string;
  date_facture: string;
  magasin: string;
  client_nom?: string;
  total_ht: string;
  total_ttc: string;
  nb_lignes: number;
}

// Types TAIYAT
interface TaiyatClientStats {
  client_nom: string;
  count: number;
  total_ttc: number;
}

interface TaiyatSummary {
  fournisseur: string;
  siret: string;
  nb_factures: number;
  nb_lignes: number;
  nb_produits: number;
  total_ttc: number;
  premiere_facture: string | null;
  derniere_facture: string | null;
}

interface TaiyatStats {
  nom: string;
  code: string;
  nb_factures: number;
  nb_produits: number;
  nb_lignes: number;
  total_ttc: number;
  clients: TaiyatClientStats[];
}

interface TaiyatFacture {
  id: number;
  numero: string;
  date_facture: string;
  client_nom: string;
  total_ttc: number;
  nb_lignes: number;
  fichier_source?: string;
}

// Types EUROCIEL
interface EurocielSummary {
  fournisseur: string;
  siret: string;
  nb_factures: number;
  nb_lignes: number;
  nb_produits: number;
  total_ht: number;
  total_ttc: number;
  poids_total_kg: number;
  premiere_facture: string | null;
  derniere_facture: string | null;
}

interface EurocielStats {
  nom: string;
  code: string;
  nb_factures: number;
  nb_produits: number;
  nb_lignes: number;
  total_ht: number;
  poids_total_kg: number;
}

// Types OTHER
interface OtherSummary {
  nb_produits: number;
  nb_produits_actifs: number;
  nb_fournisseurs: number;
  total_valeur_catalogue: number;
}

interface OtherStats {
  nom: string;
  code: string;
  nb_produits: number;
  nb_fournisseurs: number;
  total_valeur: number;
}

const formatNumber = (num: number) => {
  return new Intl.NumberFormat('fr-FR').format(num);
};

const STATUT_CONFIG: Record<SupplyOrderStatus, { label: string; variant: 'warning' | 'info' | 'success' | 'default' | 'danger'; icon: React.FC<{ className?: string }> }> = {
  en_attente: { label: 'En attente', variant: 'warning', icon: Clock },
  confirmee: { label: 'Confirmee', variant: 'info', icon: CheckCircle },
  expediee: { label: 'Expediee', variant: 'info', icon: Truck },
  livree: { label: 'Livree', variant: 'success', icon: CheckCircle },
  annulee: { label: 'Annulee', variant: 'default', icon: AlertTriangle },
};

export default function FournisseursPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'commandes' | 'fournisseurs'>('commandes');
  const [searchQuery, setSearchQuery] = useState('');
  const [statutFilter, setStatutFilter] = useState<string>('');
  const [isCommandeModalOpen, setIsCommandeModalOpen] = useState(false);
  const [isFournisseurModalOpen, setIsFournisseurModalOpen] = useState(false);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<SupplyOrderDetail | null>(null);

  // State pour les commandes depuis l'API
  const [commandes, setCommandes] = useState<SupplyOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    totalItems: 0,
    totalPages: 0,
  });

  // State pour le formulaire de nouvelle commande
  const [newOrder, setNewOrder] = useState({
    vendor_id: '',
    date_commande: new Date().toISOString().split('T')[0],
    date_livraison_prevue: '',
    notes: '',
  });
  const [creating, setCreating] = useState(false);

  // State pour les fournisseurs depuis l'API Finance
  const [fournisseurs, setFournisseurs] = useState<Vendor[]>([]);
  const [loadingVendors, setLoadingVendors] = useState(true);
  const [vendorError, setVendorError] = useState<string | null>(null);

  // State pour METRO (fournisseur DWH)
  const [metroStats, setMetroStats] = useState<MetroStats | null>(null);
  const [metroFactures, setMetroFactures] = useState<MetroFacture[]>([]);
  const [loadingMetro, setLoadingMetro] = useState(true);
  const [showAllFactures, setShowAllFactures] = useState(false);

  // State pour TAIYAT (fournisseur DWH)
  const [taiyatStats, setTaiyatStats] = useState<TaiyatStats | null>(null);
  const [taiyatFactures, setTaiyatFactures] = useState<TaiyatFacture[]>([]);
  const [loadingTaiyat, setLoadingTaiyat] = useState(true);
  const [showAllTaiyatFactures, setShowAllTaiyatFactures] = useState(false);

  // State pour EUROCIEL (fournisseur DWH)
  const [eurocielStats, setEurocielStats] = useState<EurocielStats | null>(null);
  const [loadingEurociel, setLoadingEurociel] = useState(true);

  // State pour OTHER (fournisseurs divers)
  const [otherStats, setOtherStats] = useState<OtherStats | null>(null);
  const [loadingOther, setLoadingOther] = useState(true);

  // State pour le formulaire de nouveau fournisseur
  const [newVendor, setNewVendor] = useState<Partial<VendorCreate>>({
    name: '',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    address: '',
    payment_terms_days: 30,
    entity_id: 1, // TODO: Obtenir l'entity_id du contexte utilisateur
  });
  const [creatingVendor, setCreatingVendor] = useState(false);

  // Charger les commandes
  const loadCommandes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await supplyOrdersApi.getAll(
        pagination.page,
        pagination.pageSize,
        undefined,
        statutFilter as SupplyOrderStatus | undefined
      );
      setCommandes(response.data);
      setPagination({
        page: response.pagination.page,
        pageSize: response.pagination.page_size,
        totalItems: response.pagination.total_items,
        totalPages: response.pagination.total_pages,
      });
    } catch (err) {
      console.error('Erreur chargement commandes:', err);
      setError('Erreur lors du chargement des commandes');
    } finally {
      setLoading(false);
    }
  }, [pagination.page, pagination.pageSize, statutFilter]);

  // Charger les fournisseurs
  const loadVendors = useCallback(async () => {
    setLoadingVendors(true);
    setVendorError(null);
    try {
      // TODO: entity_id devrait venir du contexte utilisateur
      const data = await vendorsApi.getAll(1, false);
      setFournisseurs(data);
    } catch (err) {
      console.error('Erreur chargement fournisseurs:', err);
      setVendorError('Erreur lors du chargement des fournisseurs');
    } finally {
      setLoadingVendors(false);
    }
  }, []);

  // Charger les stats METRO
  const loadMetroData = useCallback(async () => {
    setLoadingMetro(true);
    try {
      const [summaryRes, clientsRes, facturesRes] = await Promise.all([
        apiClient.get<MetroSummary>('/metro/summary'),
        apiClient.get<{ clients: { client_nom: string; count: number; total_ht: number }[] }>('/metro/clients'),
        apiClient.get<{ items: MetroFacture[] }>('/metro/factures?per_page=20&sort_by=date_facture&sort_order=desc'),
      ]);

      const summary = summaryRes.data;
      const totalHT = parseFloat(summary.total_ht) || 0;

      // Construire les stats clients
      const clients: MetroClientStats[] = (clientsRes.data?.clients || []).map(c => ({
        nom: c.client_nom || 'Non identifie',
        nb_factures: c.count,
        total_ht: c.total_ht || 0,
        pct_ca: totalHT > 0 ? (c.total_ht / totalHT) * 100 : 0,
      }));

      setMetroStats({
        nom: 'METRO Cash & Carry',
        code: 'METRO',
        nb_factures: summary.nb_factures,
        nb_produits: summary.nb_produits,
        nb_lignes: summary.nb_lignes,
        total_ht: totalHT,
        total_ttc: parseFloat(summary.total_ttc) || 0,
        clients,
      });

      setMetroFactures(facturesRes.data?.items || []);
    } catch (err) {
      console.error('Erreur chargement METRO:', err);
      setMetroStats(null);
      setMetroFactures([]);
    } finally {
      setLoadingMetro(false);
    }
  }, []);

  // Charger les stats TAIYAT
  const loadTaiyatData = useCallback(async () => {
    setLoadingTaiyat(true);
    try {
      const [summaryRes, clientsRes, facturesRes] = await Promise.all([
        apiClient.get<TaiyatSummary>('/taiyat/summary'),
        apiClient.get<{ clients: TaiyatClientStats[] }>('/taiyat/clients'),
        apiClient.get<{ items: TaiyatFacture[] }>('/taiyat/factures?per_page=20'),
      ]);

      const summary = summaryRes.data;

      setTaiyatStats({
        nom: 'TAI YAT Distribution',
        code: 'TAIYAT',
        nb_factures: summary.nb_factures,
        nb_produits: summary.nb_produits,
        nb_lignes: summary.nb_lignes,
        total_ttc: summary.total_ttc || 0,
        clients: clientsRes.data?.clients || [],
      });

      setTaiyatFactures(facturesRes.data?.items || []);
    } catch (err) {
      console.error('Erreur chargement TAIYAT:', err);
      setTaiyatStats(null);
      setTaiyatFactures([]);
    } finally {
      setLoadingTaiyat(false);
    }
  }, []);

  // Charger les stats EUROCIEL
  const loadEurocielData = useCallback(async () => {
    setLoadingEurociel(true);
    try {
      const summaryRes = await apiClient.get<EurocielSummary>('/eurociel/summary');
      const summary = summaryRes.data;

      setEurocielStats({
        nom: 'EUROCIEL',
        code: 'EUROCIEL',
        nb_factures: summary.nb_factures,
        nb_produits: summary.nb_produits,
        nb_lignes: summary.nb_lignes,
        total_ht: summary.total_ht || 0,
        poids_total_kg: summary.poids_total_kg || 0,
      });
    } catch (err) {
      console.error('Erreur chargement EUROCIEL:', err);
      setEurocielStats(null);
    } finally {
      setLoadingEurociel(false);
    }
  }, []);

  // Charger les stats OTHER
  const loadOtherData = useCallback(async () => {
    setLoadingOther(true);
    try {
      const summaryRes = await apiClient.get<OtherSummary>('/other/summary');
      const summary = summaryRes.data;

      setOtherStats({
        nom: 'Fournisseurs Divers',
        code: 'OTHER',
        nb_produits: summary.nb_produits,
        nb_fournisseurs: summary.nb_fournisseurs,
        total_valeur: summary.total_valeur_catalogue / 100,
      });
    } catch (err) {
      console.error('Erreur chargement OTHER:', err);
      setOtherStats(null);
    } finally {
      setLoadingOther(false);
    }
  }, []);

  useEffect(() => {
    loadCommandes();
    loadVendors();
    loadMetroData();
    loadTaiyatData();
    loadEurocielData();
    loadOtherData();
  }, [loadCommandes, loadVendors, loadMetroData, loadTaiyatData, loadEurocielData, loadOtherData]);

  // Filtrer les commandes par recherche
  const filteredCommandes = commandes.filter((cmd) => {
    if (searchQuery) {
      const search = searchQuery.toLowerCase();
      return (
        (cmd.vendor?.name?.toLowerCase().includes(search) || false) ||
        cmd.id.toString().includes(search) ||
        (cmd.reference?.toLowerCase().includes(search) || false)
      );
    }
    return true;
  });

  const commandesEnAttente = commandes.filter((c) => c.statut === 'en_attente').length;
  const commandesExpediees = commandes.filter((c) => c.statut === 'expediee').length;

  // Voir le detail d'une commande
  const handleViewOrder = async (orderId: number) => {
    try {
      const response = await supplyOrdersApi.getById(orderId);
      setSelectedOrder(response.data);
      setIsDetailModalOpen(true);
    } catch (err) {
      console.error('Erreur chargement detail:', err);
    }
  };

  // Creer une nouvelle commande
  const handleCreateOrder = async () => {
    if (!newOrder.vendor_id) return;
    setCreating(true);
    try {
      await supplyOrdersApi.create({
        vendor_id: parseInt(newOrder.vendor_id),
        date_commande: newOrder.date_commande,
        date_livraison_prevue: newOrder.date_livraison_prevue || undefined,
        notes: newOrder.notes || undefined,
        lines: [],
      });
      setIsCommandeModalOpen(false);
      setNewOrder({
        vendor_id: '',
        date_commande: new Date().toISOString().split('T')[0],
        date_livraison_prevue: '',
        notes: '',
      });
      loadCommandes();
    } catch (err) {
      console.error('Erreur creation commande:', err);
    } finally {
      setCreating(false);
    }
  };

  // Actions sur commande
  const handleConfirmOrder = async (orderId: number) => {
    try {
      await supplyOrdersApi.confirm(orderId);
      loadCommandes();
      if (selectedOrder?.id === orderId) {
        const response = await supplyOrdersApi.getById(orderId);
        setSelectedOrder(response.data);
      }
    } catch (err) {
      console.error('Erreur confirmation:', err);
    }
  };

  const handleShipOrder = async (orderId: number) => {
    try {
      await supplyOrdersApi.ship(orderId);
      loadCommandes();
      if (selectedOrder?.id === orderId) {
        const response = await supplyOrdersApi.getById(orderId);
        setSelectedOrder(response.data);
      }
    } catch (err) {
      console.error('Erreur expedition:', err);
    }
  };

  const handleReceiveOrder = async (orderId: number) => {
    try {
      await supplyOrdersApi.receive(orderId, {
        date_livraison_reelle: new Date().toISOString().split('T')[0],
      });
      loadCommandes();
      if (selectedOrder?.id === orderId) {
        const response = await supplyOrdersApi.getById(orderId);
        setSelectedOrder(response.data);
      }
    } catch (err) {
      console.error('Erreur reception:', err);
    }
  };

  const handleCancelOrder = async (orderId: number) => {
    if (!confirm('Voulez-vous vraiment annuler cette commande ?')) return;
    try {
      await supplyOrdersApi.cancel(orderId);
      loadCommandes();
      if (selectedOrder?.id === orderId) {
        setIsDetailModalOpen(false);
        setSelectedOrder(null);
      }
    } catch (err) {
      console.error('Erreur annulation:', err);
    }
  };

  const handleDeleteOrder = async (orderId: number) => {
    if (!confirm('Voulez-vous vraiment supprimer cette commande ?')) return;
    try {
      await supplyOrdersApi.delete(orderId);
      loadCommandes();
      if (selectedOrder?.id === orderId) {
        setIsDetailModalOpen(false);
        setSelectedOrder(null);
      }
    } catch (err) {
      console.error('Erreur suppression:', err);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fournisseurs"
        subtitle="Gestion des commandes et fournisseurs"
        breadcrumbs={[
          { label: 'Epicerie', href: '/epicerie' },
          { label: 'Fournisseurs' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="ghost" onClick={loadCommandes} disabled={loading}>
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Actualiser
            </Button>
            <Button variant="secondary" onClick={() => setIsFournisseurModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouveau fournisseur
            </Button>
            <Button onClick={() => setIsCommandeModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouvelle commande
            </Button>
          </div>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Commandes en attente</p>
                <p className="text-2xl font-bold text-orange-400">{commandesEnAttente}</p>
              </div>
              <Clock className="w-8 h-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">En cours de livraison</p>
                <p className="text-2xl font-bold text-blue-400">{commandesExpediees}</p>
              </div>
              <Truck className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Fournisseurs actifs</p>
                <p className="text-2xl font-bold text-green-400">
                  {fournisseurs.filter((f) => f.is_active).length}
                </p>
              </div>
              <Package className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Total en cours</p>
                <p className="text-2xl font-bold text-white">
                  {formatCurrency(
                    commandes
                      .filter((c) => ['en_attente', 'confirmee', 'expediee'].includes(c.statut))
                      .reduce((sum, c) => sum + c.montant_ht / 100, 0)
                  )}
                </p>
              </div>
              <Truck className="w-8 h-8 text-primary-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-dark-700">
        <button
          onClick={() => setActiveTab('commandes')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'commandes'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-dark-400 hover:text-white'
          }`}
        >
          <Truck className="w-4 h-4 inline mr-2" />
          Commandes ({pagination.totalItems + (metroStats?.nb_factures || 0) + (taiyatStats?.nb_factures || 0) + (eurocielStats?.nb_factures || 0)})
        </button>
        <button
          onClick={() => setActiveTab('fournisseurs')}
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === 'fournisseurs'
              ? 'text-primary-400 border-b-2 border-primary-400'
              : 'text-dark-400 hover:text-white'
          }`}
        >
          <Package className="w-4 h-4 inline mr-2" />
          Fournisseurs ({fournisseurs.length + (metroStats ? 1 : 0) + (taiyatStats ? 1 : 0) + (eurocielStats ? 1 : 0) + (otherStats ? 1 : 0)})
        </button>
      </div>

      {activeTab === 'commandes' && (
        <>
          {/* Filters */}
          <Card>
            <CardContent className="py-4">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Filter className="w-5 h-5 text-dark-400" />
                  <Select
                    options={[
                      { value: '', label: 'Tous les statuts' },
                      { value: 'en_attente', label: 'En attente' },
                      { value: 'confirmee', label: 'Confirmee' },
                      { value: 'expediee', label: 'Expediee' },
                      { value: 'livree', label: 'Livree' },
                      { value: 'annulee', label: 'Annulee' },
                    ]}
                    value={statutFilter}
                    onChange={(e) => {
                      setStatutFilter(e.target.value);
                      setPagination((p) => ({ ...p, page: 1 }));
                    }}
                  />
                </div>
                <div className="flex-1 min-w-64">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                    <Input
                      placeholder="Rechercher..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Error */}
          {error && (
            <Card className="border-red-500/50 bg-red-500/10">
              <CardContent className="py-4">
                <p className="text-red-400">{error}</p>
              </CardContent>
            </Card>
          )}

          {/* Commandes List */}
          <Card>
            <CardHeader>
              <CardTitle subtitle={`${filteredCommandes.length} commande(s)`}>
                <Truck className="w-5 h-5 inline mr-2" />
                Commandes fournisseurs
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-8 text-center text-dark-400">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
                  Chargement...
                </div>
              ) : filteredCommandes.length === 0 ? (
                <EmptyState
                  icon={<Truck className="w-12 h-12" />}
                  title="Aucune commande"
                  description="Creez votre premiere commande fournisseur."
                  action={{
                    label: 'Nouvelle commande',
                    onClick: () => setIsCommandeModalOpen(true),
                  }}
                />
              ) : (
                <div className="divide-y divide-dark-700">
                  {filteredCommandes.map((commande) => {
                    const statutConfig = STATUT_CONFIG[commande.statut];
                    const StatutIcon = statutConfig.icon;
                    return (
                      <div
                        key={commande.id}
                        className="p-4 hover:bg-dark-700/30 transition-colors cursor-pointer"
                        onClick={() => handleViewOrder(commande.id)}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <span className="font-mono text-sm text-dark-400">
                                #{commande.id.toString().padStart(4, '0')}
                              </span>
                              <span className="font-medium text-white">
                                {commande.vendor?.name || 'Fournisseur inconnu'}
                              </span>
                              <Badge variant={statutConfig.variant} size="sm">
                                <StatutIcon className="w-3 h-3 mr-1" />
                                {statutConfig.label}
                              </Badge>
                              {commande.is_late && (
                                <Badge variant="danger" size="sm">
                                  <AlertTriangle className="w-3 h-3 mr-1" />
                                  En retard
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-4 text-sm text-dark-400">
                              <span>
                                <Calendar className="w-3 h-3 inline mr-1" />
                                Commande: {commande.date_commande}
                              </span>
                              {commande.date_livraison_prevue && (
                                <span>
                                  <Truck className="w-3 h-3 inline mr-1" />
                                  Livraison: {commande.date_livraison_prevue}
                                </span>
                              )}
                              <span>
                                <Package className="w-3 h-3 inline mr-1" />
                                {commande.nb_produits} produits
                              </span>
                            </div>
                            {commande.notes && (
                              <p className="text-sm text-dark-400 mt-1 italic">
                                {commande.notes}
                              </p>
                            )}
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-bold text-white">
                              {formatCurrency(commande.montant_ht / 100)}
                            </p>
                            <p className="text-xs text-dark-400">HT</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Factures METRO */}
          <Card>
            <CardHeader>
              <CardTitle subtitle={`${metroFactures.length} facture(s) recentes sur ${metroStats?.nb_factures || 0}`}>
                <Truck className="w-5 h-5 inline mr-2 text-blue-400" />
                Factures METRO
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loadingMetro ? (
                <div className="p-8 text-center text-dark-400">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
                  Chargement...
                </div>
              ) : metroFactures.length === 0 ? (
                <div className="p-8 text-center text-dark-400">
                  Aucune facture METRO
                </div>
              ) : (
                <div className="divide-y divide-dark-700">
                  {(showAllFactures ? metroFactures : metroFactures.slice(0, 10)).map((facture) => (
                    <div
                      key={facture.id}
                      className="p-4 hover:bg-dark-700/30 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-mono text-sm text-dark-400">
                              {facture.numero.length > 20 ? facture.numero.slice(-15) : facture.numero}
                            </span>
                            <span className="font-medium text-white">
                              METRO
                            </span>
                            <Badge variant="success" size="sm">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Facturee
                            </Badge>
                            {facture.client_nom && (
                              <Badge
                                variant={
                                  facture.client_nom === 'NOUTAM' ? 'info' :
                                  facture.client_nom === 'INCONTOURNABLE' ? 'warning' :
                                  'default'
                                }
                                size="sm"
                              >
                                {facture.client_nom}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-sm text-dark-400">
                            <span>
                              <Calendar className="w-3 h-3 inline mr-1" />
                              {new Date(facture.date_facture).toLocaleDateString('fr-FR')}
                            </span>
                            <span>
                              <MapPin className="w-3 h-3 inline mr-1" />
                              {facture.magasin?.replace('METRO ', '') || '-'}
                            </span>
                            <span>
                              <Package className="w-3 h-3 inline mr-1" />
                              {facture.nb_lignes} produits
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold text-white">
                            {formatCurrency(parseFloat(facture.total_ht))}
                          </p>
                          <p className="text-xs text-dark-400">HT</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  {metroFactures.length > 10 && (
                    <div className="p-4 text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowAllFactures(!showAllFactures)}
                      >
                        {showAllFactures ? 'Voir moins' : `Voir les ${metroFactures.length} factures`}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Factures TAIYAT */}
          <Card>
            <CardHeader>
              <CardTitle subtitle={`${taiyatFactures.length} facture(s) recentes sur ${taiyatStats?.nb_factures || 0}`}>
                <Package className="w-5 h-5 inline mr-2 text-green-400" />
                Factures TAI YAT
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loadingTaiyat ? (
                <div className="p-8 text-center text-dark-400">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
                  Chargement...
                </div>
              ) : taiyatFactures.length === 0 ? (
                <div className="p-8 text-center text-dark-400">
                  Aucune facture TAIYAT
                </div>
              ) : (
                <div className="divide-y divide-dark-700">
                  {(showAllTaiyatFactures ? taiyatFactures : taiyatFactures.slice(0, 10)).map((facture) => (
                    <div
                      key={facture.id}
                      className="p-4 hover:bg-dark-700/30 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                            <span className="font-mono text-sm text-dark-400">
                              N°{facture.numero}
                            </span>
                            <span className="font-medium text-white">
                              TAI YAT
                            </span>
                            <Badge variant="success" size="sm">
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Facturee
                            </Badge>
                            {facture.client_nom && (
                              <Badge
                                variant={
                                  facture.client_nom === 'NOUTAM' ? 'info' :
                                  facture.client_nom === 'INCONTOURNABLE' ? 'warning' :
                                  'default'
                                }
                                size="sm"
                              >
                                {facture.client_nom}
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-sm text-dark-400">
                            <span>
                              <Calendar className="w-3 h-3 inline mr-1" />
                              {facture.date_facture ? new Date(facture.date_facture).toLocaleDateString('fr-FR') : '-'}
                            </span>
                            <span>
                              <Package className="w-3 h-3 inline mr-1" />
                              {facture.nb_lignes} produits
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold text-white">
                            {formatCurrency(facture.total_ttc)}
                          </p>
                          <p className="text-xs text-dark-400">TTC</p>
                        </div>
                      </div>
                    </div>
                  ))}
                  {taiyatFactures.length > 10 && (
                    <div className="p-4 text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowAllTaiyatFactures(!showAllTaiyatFactures)}
                      >
                        {showAllTaiyatFactures ? 'Voir moins' : `Voir les ${taiyatFactures.length} factures`}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {activeTab === 'fournisseurs' && (
        <div className="space-y-6">
          {/* Section METRO - Fournisseur DWH */}
          {loadingMetro ? (
            <Card>
              <CardContent className="py-8 text-center text-dark-400">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                Chargement METRO...
              </CardContent>
            </Card>
          ) : metroStats && (
            <Card className="border-blue-500/30 bg-gradient-to-br from-dark-800 to-blue-900/20">
              <CardContent className="py-0 px-0">
                {/* Header METRO */}
                <div
                  onClick={() => navigate('/catalog')}
                  className="p-6 cursor-pointer hover:bg-dark-700/30 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-xl bg-blue-500/20 flex items-center justify-center">
                        <Truck className="w-7 h-7 text-blue-400" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white">{metroStats.nom}</h2>
                        <p className="text-dark-400 text-sm">{metroStats.code} - Fournisseur principal</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className="text-sm text-dark-400">CA Total HT</p>
                        <p className="text-xl font-bold text-green-400">
                          {formatCurrency(metroStats.total_ht)}
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-dark-400" />
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-4 mt-6">
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Receipt className="w-3 h-3" />
                        <span className="text-xs">Factures</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(metroStats.nb_factures)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Package className="w-3 h-3" />
                        <span className="text-xs">Produits</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(metroStats.nb_produits)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Euro className="w-3 h-3" />
                        <span className="text-xs">Lignes</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(metroStats.nb_lignes)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Clients / Detenteurs */}
                {metroStats.clients.length > 0 && (
                  <div className="border-t border-dark-700 p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <Users className="w-4 h-4 text-dark-400" />
                      <h3 className="text-sm font-semibold text-dark-300">
                        Repartition par client
                      </h3>
                    </div>
                    <div className="space-y-3">
                      {metroStats.clients.map((client) => (
                        <div
                          key={client.nom}
                          className="flex items-center justify-between p-3 bg-dark-900/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              'w-3 h-3 rounded-full',
                              client.nom === 'NOUTAM' ? 'bg-purple-500' :
                              client.nom === 'INCONTOURNABLE' ? 'bg-amber-500' :
                              'bg-dark-500'
                            )} />
                            <span className="font-medium text-white">{client.nom}</span>
                          </div>
                          <div className="flex items-center gap-6">
                            <div className="text-right">
                              <p className="text-xs text-dark-400">{client.nb_factures} factures</p>
                            </div>
                            <div className="text-right min-w-[100px]">
                              <p className="font-semibold text-white">
                                {formatCurrency(client.total_ht)}
                              </p>
                              <p className="text-xs text-dark-400">
                                {client.pct_ca.toFixed(1)}% du CA
                              </p>
                            </div>
                            {/* Progress bar */}
                            <div className="w-24 h-2 bg-dark-700 rounded-full overflow-hidden">
                              <div
                                className={cn(
                                  'h-full rounded-full',
                                  client.nom === 'NOUTAM' ? 'bg-purple-500' :
                                  client.nom === 'INCONTOURNABLE' ? 'bg-amber-500' :
                                  'bg-dark-500'
                                )}
                                style={{ width: `${Math.min(client.pct_ca, 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </CardContent>
            </Card>
          )}

          {/* Section TAIYAT - Fournisseur DWH */}
          {loadingTaiyat ? (
            <Card>
              <CardContent className="py-8 text-center text-dark-400">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                Chargement TAI YAT...
              </CardContent>
            </Card>
          ) : taiyatStats && (
            <Card className="border-green-500/30 bg-gradient-to-br from-dark-800 to-green-900/20">
              <CardContent className="py-0 px-0">
                {/* Header TAIYAT */}
                <div className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-xl bg-green-500/20 flex items-center justify-center">
                        <Package className="w-7 h-7 text-green-400" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white">{taiyatStats.nom}</h2>
                        <p className="text-dark-400 text-sm">{taiyatStats.code} - Fruits & Legumes</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-dark-400">CA Total TTC</p>
                      <p className="text-xl font-bold text-green-400">
                        {formatCurrency(taiyatStats.total_ttc)}
                      </p>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-4 mt-6">
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Receipt className="w-3 h-3" />
                        <span className="text-xs">Factures</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(taiyatStats.nb_factures)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Package className="w-3 h-3" />
                        <span className="text-xs">Produits</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(taiyatStats.nb_produits)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Euro className="w-3 h-3" />
                        <span className="text-xs">Lignes</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(taiyatStats.nb_lignes)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Clients TAIYAT */}
                {taiyatStats.clients.length > 0 && (
                  <div className="border-t border-dark-700 p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <Users className="w-4 h-4 text-dark-400" />
                      <h3 className="text-sm font-semibold text-dark-300">
                        Repartition par client
                      </h3>
                    </div>
                    <div className="space-y-3">
                      {taiyatStats.clients.map((client) => {
                        const pctCA = taiyatStats.total_ttc > 0
                          ? (client.total_ttc / taiyatStats.total_ttc) * 100
                          : 0;
                        return (
                          <div
                            key={client.client_nom}
                            className="flex items-center justify-between p-3 bg-dark-900/50 rounded-lg"
                          >
                            <div className="flex items-center gap-3">
                              <div className={cn(
                                'w-3 h-3 rounded-full',
                                client.client_nom === 'NOUTAM' ? 'bg-purple-500' :
                                client.client_nom === 'INCONTOURNABLE' ? 'bg-amber-500' :
                                'bg-dark-500'
                              )} />
                              <span className="font-medium text-white">{client.client_nom}</span>
                            </div>
                            <div className="flex items-center gap-6">
                              <div className="text-right">
                                <p className="text-xs text-dark-400">{client.count} factures</p>
                              </div>
                              <div className="text-right min-w-[100px]">
                                <p className="font-semibold text-white">
                                  {formatCurrency(client.total_ttc)}
                                </p>
                                <p className="text-xs text-dark-400">
                                  {pctCA.toFixed(1)}% du CA
                                </p>
                              </div>
                              {/* Progress bar */}
                              <div className="w-24 h-2 bg-dark-700 rounded-full overflow-hidden">
                                <div
                                  className={cn(
                                    'h-full rounded-full',
                                    client.client_nom === 'NOUTAM' ? 'bg-purple-500' :
                                    client.client_nom === 'INCONTOURNABLE' ? 'bg-amber-500' :
                                    'bg-dark-500'
                                  )}
                                  style={{ width: `${Math.min(pctCA, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              </CardContent>
            </Card>
          )}

          {/* Section EUROCIEL - Fournisseur DWH */}
          {loadingEurociel ? (
            <Card>
              <CardContent className="py-8 text-center text-dark-400">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                Chargement EUROCIEL...
              </CardContent>
            </Card>
          ) : eurocielStats && (
            <Card className="border-cyan-500/30 bg-gradient-to-br from-dark-800 to-cyan-900/20">
              <CardContent className="py-0 px-0">
                {/* Header EUROCIEL */}
                <div
                  onClick={() => navigate('/catalog')}
                  className="p-6 cursor-pointer hover:bg-dark-700/30 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-xl bg-cyan-500/20 flex items-center justify-center">
                        <Fish className="w-7 h-7 text-cyan-400" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white">{eurocielStats.nom}</h2>
                        <p className="text-dark-400 text-sm">{eurocielStats.code} - Produits tropicaux</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className="text-sm text-dark-400">CA Total HT</p>
                        <p className="text-xl font-bold text-cyan-400">
                          {formatCurrency(eurocielStats.total_ht)}
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-dark-400" />
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-4 gap-4 mt-6">
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Receipt className="w-3 h-3" />
                        <span className="text-xs">Factures</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(eurocielStats.nb_factures)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Package className="w-3 h-3" />
                        <span className="text-xs">Produits</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(eurocielStats.nb_produits)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Euro className="w-3 h-3" />
                        <span className="text-xs">Lignes</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(eurocielStats.nb_lignes)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Package className="w-3 h-3" />
                        <span className="text-xs">Poids total</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(eurocielStats.poids_total_kg)} kg
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Section OTHER - Fournisseurs divers */}
          {loadingOther ? (
            <Card>
              <CardContent className="py-8 text-center text-dark-400">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                Chargement fournisseurs divers...
              </CardContent>
            </Card>
          ) : otherStats && (
            <Card className="border-orange-500/30 bg-gradient-to-br from-dark-800 to-orange-900/20">
              <CardContent className="py-0 px-0">
                {/* Header OTHER */}
                <div
                  onClick={() => navigate('/catalog')}
                  className="p-6 cursor-pointer hover:bg-dark-700/30 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-14 h-14 rounded-xl bg-orange-500/20 flex items-center justify-center">
                        <Store className="w-7 h-7 text-orange-400" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold text-white">{otherStats.nom}</h2>
                        <p className="text-dark-400 text-sm">Cash & Carry, etc.</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <p className="text-sm text-dark-400">Valeur catalogue</p>
                        <p className="text-xl font-bold text-orange-400">
                          {formatCurrency(otherStats.total_valeur)}
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-dark-400" />
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="grid grid-cols-2 gap-4 mt-6">
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Package className="w-3 h-3" />
                        <span className="text-xs">Produits</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(otherStats.nb_produits)}
                      </p>
                    </div>
                    <div className="bg-dark-900/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-dark-400 mb-1">
                        <Users className="w-3 h-3" />
                        <span className="text-xs">Fournisseurs</span>
                      </div>
                      <p className="text-lg font-semibold text-white">
                        {formatNumber(otherStats.nb_fournisseurs)}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Autres fournisseurs (Finance) */}
          <div>
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Package className="w-5 h-5 text-dark-400" />
              Autres fournisseurs
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loadingVendors ? (
            <div className="col-span-full p-8 text-center text-dark-400">
              <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4" />
              Chargement des fournisseurs...
            </div>
          ) : vendorError ? (
            <div className="col-span-full">
              <Card className="border-red-500/50 bg-red-500/10">
                <CardContent className="py-4">
                  <p className="text-red-400">{vendorError}</p>
                </CardContent>
              </Card>
            </div>
          ) : fournisseurs.length === 0 ? (
            <div className="col-span-full">
              <EmptyState
                icon={<Package className="w-12 h-12" />}
                title="Aucun fournisseur supplementaire"
                description={metroStats ? "METRO est votre fournisseur principal. Ajoutez d'autres fournisseurs ici si besoin." : "Ajoutez un fournisseur pour commencer a passer des commandes."}
                action={{
                  label: 'Ajouter un fournisseur',
                  onClick: () => setIsFournisseurModalOpen(true),
                }}
              />
            </div>
          ) : (
            fournisseurs.map((fournisseur) => (
              <Card key={fournisseur.id}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <h3 className="font-medium text-white">{fournisseur.name}</h3>
                      <p className="text-sm text-dark-400">{fournisseur.contact_name}</p>
                    </div>
                    <Badge
                      variant={fournisseur.is_active ? 'success' : 'default'}
                      size="sm"
                    >
                      {fournisseur.is_active ? 'Actif' : 'Inactif'}
                    </Badge>
                  </div>
                  <div className="space-y-2 text-sm">
                    {fournisseur.contact_phone && (
                      <div className="flex items-center gap-2 text-dark-400">
                        <Phone className="w-4 h-4" />
                        {fournisseur.contact_phone}
                      </div>
                    )}
                    {fournisseur.contact_email && (
                      <div className="flex items-center gap-2 text-dark-400">
                        <Mail className="w-4 h-4" />
                        {fournisseur.contact_email}
                      </div>
                    )}
                    {(fournisseur.address || fournisseur.city) && (
                      <div className="flex items-start gap-2 text-dark-400">
                        <MapPin className="w-4 h-4 mt-0.5" />
                        <span className="flex-1">
                          {[fournisseur.address, fournisseur.postal_code, fournisseur.city]
                            .filter(Boolean)
                            .join(', ')}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-4 pt-3 border-t border-dark-700">
                    <div className="flex-1 text-sm">
                      <span className="text-dark-400">Paiement: </span>
                      <span className="text-white">{fournisseur.payment_terms_days}j</span>
                    </div>
                    <Button variant="ghost" size="sm">
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400"
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (!confirm('Voulez-vous vraiment desactiver ce fournisseur ?')) return;
                        try {
                          await vendorsApi.deactivate(fournisseur.id);
                          loadVendors();
                        } catch (err) {
                          console.error('Erreur desactivation:', err);
                        }
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Nouvelle Commande */}
      <Modal
        isOpen={isCommandeModalOpen}
        onClose={() => setIsCommandeModalOpen(false)}
        title="Nouvelle commande"
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => setIsCommandeModalOpen(false)}
            onConfirm={handleCreateOrder}
            cancelText="Annuler"
            confirmText={creating ? 'Creation...' : 'Creer'}
            loading={creating}
          />
        }
      >
        <div className="space-y-4">
          <Select
            label="Fournisseur"
            options={[
              { value: '', label: 'Selectionner un fournisseur' },
              ...fournisseurs.filter((f) => f.is_active).map((f) => ({ value: f.id.toString(), label: f.name })),
            ]}
            value={newOrder.vendor_id}
            onChange={(e) => setNewOrder({ ...newOrder, vendor_id: e.target.value })}
          />
          <Input
            type="date"
            label="Date de commande"
            value={newOrder.date_commande}
            onChange={(e) => setNewOrder({ ...newOrder, date_commande: e.target.value })}
          />
          <Input
            type="date"
            label="Date de livraison souhaitee"
            value={newOrder.date_livraison_prevue}
            onChange={(e) => setNewOrder({ ...newOrder, date_livraison_prevue: e.target.value })}
          />
          <Input
            label="Notes"
            placeholder="Notes pour le fournisseur..."
            value={newOrder.notes}
            onChange={(e) => setNewOrder({ ...newOrder, notes: e.target.value })}
          />
          <p className="text-sm text-dark-400">
            Les produits seront ajoutes apres la creation de la commande.
          </p>
        </div>
      </Modal>

      {/* Modal Nouveau Fournisseur */}
      <Modal
        isOpen={isFournisseurModalOpen}
        onClose={() => setIsFournisseurModalOpen(false)}
        title="Nouveau fournisseur"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsFournisseurModalOpen(false)}
            onConfirm={async () => {
              if (!newVendor.name) return;
              setCreatingVendor(true);
              try {
                await vendorsApi.create(newVendor as VendorCreate);
                setIsFournisseurModalOpen(false);
                setNewVendor({
                  name: '',
                  contact_name: '',
                  contact_phone: '',
                  contact_email: '',
                  address: '',
                  payment_terms_days: 30,
                  entity_id: 1,
                });
                loadVendors();
              } catch (err) {
                console.error('Erreur creation fournisseur:', err);
              } finally {
                setCreatingVendor(false);
              }
            }}
            cancelText="Annuler"
            confirmText={creatingVendor ? 'Creation...' : 'Creer'}
            loading={creatingVendor}
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom"
            placeholder="Nom du fournisseur"
            value={newVendor.name || ''}
            onChange={(e) => setNewVendor({ ...newVendor, name: e.target.value })}
          />
          <Input
            label="Contact"
            placeholder="Nom du contact"
            value={newVendor.contact_name || ''}
            onChange={(e) => setNewVendor({ ...newVendor, contact_name: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Telephone"
              placeholder="01 23 45 67 89"
              value={newVendor.contact_phone || ''}
              onChange={(e) => setNewVendor({ ...newVendor, contact_phone: e.target.value })}
            />
            <Input
              label="Email"
              type="email"
              placeholder="contact@fournisseur.fr"
              value={newVendor.contact_email || ''}
              onChange={(e) => setNewVendor({ ...newVendor, contact_email: e.target.value })}
            />
          </div>
          <Input
            label="Adresse"
            placeholder="Adresse complete"
            value={newVendor.address || ''}
            onChange={(e) => setNewVendor({ ...newVendor, address: e.target.value })}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Code postal"
              placeholder="75001"
              value={newVendor.postal_code || ''}
              onChange={(e) => setNewVendor({ ...newVendor, postal_code: e.target.value })}
            />
            <Input
              label="Ville"
              placeholder="Paris"
              value={newVendor.city || ''}
              onChange={(e) => setNewVendor({ ...newVendor, city: e.target.value })}
            />
          </div>
          <Input
            type="number"
            label="Conditions de paiement (jours)"
            placeholder="30"
            value={newVendor.payment_terms_days || 30}
            onChange={(e) => setNewVendor({ ...newVendor, payment_terms_days: parseInt(e.target.value) || 30 })}
          />
        </div>
      </Modal>

      {/* Modal Detail Commande */}
      <Modal
        isOpen={isDetailModalOpen}
        onClose={() => {
          setIsDetailModalOpen(false);
          setSelectedOrder(null);
        }}
        title={`Commande #${selectedOrder?.id.toString().padStart(4, '0') || ''}`}
        size="xl"
      >
        {selectedOrder && (
          <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-medium text-white">
                  {selectedOrder.vendor?.name || 'Fournisseur inconnu'}
                </h3>
                <p className="text-sm text-dark-400">
                  Commande du {selectedOrder.date_commande}
                </p>
              </div>
              <Badge variant={STATUT_CONFIG[selectedOrder.statut].variant}>
                {STATUT_CONFIG[selectedOrder.statut].label}
              </Badge>
            </div>

            {/* Infos */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-dark-400">Livraison prevue</p>
                <p className="text-white">
                  {selectedOrder.date_livraison_prevue || 'Non definie'}
                </p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Livraison reelle</p>
                <p className="text-white">
                  {selectedOrder.date_livraison_reelle || '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Montant HT</p>
                <p className="text-white font-bold">
                  {formatCurrency(selectedOrder.montant_ht / 100)}
                </p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Montant TTC</p>
                <p className="text-white font-bold">
                  {formatCurrency(selectedOrder.montant_ttc / 100)}
                </p>
              </div>
            </div>

            {/* Lignes */}
            <div>
              <h4 className="font-medium text-white mb-3">
                Lignes de commande ({selectedOrder.lines?.length || 0})
              </h4>
              {selectedOrder.lines && selectedOrder.lines.length > 0 ? (
                <div className="border border-dark-700 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-dark-700">
                      <tr>
                        <th className="px-4 py-2 text-left text-sm text-dark-400">Designation</th>
                        <th className="px-4 py-2 text-right text-sm text-dark-400">Qte</th>
                        <th className="px-4 py-2 text-right text-sm text-dark-400">Prix U.</th>
                        <th className="px-4 py-2 text-right text-sm text-dark-400">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-700">
                      {selectedOrder.lines.map((line) => (
                        <tr key={line.id}>
                          <td className="px-4 py-2 text-white">{line.designation}</td>
                          <td className="px-4 py-2 text-right text-white">{line.quantity}</td>
                          <td className="px-4 py-2 text-right text-white">
                            {formatCurrency(line.prix_unitaire / 100)}
                          </td>
                          <td className="px-4 py-2 text-right text-white font-medium">
                            {formatCurrency(line.montant_ligne / 100)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-dark-400 text-center py-4">
                  Aucune ligne dans cette commande
                </p>
              )}
            </div>

            {/* Notes */}
            {selectedOrder.notes && (
              <div>
                <h4 className="font-medium text-white mb-2">Notes</h4>
                <p className="text-dark-400 text-sm">{selectedOrder.notes}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-4 border-t border-dark-700">
              {selectedOrder.statut === 'en_attente' && (
                <>
                  <Button onClick={() => handleConfirmOrder(selectedOrder.id)}>
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Confirmer
                  </Button>
                  <Button
                    variant="danger"
                    onClick={() => handleDeleteOrder(selectedOrder.id)}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Supprimer
                  </Button>
                </>
              )}
              {selectedOrder.statut === 'confirmee' && (
                <>
                  <Button onClick={() => handleShipOrder(selectedOrder.id)}>
                    <Send className="w-4 h-4 mr-2" />
                    Marquer expediee
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => handleCancelOrder(selectedOrder.id)}
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Annuler
                  </Button>
                </>
              )}
              {selectedOrder.statut === 'expediee' && (
                <>
                  <Button onClick={() => handleReceiveOrder(selectedOrder.id)}>
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Marquer livree
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => handleCancelOrder(selectedOrder.id)}
                  >
                    <XCircle className="w-4 h-4 mr-2" />
                    Annuler
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                onClick={() => {
                  setIsDetailModalOpen(false);
                  setSelectedOrder(null);
                }}
              >
                Fermer
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
