import { useState } from 'react';
import {
  Receipt,
  Plus,
  Edit2,
  Trash2,
  RefreshCw,
  PieChart,
  Calendar,
} from 'lucide-react';
import {
  useCharges,
  useChargesSummary,
  useCreateCharge,
  useUpdateCharge,
  useDeleteCharge,
} from '../../hooks/useRestaurant';
import type { Charge, ChargeCreate, ChargeUpdate } from '../../types/restaurant';
import {
  RestaurantChargeType,
  RestaurantChargeFrequency,
  CHARGE_TYPE_LABELS,
  CHARGE_FREQUENCY_LABELS,
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
  EmptyState,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency } from '../../lib/utils';

export default function ChargesPage() {
  const [selectedType, setSelectedType] = useState<RestaurantChargeType | undefined>();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingCharge, setEditingCharge] = useState<Charge | null>(null);

  const [formData, setFormData] = useState<ChargeCreate>({
    name: '',
    charge_type: RestaurantChargeType.AUTRES,
    montant: 0,
    frequency: RestaurantChargeFrequency.MENSUEL,
    date_debut: new Date().toISOString().split('T')[0],
    notes: '',
  });

  const { data: charges, isLoading, refetch } = useCharges(selectedType);
  const { data: summary } = useChargesSummary();
  const createCharge = useCreateCharge();
  const updateCharge = useUpdateCharge();
  const deleteCharge = useDeleteCharge();

  const typeOptions = [
    { value: '', label: 'Tous les types' },
    ...Object.entries(CHARGE_TYPE_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  ];

  const frequencyOptions = Object.entries(CHARGE_FREQUENCY_LABELS).map(([value, label]) => ({
    value,
    label,
  }));

  const filteredCharges = selectedType
    ? charges?.filter(c => c.type === selectedType)
    : charges;

  const handleCreate = async () => {
    try {
      await createCharge.mutateAsync({
        ...formData,
        montant: Math.round(formData.montant * 100),
      });
      setIsCreateModalOpen(false);
      resetForm();
    } catch (error) {
      console.error('Erreur creation:', error);
    }
  };

  const handleUpdate = async () => {
    if (!editingCharge) return;
    try {
      const updateData: ChargeUpdate = {
        name: formData.name,
        charge_type: formData.charge_type,
        montant: Math.round(formData.montant * 100),
        frequency: formData.frequency,
        date_debut: formData.date_debut,
        date_fin: formData.date_fin,
        notes: formData.notes,
      };
      await updateCharge.mutateAsync({ id: editingCharge.id, data: updateData });
      setEditingCharge(null);
      resetForm();
    } catch (error) {
      console.error('Erreur modification:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Desactiver cette charge ?')) return;
    try {
      await deleteCharge.mutateAsync(id);
    } catch (error) {
      console.error('Erreur suppression:', error);
    }
  };

  const openEditModal = (charge: Charge) => {
    setEditingCharge(charge);
    setFormData({
      name: charge.name,
      charge_type: charge.type,
      montant: charge.montant / 100,
      frequency: charge.frequency,
      date_debut: charge.date_debut,
      date_fin: charge.date_fin || undefined,
      notes: charge.notes || '',
    });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      charge_type: RestaurantChargeType.AUTRES,
      montant: 0,
      frequency: RestaurantChargeFrequency.MENSUEL,
      date_debut: new Date().toISOString().split('T')[0],
      notes: '',
    });
  };

  // Calcul du total par type pour le pie chart
  const chargesByType: Record<RestaurantChargeType, number> = charges?.reduce((acc, charge) => {
    if (!acc[charge.type]) acc[charge.type] = 0;
    acc[charge.type] += charge.montant_mensuel;
    return acc;
  }, {} as Record<RestaurantChargeType, number>) || {} as Record<RestaurantChargeType, number>;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des charges..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Charges fixes"
        subtitle="Gestion des charges du restaurant"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Charges' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouvelle charge
            </Button>
          </div>
        }
      />

      {/* Resume */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Total mensuel</p>
                <p className="text-3xl font-bold text-white">
                  {formatCurrency((summary?.total_mensuel || 0) / 100)}
                </p>
              </div>
              <Receipt className="w-10 h-10 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Nombre de charges</p>
                <p className="text-3xl font-bold text-white">{charges?.length || 0}</p>
              </div>
              <Receipt className="w-10 h-10 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Charges actives</p>
                <p className="text-3xl font-bold text-green-400">
                  {charges?.filter(c => c.is_active).length || 0}
                </p>
              </div>
              <Receipt className="w-10 h-10 text-green-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Repartition par type */}
        <Card>
          <CardHeader>
            <CardTitle>
              <PieChart className="w-5 h-5 inline mr-2" />
              Repartition mensuelle
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(chargesByType).map(([type, montant]) => {
                const percentage = summary?.total_mensuel
                  ? ((montant / summary.total_mensuel) * 100).toFixed(1)
                  : '0';
                return (
                  <div key={type} className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-dark-300">
                        {CHARGE_TYPE_LABELS[type as RestaurantChargeType]}
                      </span>
                      <span className="text-white">
                        {formatCurrency(montant / 100)} ({percentage}%)
                      </span>
                    </div>
                    <div className="h-2 bg-dark-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 rounded-full"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}

              {Object.keys(chargesByType).length === 0 && (
                <p className="text-center text-dark-400 py-4">Aucune charge</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Liste des charges */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle subtitle={`${filteredCharges?.length || 0} charge(s)`}>
              <Receipt className="w-5 h-5 inline mr-2" />
              Liste des charges
            </CardTitle>
          </CardHeader>
          <CardContent>
            {/* Filtre */}
            <div className="mb-4">
              <Select
                options={typeOptions}
                value={selectedType || ''}
                onChange={(e) => setSelectedType(e.target.value as RestaurantChargeType || undefined)}
              />
            </div>

            {filteredCharges && filteredCharges.length > 0 ? (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {filteredCharges.map((charge) => (
                  <div
                    key={charge.id}
                    className={`p-4 bg-dark-700/50 rounded-lg ${!charge.is_active ? 'opacity-50' : ''}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="font-medium text-white">{charge.name}</span>
                          <Badge variant="default" size="sm">
                            {CHARGE_TYPE_LABELS[charge.type]}
                          </Badge>
                          <Badge variant="info" size="sm">
                            {CHARGE_FREQUENCY_LABELS[charge.frequency]}
                          </Badge>
                          {!charge.is_active && (
                            <Badge variant="default" size="sm">Inactive</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-dark-400">
                          <span>
                            <Calendar className="w-3 h-3 inline mr-1" />
                            Depuis {charge.date_debut}
                          </span>
                          {charge.date_fin && (
                            <span>Jusqu'au {charge.date_fin}</span>
                          )}
                        </div>
                        {charge.notes && (
                          <p className="text-sm text-dark-400 mt-1">{charge.notes}</p>
                        )}
                      </div>
                      <div className="text-right ml-4">
                        <p className="text-lg font-bold text-white">
                          {formatCurrency(charge.montant / 100)}
                        </p>
                        <p className="text-xs text-dark-400">
                          {formatCurrency(charge.montant_mensuel / 100)}/mois
                        </p>
                        <div className="flex gap-1 mt-2 justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(charge)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => handleDelete(charge.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<Receipt className="w-12 h-12" />}
                title="Aucune charge"
                description="Ajoutez vos premieres charges fixes."
                action={{
                  label: 'Ajouter une charge',
                  onClick: () => setIsCreateModalOpen(true),
                }}
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Modal creation/edition */}
      <Modal
        isOpen={isCreateModalOpen || !!editingCharge}
        onClose={() => {
          setIsCreateModalOpen(false);
          setEditingCharge(null);
          resetForm();
        }}
        title={editingCharge ? 'Modifier la charge' : 'Nouvelle charge'}
        size="md"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsCreateModalOpen(false);
              setEditingCharge(null);
              resetForm();
            }}
            onConfirm={editingCharge ? handleUpdate : handleCreate}
            cancelText="Annuler"
            confirmText={editingCharge ? 'Modifier' : 'Creer'}
            loading={createCharge.isPending || updateCharge.isPending}
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom de la charge"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Ex: Loyer local"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Type"
              options={Object.entries(CHARGE_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
              value={formData.charge_type}
              onChange={(e) => setFormData(prev => ({ ...prev, charge_type: e.target.value as RestaurantChargeType }))}
            />

            <Select
              label="Frequence"
              options={frequencyOptions}
              value={formData.frequency || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, frequency: e.target.value as RestaurantChargeFrequency }))}
            />
          </div>

          <Input
            type="number"
            label="Montant (EUR)"
            value={formData.montant || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, montant: Number(e.target.value) }))}
            placeholder="0.00"
            step="0.01"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              type="date"
              label="Date debut"
              value={formData.date_debut || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, date_debut: e.target.value }))}
            />

            <Input
              type="date"
              label="Date fin (optionnel)"
              value={formData.date_fin || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, date_fin: e.target.value || undefined }))}
            />
          </div>

          <Input
            label="Notes"
            value={formData.notes || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Notes..."
          />
        </div>
      </Modal>
    </div>
  );
}
