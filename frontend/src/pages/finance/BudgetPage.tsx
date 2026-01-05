import { useState } from 'react';
import { useForm } from 'react-hook-form';
import {
  PiggyBank,
  Plus,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  BarChart3
} from 'lucide-react';
import {
  useBudgets,
  useBudgetSummary,
  useFiscalYears,
  useCostCenters,
  useValidateBudget,
  useCreateBudget
} from '../../hooks/useFinance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  StatCard,
  Button,
  Select,
  Badge,
  Table,
  Progress,
  CircularProgress,
  Modal,
  Input,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { useModal, useToast } from '../../hooks';
import type { Budget } from '../../types/finance';

export default function BudgetPage() {
  const toast = useToast();
  const [selectedYear, setSelectedYear] = useState<number | undefined>();
  const [selectedCostCenter, setSelectedCostCenter] = useState<number | undefined>();
  const createModal = useModal();

  // Queries
  const { data: fiscalYears } = useFiscalYears();
  const { data: costCenters } = useCostCenters();
  const { data: budgets, isLoading } = useBudgets(selectedYear, selectedCostCenter);
  const { data: summary } = useBudgetSummary(selectedYear || 0);

  // Mutations
  const validateMutation = useValidateBudget();
  const createMutation = useCreateBudget();

  // Form for create modal
  const { register, handleSubmit, reset } = useForm<{
    cost_center_id: number;
    exercice_id: number;
    mois: number;
    montant_budgete: number;
  }>();

  const handleCreate = async (data: { cost_center_id: number; exercice_id: number; mois: number; montant_budgete: number }) => {
    try {
      await createMutation.mutateAsync(data);
      toast.success('Ligne budgetaire creee');
      createModal.close();
      reset();
    } catch {
      toast.error('Erreur lors de la creation');
    }
  };

  // Set default year
  if (!selectedYear && fiscalYears && fiscalYears.length > 0) {
    const activeYear = fiscalYears.find(y => y.est_actif);
    if (activeYear) {
      setSelectedYear(activeYear.exercice_id);
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const handleValidate = async (budget: Budget) => {
    try {
      await validateMutation.mutateAsync(budget.budget_id);
      toast.success('Budget validé');
    } catch {
      toast.error('Erreur lors de la validation');
    }
  };

  const getConsumptionVariant = (taux: number): 'success' | 'warning' | 'danger' => {
    if (taux >= 100) return 'danger';
    if (taux >= 80) return 'warning';
    return 'success';
  };

  const columns = [
    {
      key: 'cost_center',
      header: 'Centre de coût',
      render: (b: Budget) => (
        <div>
          <p className="font-medium text-white">{b.cost_center_libelle}</p>
          {b.categorie_depense_libelle && (
            <p className="text-xs text-dark-400">{b.categorie_depense_libelle}</p>
          )}
        </div>
      ),
    },
    {
      key: 'periode',
      header: 'Période',
      render: (b: Budget) => (
        <span className="text-dark-300">
          {new Date(b.annee, b.mois - 1).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })}
        </span>
      ),
    },
    {
      key: 'budgete',
      header: 'Budgété',
      align: 'right' as const,
      render: (b: Budget) => formatCurrency(b.montant_budgete),
    },
    {
      key: 'engage',
      header: 'Engagé',
      align: 'right' as const,
      render: (b: Budget) => (
        <span className="text-yellow-400">{formatCurrency(b.montant_engage)}</span>
      ),
    },
    {
      key: 'realise',
      header: 'Réalisé',
      align: 'right' as const,
      render: (b: Budget) => (
        <span className="text-primary-400">{formatCurrency(b.montant_realise)}</span>
      ),
    },
    {
      key: 'ecart',
      header: 'Écart',
      align: 'right' as const,
      render: (b: Budget) => (
        <span className={b.ecart >= 0 ? 'text-green-400' : 'text-red-400'}>
          {b.ecart >= 0 ? '+' : ''}{formatCurrency(b.ecart)}
        </span>
      ),
    },
    {
      key: 'consommation',
      header: 'Consommation',
      width: '150px',
      render: (b: Budget) => (
        <div className="flex items-center gap-2">
          <Progress
            value={b.taux_consommation}
            max={100}
            variant={getConsumptionVariant(b.taux_consommation)}
            size="sm"
            className="flex-1"
          />
          <span className="text-xs text-dark-400 w-10">
            {Math.round(b.taux_consommation)}%
          </span>
        </div>
      ),
    },
    {
      key: 'statut',
      header: 'Statut',
      render: (b: Budget) => (
        <Badge
          variant={
            b.statut === 'valide' ? 'success' :
            b.statut === 'cloture' ? 'default' :
            'warning'
          }
        >
          {b.statut === 'brouillon' ? 'Brouillon' :
           b.statut === 'valide' ? 'Validé' : 'Clôturé'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      width: '80px',
      render: (b: Budget) => (
        b.statut === 'brouillon' && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => handleValidate(b)}
            loading={validateMutation.isPending}
          >
            <CheckCircle className="w-4 h-4 mr-1" />
            Valider
          </Button>
        )
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Budget"
        subtitle="Suivi et contrôle budgétaire"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Budget' },
        ]}
        actions={
          <Button leftIcon={<Plus className="w-4 h-4" />} onClick={() => createModal.open()}>
            Nouveau budget
          </Button>
        }
      />

      {/* Filtres */}
      <Card padding="sm">
        <CardContent>
          <div className="flex items-center gap-4">
            <Select
              label="Exercice"
              options={[
                { value: '', label: 'Tous les exercices' },
                ...(fiscalYears?.map(y => ({
                  value: String(y.exercice_id),
                  label: y.libelle + (y.est_actif ? ' (actif)' : '')
                })) || [])
              ]}
              value={selectedYear ? String(selectedYear) : ''}
              onChange={(e) => setSelectedYear(e.target.value ? Number(e.target.value) : undefined)}
              className="w-48"
            />
            <Select
              label="Centre de coût"
              options={[
                { value: '', label: 'Tous les centres' },
                ...(costCenters?.map(c => ({
                  value: String(c.cost_center_id),
                  label: c.libelle
                })) || [])
              ]}
              value={selectedCostCenter ? String(selectedCostCenter) : ''}
              onChange={(e) => setSelectedCostCenter(e.target.value ? Number(e.target.value) : undefined)}
              className="w-48"
            />
          </div>
        </CardContent>
      </Card>

      {/* Résumé */}
      {summary && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <Card className="lg:col-span-1">
            <CardContent className="flex flex-col items-center justify-center py-6">
              <CircularProgress
                value={summary.taux_consommation_global}
                max={100}
                size={120}
                strokeWidth={10}
                variant={getConsumptionVariant(summary.taux_consommation_global)}
                label="consommé"
              />
              <p className="mt-4 text-dark-400">Taux de consommation global</p>
            </CardContent>
          </Card>

          <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              title="Budget total"
              value={formatCurrency(summary.total_budgete)}
              icon={<PiggyBank className="w-6 h-6" />}
            />
            <StatCard
              title="Réalisé"
              value={formatCurrency(summary.total_realise)}
              icon={<BarChart3 className="w-6 h-6" />}
            />
            <StatCard
              title="Écart global"
              value={formatCurrency(summary.ecart_global)}
              icon={summary.ecart_global >= 0 ?
                <TrendingUp className="w-6 h-6" /> :
                <TrendingDown className="w-6 h-6" />
              }
              trend={summary.ecart_global >= 0 ? 'up' : 'down'}
            />
          </div>
        </div>
      )}

      {/* Alertes dépassement */}
      {summary?.par_cost_center?.some(c => c.taux > 90) && (
        <Alert
          variant="warning"
          title="Attention aux dépassements"
          icon={<AlertTriangle className="w-5 h-5" />}
        >
          {summary.par_cost_center.filter(c => c.taux > 90).map(c => (
            <span key={c.cost_center_id} className="block">
              {c.cost_center_libelle}: {Math.round(c.taux)}% du budget consommé
            </span>
          ))}
        </Alert>
      )}

      {/* Tableau par centre de coût */}
      {summary && (
        <Card>
          <CardHeader>
            <CardTitle>Répartition par centre de coût</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {summary.par_cost_center?.map((cc) => (
                <div key={cc.cost_center_id} className="p-4 bg-dark-700/50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-white">{cc.cost_center_libelle}</span>
                    <span className={cc.ecart >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {cc.ecart >= 0 ? '+' : ''}{formatCurrency(cc.ecart)}
                    </span>
                  </div>
                  <Progress
                    value={cc.taux}
                    max={100}
                    variant={getConsumptionVariant(cc.taux)}
                    showLabel
                    label={`${formatCurrency(cc.realise)} / ${formatCurrency(cc.budgete)}`}
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Détail des lignes budgétaires */}
      <Card>
        <CardHeader>
          <CardTitle>Détail des lignes budgétaires</CardTitle>
        </CardHeader>
        <CardContent>
          <Table
            data={budgets || []}
            columns={columns}
            keyExtractor={(b) => b.budget_id}
            loading={isLoading}
            emptyMessage="Aucune ligne budgétaire"
          />
        </CardContent>
      </Card>

      {/* Modal création */}
      <Modal
        isOpen={createModal.isOpen}
        onClose={createModal.close}
        title="Nouvelle ligne budgetaire"
        size="md"
      >
        <form onSubmit={handleSubmit(handleCreate)} className="space-y-4">
          <div>
            <label className="label">Centre de cout *</label>
            <Select
              {...register('cost_center_id', { required: true, valueAsNumber: true })}
              options={[
                { value: '', label: 'Selectionner...' },
                ...(costCenters?.map(c => ({
                  value: String(c.cost_center_id),
                  label: c.libelle
                })) || [])
              ]}
            />
          </div>
          <div>
            <label className="label">Exercice *</label>
            <Select
              {...register('exercice_id', { required: true, valueAsNumber: true })}
              options={[
                { value: '', label: 'Selectionner...' },
                ...(fiscalYears?.map(y => ({
                  value: String(y.exercice_id),
                  label: y.libelle
                })) || [])
              ]}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Mois *</label>
              <Select
                {...register('mois', { required: true, valueAsNumber: true })}
                options={Array.from({ length: 12 }, (_, i) => ({
                  value: String(i + 1),
                  label: new Date(2024, i).toLocaleDateString('fr-FR', { month: 'long' })
                }))}
              />
            </div>
            <div>
              <label className="label">Montant budgete *</label>
              <Input
                type="number"
                step="0.01"
                placeholder="0.00"
                {...register('montant_budgete', { required: true, valueAsNumber: true })}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="ghost" onClick={() => { createModal.close(); reset(); }}>
              Annuler
            </Button>
            <Button type="submit" loading={createMutation.isPending}>
              Creer
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
