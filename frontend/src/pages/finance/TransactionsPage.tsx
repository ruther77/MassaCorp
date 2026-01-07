import { useState, useMemo } from 'react';
import {
  ArrowUpCircle,
  ArrowDownCircle,
  Search,
  Filter,
  Download,
  CheckCircle,
  XCircle,
  Calendar,
  Building2,
  RefreshCw,
} from 'lucide-react';
import { useBankMovements, useBankAccounts } from '../../hooks/useFinance';
import type { BankMovementFilters, BankMovement } from '../../types/finance';
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
  Pagination,
  EmptyState,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatDate, formatCurrency } from '../../lib/utils';

export default function TransactionsPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<BankMovementFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  const { data: bankMovements, isLoading, refetch } = useBankMovements(filters, page, 50);
  const { data: bankAccounts } = useBankAccounts();

  const stats = useMemo(() => {
    if (!bankMovements?.items) return { credits: 0, debits: 0, rapproches: 0 };
    return {
      credits: bankMovements.items.filter(m => m.type_mouvement === 'credit').length,
      debits: bankMovements.items.filter(m => m.type_mouvement === 'debit').length,
      rapproches: bankMovements.items.filter(m => m.est_rapproche).length,
    };
  }, [bankMovements]);

  const handleFilterChange = (key: keyof BankMovementFilters, value: string | number | boolean | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({});
    setPage(1);
  };

  const exportCSV = () => {
    if (!bankMovements?.items) return;
    const headers = ['Date', 'Compte', 'Libelle', 'Type', 'Montant', 'Rapproche', 'Categorie'];
    const rows = bankMovements.items.map(m => [
      formatDate(m.date_operation),
      m.compte_bancaire_libelle,
      m.libelle,
      m.type_mouvement,
      m.montant.toString(),
      m.est_rapproche ? 'Oui' : 'Non',
      m.categorie_depense_libelle || '',
    ]);
    const csv = [headers, ...rows].map(r => r.join(';')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const accountOptions = bankAccounts?.map(account => ({
    value: account.compte_bancaire_id,
    label: account.libelle,
  })) || [];

  const typeOptions = [
    { value: '', label: 'Tous les types' },
    { value: 'credit', label: 'Credit' },
    { value: 'debit', label: 'Debit' },
  ];

  const reconcileOptions = [
    { value: '', label: 'Tous' },
    { value: 'true', label: 'Rapproches' },
    { value: 'false', label: 'Non rapproches' },
  ];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des transactions..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Transactions bancaires"
        subtitle="Mouvements de vos comptes bancaires"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Transactions' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button variant="secondary" onClick={exportCSV}>
              <Download className="w-4 h-4 mr-2" />
              Exporter
            </Button>
          </div>
        }
      />

      {/* Stats rapides */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Total mouvements</p>
                <p className="text-2xl font-bold text-white">{bankMovements?.total || 0}</p>
              </div>
              <Calendar className="w-8 h-8 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Credits</p>
                <p className="text-2xl font-bold text-green-400">{stats.credits}</p>
              </div>
              <ArrowUpCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Debits</p>
                <p className="text-2xl font-bold text-red-400">{stats.debits}</p>
              </div>
              <ArrowDownCircle className="w-8 h-8 text-red-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Rapproches</p>
                <p className="text-2xl font-bold text-blue-400">{stats.rapproches}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filtres */}
      <Card>
        <CardHeader
          action={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4 mr-2" />
              {showFilters ? 'Masquer les filtres' : 'Afficher les filtres'}
            </Button>
          }
        >
          <CardTitle>Filtres</CardTitle>
        </CardHeader>

        {showFilters && (
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Select
                label="Compte bancaire"
                options={[{ value: '', label: 'Tous les comptes' }, ...accountOptions]}
                value={filters.compte_bancaire_id?.toString() || ''}
                onChange={(e) => handleFilterChange('compte_bancaire_id', e.target.value ? Number(e.target.value) : undefined)}
              />

              <Select
                label="Type"
                options={typeOptions}
                value={filters.type_mouvement || ''}
                onChange={(e) => handleFilterChange('type_mouvement', e.target.value || undefined)}
              />

              <Select
                label="Rapprochement"
                options={reconcileOptions}
                value={filters.est_rapproche === undefined ? '' : filters.est_rapproche.toString()}
                onChange={(e) => handleFilterChange('est_rapproche', e.target.value === '' ? undefined : e.target.value === 'true')}
              />

              <div className="flex items-end">
                <Button variant="secondary" onClick={clearFilters} className="w-full">
                  Effacer les filtres
                </Button>
              </div>

              <Input
                type="date"
                label="Date debut"
                value={filters.date_debut || ''}
                onChange={(e) => handleFilterChange('date_debut', e.target.value || undefined)}
              />

              <Input
                type="date"
                label="Date fin"
                value={filters.date_fin || ''}
                onChange={(e) => handleFilterChange('date_fin', e.target.value || undefined)}
              />

              <Input
                type="number"
                label="Montant min"
                value={filters.montant_min || ''}
                onChange={(e) => handleFilterChange('montant_min', e.target.value ? Number(e.target.value) : undefined)}
              />

              <Input
                type="number"
                label="Montant max"
                value={filters.montant_max || ''}
                onChange={(e) => handleFilterChange('montant_max', e.target.value ? Number(e.target.value) : undefined)}
              />
            </div>
          </CardContent>
        )}
      </Card>

      {/* Liste des transactions */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${bankMovements?.total || 0} mouvements`}>
            Liste des mouvements
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!bankMovements?.items?.length ? (
            <EmptyState
              icon={<Search className="w-12 h-12" />}
              title="Aucune transaction"
              description="Aucune transaction ne correspond a vos criteres de recherche."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-dark-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Compte</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Libelle</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Categorie</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Montant</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Statut</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {bankMovements.items.map((movement: BankMovement) => (
                    <tr key={movement.mouvement_id} className="hover:bg-dark-700/30">
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm text-white">{formatDate(movement.date_operation)}</p>
                          <p className="text-xs text-dark-400">Valeur: {formatDate(movement.date_valeur)}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Building2 className="w-4 h-4 text-dark-400" />
                          <span className="text-sm text-white">{movement.compte_bancaire_libelle}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-white max-w-xs truncate" title={movement.libelle}>
                          {movement.libelle}
                        </p>
                        {movement.reference && (
                          <p className="text-xs text-dark-400">Ref: {movement.reference}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {movement.categorie_depense_libelle ? (
                          <Badge variant="default" size="sm">
                            {movement.categorie_depense_libelle}
                          </Badge>
                        ) : (
                          <span className="text-xs text-dark-500">Non categorise</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`font-medium ${
                          movement.type_mouvement === 'credit' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {movement.type_mouvement === 'credit' ? '+' : '-'}
                          {formatCurrency(Math.abs(movement.montant))}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {movement.est_rapproche ? (
                          <Badge variant="success" size="sm">
                            <CheckCircle className="w-3 h-3 mr-1" />
                            Rapproche
                          </Badge>
                        ) : (
                          <Badge variant="warning" size="sm">
                            <XCircle className="w-3 h-3 mr-1" />
                            A rapprocher
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>

        {bankMovements && bankMovements.pages > 1 && (
          <div className="px-4 py-3 border-t border-dark-700">
            <Pagination
              page={page}
              totalPages={bankMovements.pages}
              onPageChange={setPage}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
