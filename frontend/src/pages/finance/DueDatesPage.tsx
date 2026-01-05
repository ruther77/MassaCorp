import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar,
  AlertTriangle,
  Clock,
  Download
} from 'lucide-react';
import { useDueDates, useOverdueDueDates, useUpcomingDueDates } from '../../hooks/useFinance';
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
  Pagination,
  Tabs,
  TabList,
  TabTrigger,
  TabContent,
  Alert,
  Spinner,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { usePagination, useFilter } from '../../hooks';
import { formatDate } from '../../lib/utils';
import type { DueDate, DueDateFilters } from '../../types/finance';

export default function DueDatesPage() {
  const [activeTab, setActiveTab] = useState('all');
  const pagination = usePagination({ initialPerPage: 50 });
  const filters = useFilter<DueDateFilters>({
    initialFilters: {},
  });

  // Queries
  const { data: allDueDates, isLoading } = useDueDates(
    { ...filters.filters, en_retard: activeTab === 'overdue' ? true : undefined },
    pagination.page,
    pagination.perPage
  );
  const { data: overdueDueDates } = useOverdueDueDates();
  const { data: upcomingDueDates } = useUpcomingDueDates(7);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  // Update pagination total
  if (allDueDates?.total && allDueDates.total !== pagination.total) {
    pagination.setTotal(allDueDates.total);
  }

  // Stats
  const totalOverdue = overdueDueDates?.reduce((sum, d) => sum + d.montant_restant, 0) || 0;
  const totalUpcoming = upcomingDueDates?.reduce((sum, d) => sum + d.montant_restant, 0) || 0;

  const columns = [
    {
      key: 'facture',
      header: 'Facture',
      render: (d: DueDate) => (
        <Link
          to={`/finance/factures/${d.facture_id}`}
          className="text-primary-500 hover:text-primary-400"
        >
          {d.facture_numero}
        </Link>
      ),
    },
    {
      key: 'tiers',
      header: 'Tiers',
      render: (d: DueDate) => (
        <div>
          <p className="text-white">{d.fournisseur_nom || d.client_nom}</p>
          <Badge variant={d.type_document.includes('achat') ? 'info' : 'success'} size="sm">
            {d.type_document.includes('achat') ? 'Fournisseur' : 'Client'}
          </Badge>
        </div>
      ),
    },
    {
      key: 'date_facture',
      header: 'Date facture',
      render: (d: DueDate) => formatDate(d.date_facture),
    },
    {
      key: 'date_echeance',
      header: 'Échéance',
      render: (d: DueDate) => (
        <span className={d.est_en_retard ? 'text-red-400 font-medium' : ''}>
          {formatDate(d.date_echeance)}
        </span>
      ),
    },
    {
      key: 'montant_initial',
      header: 'Montant initial',
      align: 'right' as const,
      render: (d: DueDate) => formatCurrency(d.montant_initial),
    },
    {
      key: 'montant_restant',
      header: 'Restant dû',
      align: 'right' as const,
      render: (d: DueDate) => (
        <span className="font-medium text-white">
          {formatCurrency(d.montant_restant)}
        </span>
      ),
    },
    {
      key: 'retard',
      header: 'Retard',
      render: (d: DueDate) => (
        d.est_en_retard ? (
          <Badge variant="danger" dot>
            {d.jours_retard} jour{d.jours_retard > 1 ? 's' : ''}
          </Badge>
        ) : (
          <Badge variant="default">À jour</Badge>
        )
      ),
    },
    {
      key: 'statut',
      header: 'Statut',
      render: (d: DueDate) => (
        <Badge
          variant={
            d.statut_paiement === 'paye' ? 'success' :
            d.statut_paiement === 'partiellement_paye' ? 'warning' :
            'default'
          }
        >
          {d.statut_paiement === 'paye' ? 'Payé' :
           d.statut_paiement === 'partiellement_paye' ? 'Partiel' : 'Non payé'}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Échéancier"
        subtitle="Suivi des échéances fournisseurs et clients"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Échéancier' },
        ]}
        actions={
          <Button variant="outline" leftIcon={<Download className="w-4 h-4" />}>
            Exporter
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="En retard"
          value={overdueDueDates?.length || 0}
          icon={<AlertTriangle className="w-6 h-6" />}
          trend={overdueDueDates?.length && overdueDueDates.length > 0 ? 'down' : 'neutral'}
          className={overdueDueDates?.length && overdueDueDates.length > 0 ? 'border-red-500/50' : ''}
        />
        <StatCard
          title="Montant en retard"
          value={formatCurrency(totalOverdue)}
          className={totalOverdue > 0 ? 'border-red-500/50' : ''}
        />
        <StatCard
          title="À venir (7j)"
          value={upcomingDueDates?.length || 0}
          icon={<Clock className="w-6 h-6" />}
        />
        <StatCard
          title="Montant à venir"
          value={formatCurrency(totalUpcoming)}
        />
      </div>

      {/* Alerte retards */}
      {overdueDueDates && overdueDueDates.length > 0 && (
        <Alert
          variant="error"
          title={`${overdueDueDates.length} échéance(s) en retard`}
          icon={<AlertTriangle className="w-5 h-5" />}
        >
          Montant total: {formatCurrency(totalOverdue)}.
          Pensez à régulariser ces échéances au plus vite.
        </Alert>
      )}

      {/* Tabs et filtres */}
      <Card>
        <Tabs value={activeTab} onChange={setActiveTab}>
          <CardHeader>
            <TabList variant="underline">
              <TabTrigger value="all" variant="underline">
                Toutes
              </TabTrigger>
              <TabTrigger value="overdue" variant="underline">
                <AlertTriangle className="w-4 h-4 mr-1" />
                En retard ({overdueDueDates?.length || 0})
              </TabTrigger>
              <TabTrigger value="upcoming" variant="underline">
                <Clock className="w-4 h-4 mr-1" />
                À venir ({upcomingDueDates?.length || 0})
              </TabTrigger>
            </TabList>
          </CardHeader>

          <CardContent>
            {/* Filtres */}
            <div className="flex items-center gap-4 mb-4 pb-4 border-b border-dark-700">
              <Select
                options={[
                  { value: '', label: 'Tous les types' },
                  { value: 'fournisseur', label: 'Fournisseurs' },
                  { value: 'client', label: 'Clients' },
                ]}
                value={filters.filters.type || ''}
                onChange={(e) => filters.setFilter('type', e.target.value as 'fournisseur' | 'client' | undefined)}
                className="w-40"
              />
              {filters.hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={filters.clearFilters}>
                  Réinitialiser
                </Button>
              )}
            </div>

            <TabContent value="all">
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <Spinner size="lg" />
                </div>
              ) : (
                <>
                  <Table
                    data={allDueDates?.items || []}
                    columns={columns}
                    keyExtractor={(d) => d.echeance_id}
                    emptyMessage="Aucune échéance"
                  />
                  {allDueDates && allDueDates.pages > 1 && (
                    <Pagination
                      page={pagination.page}
                      totalPages={allDueDates.pages}
                      total={allDueDates.total}
                      perPage={pagination.perPage}
                      onPageChange={pagination.setPage}
                    />
                  )}
                </>
              )}
            </TabContent>

            <TabContent value="overdue">
              <Table
                data={overdueDueDates || []}
                columns={columns}
                keyExtractor={(d) => d.echeance_id}
                emptyMessage="Aucune échéance en retard"
              />
            </TabContent>

            <TabContent value="upcoming">
              <Table
                data={upcomingDueDates || []}
                columns={columns}
                keyExtractor={(d) => d.echeance_id}
                emptyMessage="Aucune échéance dans les 7 prochains jours"
              />
            </TabContent>
          </CardContent>
        </Tabs>
      </Card>

      {/* Calendrier simplifié des prochaines échéances */}
      <Card>
        <CardHeader>
          <CardTitle>
            <Calendar className="w-5 h-5 inline mr-2" />
            Calendrier des échéances
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-2">
            {/* Headers jours */}
            {['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map((day) => (
              <div key={day} className="text-center text-xs text-dark-400 font-medium py-2">
                {day}
              </div>
            ))}

            {/* Jours du mois en cours */}
            {Array.from({ length: 35 }, (_, i) => {
              const today = new Date();
              const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
              const startOffset = (firstDay.getDay() + 6) % 7;
              const dayNumber = i - startOffset + 1;
              const date = new Date(today.getFullYear(), today.getMonth(), dayNumber);
              const isCurrentMonth = date.getMonth() === today.getMonth();
              const isToday = date.toDateString() === today.toDateString();

              // Compter les échéances pour ce jour
              const dueDatesForDay = upcomingDueDates?.filter(d =>
                new Date(d.date_echeance).toDateString() === date.toDateString()
              ) || [];
              const overdueForDay = overdueDueDates?.filter(d =>
                new Date(d.date_echeance).toDateString() === date.toDateString()
              ) || [];

              return (
                <div
                  key={i}
                  className={`
                    aspect-square p-1 rounded-lg text-center relative
                    ${!isCurrentMonth ? 'opacity-30' : ''}
                    ${isToday ? 'bg-primary-900/50 border border-primary-500' : 'bg-dark-700/50'}
                  `}
                >
                  <span className={`text-sm ${isToday ? 'font-bold text-primary-400' : 'text-dark-300'}`}>
                    {dayNumber > 0 && dayNumber <= 31 ? dayNumber : ''}
                  </span>
                  {overdueForDay.length > 0 && (
                    <div className="absolute bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-red-500 rounded-full" />
                  )}
                  {dueDatesForDay.length > 0 && overdueForDay.length === 0 && (
                    <div className="absolute bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-yellow-500 rounded-full" />
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-center gap-6 mt-4 pt-4 border-t border-dark-700">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded-full" />
              <span className="text-sm text-dark-400">En retard</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full" />
              <span className="text-sm text-dark-400">À venir</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
