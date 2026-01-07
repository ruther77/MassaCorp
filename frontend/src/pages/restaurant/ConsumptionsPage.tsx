import { useState, useMemo } from 'react';
import {
  ShoppingCart,
  AlertTriangle,
  Users,
  Gift,
  RefreshCw,
  TrendingUp,
  Calendar,
  Trophy,
} from 'lucide-react';
import {
  useConsumptions,
  useDailySummary,
  useBestSellers,
  usePlats,
  useRecordSale,
  useRecordLoss,
  useRecordStaffMeal,
  useRecordOffered,
} from '../../hooks/useRestaurant';
import type { ConsumptionCreate } from '../../types/restaurant';
import {
  RestaurantConsumptionType,
  CONSUMPTION_TYPE_LABELS,
} from '../../types/restaurant';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Select,
  Badge,
  Spinner,
  Modal,
  ModalFooter,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency } from '../../lib/utils';

export default function ConsumptionsPage() {
  const today = new Date().toISOString().split('T')[0];
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
  const [recordType, setRecordType] = useState<'sale' | 'loss' | 'staff' | 'offered'>('sale');

  const [formData, setFormData] = useState<ConsumptionCreate>({
    plat_id: 0,
    quantite: 1,
    prix_vente: undefined,
    notes: '',
    decrement_stock: true,
  });

  const { data: consumptions, isLoading, refetch } = useConsumptions(startDate, endDate);
  const { data: dailySummary } = useDailySummary(today);
  const { data: bestSellers } = useBestSellers(startDate, endDate, 5);
  const { data: plats } = usePlats();

  const recordSale = useRecordSale();
  const recordLoss = useRecordLoss();
  const recordStaffMeal = useRecordStaffMeal();
  const recordOffered = useRecordOffered();

  const platOptions = plats?.map(p => ({
    value: p.id,
    label: `${p.name} - ${formatCurrency(p.prix_vente / 100)}`,
  })) || [];

  const stats = useMemo(() => {
    if (!consumptions) return { sales: 0, losses: 0, staff: 0, offered: 0 };
    return {
      sales: consumptions.filter(c => c.type === RestaurantConsumptionType.VENTE).length,
      losses: consumptions.filter(c => c.type === RestaurantConsumptionType.PERTE).length,
      staff: consumptions.filter(c => c.type === RestaurantConsumptionType.REPAS_STAFF).length,
      offered: consumptions.filter(c => c.type === RestaurantConsumptionType.OFFERT).length,
    };
  }, [consumptions]);

  const openRecordModal = (type: 'sale' | 'loss' | 'staff' | 'offered') => {
    setRecordType(type);
    setFormData({
      plat_id: 0,
      quantite: 1,
      prix_vente: undefined,
      notes: '',
      decrement_stock: true,
    });
    setIsRecordModalOpen(true);
  };

  const handleRecord = async () => {
    const data: ConsumptionCreate = {
      ...formData,
      prix_vente: formData.prix_vente ? Math.round(formData.prix_vente * 100) : undefined,
    };

    try {
      switch (recordType) {
        case 'sale':
          await recordSale.mutateAsync(data);
          break;
        case 'loss':
          await recordLoss.mutateAsync(data);
          break;
        case 'staff':
          await recordStaffMeal.mutateAsync(data);
          break;
        case 'offered':
          await recordOffered.mutateAsync(data);
          break;
      }
      setIsRecordModalOpen(false);
      refetch();
    } catch (error) {
      console.error('Erreur enregistrement:', error);
    }
  };

  const getRecordTitle = () => {
    switch (recordType) {
      case 'sale': return 'Enregistrer une vente';
      case 'loss': return 'Enregistrer une perte';
      case 'staff': return 'Enregistrer un repas staff';
      case 'offered': return 'Enregistrer un offert';
    }
  };

  const getConsumptionBadge = (type: RestaurantConsumptionType) => {
    switch (type) {
      case RestaurantConsumptionType.VENTE:
        return <Badge variant="success" size="sm">{CONSUMPTION_TYPE_LABELS[type]}</Badge>;
      case RestaurantConsumptionType.PERTE:
        return <Badge variant="danger" size="sm">{CONSUMPTION_TYPE_LABELS[type]}</Badge>;
      case RestaurantConsumptionType.REPAS_STAFF:
        return <Badge variant="info" size="sm">{CONSUMPTION_TYPE_LABELS[type]}</Badge>;
      case RestaurantConsumptionType.OFFERT:
        return <Badge variant="warning" size="sm">{CONSUMPTION_TYPE_LABELS[type]}</Badge>;
      default:
        return <Badge variant="default" size="sm">{type}</Badge>;
    }
  };

  const isRecording = recordSale.isPending || recordLoss.isPending || recordStaffMeal.isPending || recordOffered.isPending;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des ventes..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ventes & Consommations"
        subtitle="Enregistrement et suivi des ventes"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Ventes' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button onClick={() => openRecordModal('sale')}>
              <ShoppingCart className="w-4 h-4 mr-2" />
              Nouvelle vente
            </Button>
          </div>
        }
      />

      {/* Resume du jour */}
      {dailySummary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">CA du jour</p>
                  <p className="text-3xl font-bold text-green-400">
                    {formatCurrency(dailySummary.total_revenue / 100)}
                  </p>
                </div>
                <TrendingUp className="w-10 h-10 text-green-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Ventes</p>
                  <p className="text-3xl font-bold text-white">{dailySummary.ventes.count}</p>
                </div>
                <ShoppingCart className="w-10 h-10 text-primary-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Pertes</p>
                  <p className="text-3xl font-bold text-red-400">{dailySummary.pertes.count}</p>
                </div>
                <AlertTriangle className="w-10 h-10 text-red-500" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-dark-400">Marge</p>
                  <p className={`text-3xl font-bold ${dailySummary.margin >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(dailySummary.margin / 100)}
                  </p>
                </div>
                <TrendingUp className="w-10 h-10 text-blue-500" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Actions rapides */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card hover className="cursor-pointer" onClick={() => openRecordModal('sale')}>
          <CardContent className="py-4 text-center">
            <ShoppingCart className="w-8 h-8 mx-auto text-green-500 mb-2" />
            <p className="text-sm font-medium text-white">Vente</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => openRecordModal('loss')}>
          <CardContent className="py-4 text-center">
            <AlertTriangle className="w-8 h-8 mx-auto text-red-500 mb-2" />
            <p className="text-sm font-medium text-white">Perte</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => openRecordModal('staff')}>
          <CardContent className="py-4 text-center">
            <Users className="w-8 h-8 mx-auto text-blue-500 mb-2" />
            <p className="text-sm font-medium text-white">Repas staff</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => openRecordModal('offered')}>
          <CardContent className="py-4 text-center">
            <Gift className="w-8 h-8 mx-auto text-yellow-500 mb-2" />
            <p className="text-sm font-medium text-white">Offert</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Meilleures ventes */}
        <Card>
          <CardHeader>
            <CardTitle>
              <Trophy className="w-5 h-5 inline mr-2 text-yellow-500" />
              Top ventes
            </CardTitle>
          </CardHeader>
          <CardContent>
            {bestSellers && bestSellers.length > 0 ? (
              <div className="space-y-3">
                {bestSellers.map((item, idx) => (
                  <div key={item.plat_id} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold ${
                        idx === 0 ? 'bg-yellow-500 text-dark-900' :
                        idx === 1 ? 'bg-gray-400 text-dark-900' :
                        idx === 2 ? 'bg-amber-700 text-white' :
                        'bg-dark-600 text-dark-300'
                      }`}>
                        {idx + 1}
                      </span>
                      <span className="text-white">{item.plat_name}</span>
                    </div>
                    <div className="text-right">
                      <p className="text-white font-medium">{item.total_sold}</p>
                      <p className="text-xs text-dark-400">{formatCurrency(item.total_revenue / 100)}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-dark-400 py-4">Aucune donnee</p>
            )}
          </CardContent>
        </Card>

        {/* Historique */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle subtitle="Filtrer par periode">
              <Calendar className="w-5 h-5 inline mr-2" />
              Historique
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Filtres dates */}
            <div className="flex gap-4 mb-4">
              <Input
                type="date"
                label="Du"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <Input
                type="date"
                label="Au"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>

            {/* Stats periode */}
            <div className="grid grid-cols-4 gap-2 mb-4">
              <div className="text-center p-2 bg-dark-700 rounded">
                <p className="text-xl font-bold text-green-400">{stats.sales}</p>
                <p className="text-xs text-dark-400">Ventes</p>
              </div>
              <div className="text-center p-2 bg-dark-700 rounded">
                <p className="text-xl font-bold text-red-400">{stats.losses}</p>
                <p className="text-xs text-dark-400">Pertes</p>
              </div>
              <div className="text-center p-2 bg-dark-700 rounded">
                <p className="text-xl font-bold text-blue-400">{stats.staff}</p>
                <p className="text-xs text-dark-400">Staff</p>
              </div>
              <div className="text-center p-2 bg-dark-700 rounded">
                <p className="text-xl font-bold text-yellow-400">{stats.offered}</p>
                <p className="text-xs text-dark-400">Offerts</p>
              </div>
            </div>

            {/* Liste */}
            <div className="max-h-64 overflow-y-auto">
              {consumptions && consumptions.length > 0 ? (
                <table className="w-full">
                  <thead className="bg-dark-700/50 sticky top-0">
                    <tr>
                      <th className="px-2 py-2 text-left text-xs text-dark-400">Date</th>
                      <th className="px-2 py-2 text-left text-xs text-dark-400">Plat</th>
                      <th className="px-2 py-2 text-center text-xs text-dark-400">Qte</th>
                      <th className="px-2 py-2 text-center text-xs text-dark-400">Type</th>
                      <th className="px-2 py-2 text-right text-xs text-dark-400">Montant</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-dark-700">
                    {consumptions.map((c) => (
                      <tr key={c.id}>
                        <td className="px-2 py-2 text-sm text-dark-300">{c.date}</td>
                        <td className="px-2 py-2 text-sm text-white">{c.plat_name}</td>
                        <td className="px-2 py-2 text-sm text-center text-white">{c.quantite}</td>
                        <td className="px-2 py-2 text-center">{getConsumptionBadge(c.type)}</td>
                        <td className="px-2 py-2 text-sm text-right">
                          {c.type === RestaurantConsumptionType.VENTE ? (
                            <span className="text-green-400">+{formatCurrency(c.prix_vente / 100)}</span>
                          ) : (
                            <span className="text-red-400">-{formatCurrency(c.cout / 100)}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-center text-dark-400 py-4">Aucune consommation</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modal enregistrement */}
      <Modal
        isOpen={isRecordModalOpen}
        onClose={() => setIsRecordModalOpen(false)}
        title={getRecordTitle()}
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsRecordModalOpen(false)}
            onConfirm={handleRecord}
            cancelText="Annuler"
            confirmText="Enregistrer"
            loading={isRecording}
          />
        }
      >
        <div className="space-y-4">
          <Select
            label="Plat"
            options={[{ value: '', label: 'Selectionnez un plat' }, ...platOptions]}
            value={formData.plat_id || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, plat_id: Number(e.target.value) }))}
          />

          <Input
            type="number"
            label="Quantite"
            value={formData.quantite || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, quantite: Number(e.target.value) }))}
            min="1"
          />

          {recordType === 'sale' && (
            <Input
              type="number"
              label="Prix de vente (EUR) - laisser vide pour prix par defaut"
              value={formData.prix_vente || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, prix_vente: e.target.value ? Number(e.target.value) : undefined }))}
              step="0.01"
            />
          )}

          <Input
            label="Notes"
            value={formData.notes || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Notes..."
          />

          <label className="flex items-center gap-2 text-sm text-dark-300">
            <input
              type="checkbox"
              checked={formData.decrement_stock}
              onChange={(e) => setFormData(prev => ({ ...prev, decrement_stock: e.target.checked }))}
              className="rounded border-dark-600"
            />
            Decrementer le stock
          </label>
        </div>
      </Modal>
    </div>
  );
}
