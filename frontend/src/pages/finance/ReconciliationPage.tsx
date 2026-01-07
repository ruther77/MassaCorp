import { useState, useMemo } from 'react';
import {
  Link2,
  Link2Off,
  CheckCircle,
  AlertCircle,
  Search,
  ArrowRight,
  Building2,
  FileText,
  RefreshCw,
} from 'lucide-react';
import {
  useBankMovements,
  useBankAccounts,
  useInvoices,
  useReconcileBankMovement,
} from '../../hooks/useFinance';
import type { BankMovement, Invoice } from '../../types/finance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Select,
  Badge,
  Spinner,
  Modal,
  ModalFooter,
  EmptyState,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatDate, formatCurrency } from '../../lib/utils';

export default function ReconciliationPage() {
  const [selectedAccount, setSelectedAccount] = useState<number | undefined>();
  const [selectedMovement, setSelectedMovement] = useState<BankMovement | null>(null);
  const [isMatchModalOpen, setIsMatchModalOpen] = useState(false);

  const { data: bankAccounts } = useBankAccounts();
  const { data: movements, isLoading: loadingMovements, refetch } = useBankMovements(
    { compte_bancaire_id: selectedAccount, est_rapproche: false },
    1,
    100
  );
  const { data: invoices } = useInvoices({ statut: 'validee' }, 1, 100);
  const reconcile = useReconcileBankMovement();

  const accountOptions = bankAccounts?.map(account => ({
    value: account.compte_bancaire_id,
    label: `${account.libelle} (${account.banque_nom})`,
  })) || [];

  const stats = useMemo(() => {
    if (!movements?.items) return { total: 0, unreconciled: 0, percentage: 0 };
    const total = movements.total;
    const unreconciled = movements.items.filter(m => !m.est_rapproche).length;
    return {
      total,
      unreconciled,
      percentage: total > 0 ? Math.round(((total - unreconciled) / total) * 100) : 100,
    };
  }, [movements]);

  // Suggestions de rapprochement basees sur le montant
  const getSuggestions = (movement: BankMovement): Invoice[] => {
    if (!invoices?.items) return [];
    const amount = Math.abs(movement.montant);
    return invoices.items
      .filter(inv => {
        const diff = Math.abs(inv.montant_ttc - amount);
        return diff < amount * 0.01; // 1% de tolerance
      })
      .slice(0, 5);
  };

  const handleMatch = async (invoiceId: number) => {
    if (!selectedMovement) return;
    try {
      await reconcile.mutateAsync({
        movementId: selectedMovement.mouvement_id,
        paymentId: invoiceId,
      });
      setIsMatchModalOpen(false);
      setSelectedMovement(null);
      refetch();
    } catch (error) {
      console.error('Erreur rapprochement:', error);
    }
  };

  const openMatchModal = (movement: BankMovement) => {
    setSelectedMovement(movement);
    setIsMatchModalOpen(true);
  };

  if (loadingMovements) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rapprochement bancaire"
        subtitle="Associez vos mouvements bancaires aux factures"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Rapprochement' },
        ]}
        actions={
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Actualiser
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">A rapprocher</p>
                <p className="text-2xl font-bold text-yellow-400">{stats.unreconciled}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Taux de rapprochement</p>
                <p className="text-2xl font-bold text-green-400">{stats.percentage}%</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Total mouvements</p>
                <p className="text-2xl font-bold text-white">{stats.total}</p>
              </div>
              <Link2 className="w-8 h-8 text-primary-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filtre par compte */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center gap-4">
            <Building2 className="w-5 h-5 text-dark-400" />
            <div className="w-64">
              <Select
                options={[{ value: '', label: 'Tous les comptes' }, ...accountOptions]}
                value={selectedAccount?.toString() || ''}
                onChange={(e) => setSelectedAccount(e.target.value ? Number(e.target.value) : undefined)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liste des mouvements non rapproches */}
      <Card>
        <CardHeader>
          <CardTitle subtitle="Mouvements en attente de rapprochement">
            <Link2Off className="w-5 h-5 inline mr-2 text-yellow-500" />
            Mouvements a rapprocher
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!movements?.items?.length ? (
            <EmptyState
              icon={<CheckCircle className="w-12 h-12 text-green-500" />}
              title="Tout est rapproche !"
              description="Tous vos mouvements bancaires ont ete rapproches."
            />
          ) : (
            <div className="divide-y divide-dark-700">
              {movements.items.map((movement: BankMovement) => {
                const suggestions = getSuggestions(movement);
                return (
                  <div
                    key={movement.mouvement_id}
                    className="p-4 hover:bg-dark-700/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className={`font-medium ${
                            movement.type_mouvement === 'credit' ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {movement.type_mouvement === 'credit' ? '+' : '-'}
                            {formatCurrency(Math.abs(movement.montant))}
                          </span>
                          <Badge variant="default" size="sm">
                            {formatDate(movement.date_operation)}
                          </Badge>
                          <Badge variant="default" size="sm">
                            {movement.compte_bancaire_libelle}
                          </Badge>
                        </div>
                        <p className="text-sm text-white mb-1">{movement.libelle}</p>
                        {movement.reference && (
                          <p className="text-xs text-dark-400">Ref: {movement.reference}</p>
                        )}

                        {/* Suggestions */}
                        {suggestions.length > 0 && (
                          <div className="mt-3 p-3 bg-dark-700/50 rounded-lg">
                            <p className="text-xs text-dark-400 mb-2">
                              <Search className="w-3 h-3 inline mr-1" />
                              Factures correspondantes:
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {suggestions.map((inv) => (
                                <button
                                  key={inv.facture_id}
                                  className="inline-flex items-center px-2 py-1 text-xs font-medium rounded bg-dark-600 text-white cursor-pointer hover:bg-primary-600 transition-colors"
                                  onClick={() => handleMatch(inv.facture_id)}
                                >
                                  <FileText className="w-3 h-3 mr-1" />
                                  {inv.numero} - {formatCurrency(inv.montant_ttc)}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => openMatchModal(movement)}
                      >
                        <Link2 className="w-4 h-4 mr-2" />
                        Rapprocher
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal de rapprochement manuel */}
      <Modal
        isOpen={isMatchModalOpen}
        onClose={() => setIsMatchModalOpen(false)}
        title="Rapprocher le mouvement"
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => setIsMatchModalOpen(false)}
            cancelText="Annuler"
          />
        }
      >
        {selectedMovement && (
          <div className="space-y-4">
            {/* Mouvement selectionne */}
            <div className="p-4 bg-dark-700 rounded-lg">
              <p className="text-sm text-dark-400 mb-2">Mouvement bancaire</p>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-white">{selectedMovement.libelle}</p>
                  <p className="text-sm text-dark-400">
                    {formatDate(selectedMovement.date_operation)} - {selectedMovement.compte_bancaire_libelle}
                  </p>
                </div>
                <span className={`text-lg font-bold ${
                  selectedMovement.type_mouvement === 'credit' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {selectedMovement.type_mouvement === 'credit' ? '+' : '-'}
                  {formatCurrency(Math.abs(selectedMovement.montant))}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-center py-2">
              <ArrowRight className="w-6 h-6 text-dark-500" />
            </div>

            {/* Liste des factures */}
            <div>
              <p className="text-sm text-dark-400 mb-3">
                Selectionnez la facture correspondante
              </p>
              <div className="max-h-64 overflow-y-auto space-y-2">
                {invoices?.items?.map((invoice: Invoice) => (
                  <div
                    key={invoice.facture_id}
                    className="p-3 bg-dark-700/50 rounded-lg hover:bg-dark-600/50 cursor-pointer transition-colors"
                    onClick={() => handleMatch(invoice.facture_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-white">{invoice.numero}</p>
                        <p className="text-sm text-dark-400">
                          {invoice.fournisseur_nom || invoice.client_nom} - {formatDate(invoice.date_facture)}
                        </p>
                      </div>
                      <span className="font-medium text-white">
                        {formatCurrency(invoice.montant_ttc)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
