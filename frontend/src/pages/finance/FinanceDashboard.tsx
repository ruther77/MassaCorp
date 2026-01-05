import {
  Wallet,
  FileText,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Calendar,
  CreditCard,
  PiggyBank,
  BarChart3
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  useFinanceKPIs,
  useTreasurySummary,
  useUpcomingDueDates,
  useOverdueDueDates,
  useCashFlowChart
} from '../../hooks/useFinance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  StatCard,
  Badge,
  Spinner,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatDate } from '../../lib/utils';

export default function FinanceDashboard() {
  const { data: kpis, isLoading: loadingKpis } = useFinanceKPIs();
  const { data: treasury, isLoading: loadingTreasury } = useTreasurySummary();
  const { data: upcomingDueDates } = useUpcomingDueDates(7);
  const { data: overdueDueDates } = useOverdueDueDates();
  const { data: cashFlowData } = useCashFlowChart('month');

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  if (loadingKpis || loadingTreasury) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Finance"
        subtitle="Vue d'ensemble de votre situation financière"
        breadcrumbs={[{ label: 'Finance' }]}
      />

      {/* KPIs principaux */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Trésorerie totale"
          value={formatCurrency(treasury?.solde_total || 0)}
          icon={<Wallet className="w-6 h-6" />}
          trend={treasury?.variation_mois && treasury.variation_mois >= 0 ? 'up' : 'down'}
          change={treasury?.variation_mois ? {
            value: treasury.variation_mois,
            label: 'ce mois'
          } : undefined}
        />

        <StatCard
          title="Factures en attente"
          value={kpis?.factures_en_attente || 0}
          icon={<FileText className="w-6 h-6" />}
          className={kpis?.factures_en_attente && kpis.factures_en_attente > 10 ? 'border-yellow-500/50' : ''}
        />

        <StatCard
          title="En retard"
          value={kpis?.factures_en_retard || 0}
          icon={<AlertTriangle className="w-6 h-6" />}
          trend={kpis?.factures_en_retard && kpis.factures_en_retard > 0 ? 'down' : 'neutral'}
          className={kpis?.factures_en_retard && kpis.factures_en_retard > 0 ? 'border-red-500/50' : ''}
        />

        <StatCard
          title="Budget consommé"
          value={`${kpis?.budget_consomme_pct || 0}%`}
          icon={<PiggyBank className="w-6 h-6" />}
          trend={kpis?.budget_consomme_pct && kpis.budget_consomme_pct > 80 ? 'down' : 'up'}
        />
      </div>

      {/* Alertes */}
      {(overdueDueDates?.length || 0) > 0 && (
        <Alert variant="warning" title="Échéances en retard">
          Vous avez {overdueDueDates?.length} échéance(s) en retard pour un montant total de{' '}
          {formatCurrency(overdueDueDates?.reduce((sum, d) => sum + d.montant_restant, 0) || 0)}.
          <Link to="/finance/echeances?filter=overdue" className="ml-2 underline">
            Voir le détail
          </Link>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trésorerie par compte */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle subtitle="Évolution sur le mois">
              Flux de trésorerie
            </CardTitle>
          </CardHeader>
          <CardContent>
            {cashFlowData && cashFlowData.length > 0 ? (
              <div className="h-64 flex items-end gap-1">
                {cashFlowData.slice(-14).map((day, i) => {
                  const maxValue = Math.max(
                    ...cashFlowData.map(d => Math.max(d.encaissements, d.decaissements))
                  );
                  const encHeight = (day.encaissements / maxValue) * 100;
                  const decHeight = (day.decaissements / maxValue) * 100;

                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-1">
                      <div className="w-full flex gap-0.5 h-48 items-end">
                        <div
                          className="flex-1 bg-green-600 rounded-t"
                          style={{ height: `${encHeight}%` }}
                          title={`Encaissements: ${formatCurrency(day.encaissements)}`}
                        />
                        <div
                          className="flex-1 bg-red-500 rounded-t"
                          style={{ height: `${decHeight}%` }}
                          title={`Décaissements: ${formatCurrency(day.decaissements)}`}
                        />
                      </div>
                      <span className="text-xs text-dark-500">
                        {new Date(day.date).getDate()}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center text-dark-400">
                Pas de données disponibles
              </div>
            )}
            <div className="flex items-center justify-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-600 rounded" />
                <span className="text-sm text-dark-400">Encaissements</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded" />
                <span className="text-sm text-dark-400">Décaissements</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Soldes par devise */}
        <Card>
          <CardHeader>
            <CardTitle>Soldes par devise</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {treasury?.solde_par_devise?.map((solde) => (
                <div key={solde.devise_code} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-dark-700 rounded-lg flex items-center justify-center font-bold text-primary-500">
                      {solde.devise_code}
                    </div>
                    <div>
                      <p className="font-medium text-white">{formatCurrency(solde.solde)}</p>
                      {solde.devise_code !== 'EUR' && (
                        <p className="text-xs text-dark-400">
                          ≈ {formatCurrency(solde.solde_eur)} EUR
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )) || (
                <p className="text-dark-400 text-sm">Aucune donnée</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Échéances à venir */}
        <Card>
          <CardHeader
            action={
              <Link to="/finance/echeances" className="text-sm text-primary-500 hover:text-primary-400 flex items-center gap-1">
                Tout voir <ArrowRight className="w-4 h-4" />
              </Link>
            }
          >
            <CardTitle
              subtitle={`${upcomingDueDates?.length || 0} dans les 7 prochains jours`}
            >
              <Calendar className="w-5 h-5 inline mr-2" />
              Échéances à venir
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {upcomingDueDates?.slice(0, 5).map((dueDate) => (
                <div
                  key={dueDate.echeance_id}
                  className="flex items-center justify-between p-3 bg-dark-700/50 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-white">{dueDate.fournisseur_nom || dueDate.client_nom}</p>
                    <p className="text-sm text-dark-400">
                      {dueDate.facture_numero} • {formatDate(dueDate.date_echeance)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-white">
                      {formatCurrency(dueDate.montant_restant)}
                    </p>
                    {dueDate.est_en_retard && (
                      <Badge variant="danger" size="sm">
                        {dueDate.jours_retard}j retard
                      </Badge>
                    )}
                  </div>
                </div>
              )) || (
                <p className="text-dark-400 text-sm text-center py-4">
                  Aucune échéance dans les 7 prochains jours
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Prévisions */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="30 prochains jours">
              <BarChart3 className="w-5 h-5 inline mr-2" />
              Prévisions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-green-900/20 rounded-lg border border-green-700/50">
                <div className="flex items-center gap-3">
                  <TrendingUp className="w-5 h-5 text-green-500" />
                  <span className="text-dark-200">Encaissements prévus</span>
                </div>
                <span className="font-bold text-green-400">
                  {formatCurrency(kpis?.encaissements_prevus_mois || 0)}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 bg-red-900/20 rounded-lg border border-red-700/50">
                <div className="flex items-center gap-3">
                  <TrendingDown className="w-5 h-5 text-red-500" />
                  <span className="text-dark-200">Décaissements prévus</span>
                </div>
                <span className="font-bold text-red-400">
                  {formatCurrency(kpis?.decaissements_prevus_mois || 0)}
                </span>
              </div>

              <div className="pt-4 border-t border-dark-700">
                <div className="flex items-center justify-between">
                  <span className="text-dark-300">Solde prévisionnel</span>
                  <span className="text-xl font-bold text-white">
                    {formatCurrency(
                      (treasury?.solde_total || 0) +
                      (kpis?.encaissements_prevus_mois || 0) -
                      (kpis?.decaissements_prevus_mois || 0)
                    )}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Accès rapides */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link to="/finance/factures" className="group">
          <Card hover className="text-center py-6">
            <FileText className="w-8 h-8 mx-auto text-primary-500 mb-2 group-hover:scale-110 transition-transform" />
            <p className="font-medium text-white">Factures</p>
            <p className="text-sm text-dark-400">{kpis?.factures_en_attente || 0} en attente</p>
          </Card>
        </Link>

        <Link to="/finance/paiements" className="group">
          <Card hover className="text-center py-6">
            <CreditCard className="w-8 h-8 mx-auto text-green-500 mb-2 group-hover:scale-110 transition-transform" />
            <p className="font-medium text-white">Paiements</p>
            <p className="text-sm text-dark-400">Gérer les paiements</p>
          </Card>
        </Link>

        <Link to="/finance/tresorerie" className="group">
          <Card hover className="text-center py-6">
            <Wallet className="w-8 h-8 mx-auto text-blue-500 mb-2 group-hover:scale-110 transition-transform" />
            <p className="font-medium text-white">Trésorerie</p>
            <p className="text-sm text-dark-400">Suivre les flux</p>
          </Card>
        </Link>

        <Link to="/finance/budget" className="group">
          <Card hover className="text-center py-6">
            <PiggyBank className="w-8 h-8 mx-auto text-yellow-500 mb-2 group-hover:scale-110 transition-transform" />
            <p className="font-medium text-white">Budget</p>
            <p className="text-sm text-dark-400">{kpis?.budget_consomme_pct || 0}% consommé</p>
          </Card>
        </Link>
      </div>
    </div>
  );
}
