import { useState } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Building2,
  RefreshCw,
  Upload,
  Download
} from 'lucide-react';
import {
  useTreasurySummary,
  useTreasuryForecast,
  useBankAccounts,
  useBankMovements,
  useImportBankStatement
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
  Spinner,
  Modal,
  FileUpload,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { useModal, useToast } from '../../hooks';
import { formatDate } from '../../lib/utils';
import type { BankAccount, BankMovement } from '../../types/finance';

export default function TreasuryPage() {
  const toast = useToast();
  const [selectedAccount, setSelectedAccount] = useState<number | undefined>();
  const [forecastDays, setForecastDays] = useState(30);
  const importModal = useModal<BankAccount>();
  const [importFiles, setImportFiles] = useState<File[]>([]);

  // Queries
  const { data: summary, isLoading: loadingSummary } = useTreasurySummary();
  const { data: forecast } = useTreasuryForecast(forecastDays);
  const { data: accounts } = useBankAccounts();
  const { data: movements, isLoading: loadingMovements } = useBankMovements(
    selectedAccount ? { compte_bancaire_id: selectedAccount } : {},
    1,
    50
  );

  // Mutations
  const importMutation = useImportBankStatement();

  const formatCurrency = (amount: number, currency = 'EUR') => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency,
    }).format(amount);
  };

  const handleImport = async () => {
    if (!importModal.data || importFiles.length === 0) return;

    try {
      const result = await importMutation.mutateAsync({
        accountId: importModal.data.compte_bancaire_id,
        file: importFiles[0],
      });
      toast.success(`${result.imported} mouvements importés`);
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} erreurs lors de l'import`);
      }
      importModal.close();
      setImportFiles([]);
    } catch {
      toast.error("Erreur lors de l'import");
    }
  };

  const movementColumns = [
    {
      key: 'date_operation',
      header: 'Date',
      render: (m: BankMovement) => formatDate(m.date_operation),
    },
    {
      key: 'libelle',
      header: 'Libellé',
      render: (m: BankMovement) => (
        <div>
          <p className="text-white">{m.libelle}</p>
          {m.reference && <p className="text-xs text-dark-400">{m.reference}</p>}
        </div>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (m: BankMovement) => (
        m.type_mouvement === 'credit' ? (
          <Badge variant="success" dot>Crédit</Badge>
        ) : (
          <Badge variant="danger" dot>Débit</Badge>
        )
      ),
    },
    {
      key: 'montant',
      header: 'Montant',
      align: 'right' as const,
      render: (m: BankMovement) => (
        <span className={m.type_mouvement === 'credit' ? 'text-green-400' : 'text-red-400'}>
          {m.type_mouvement === 'credit' ? '+' : '-'}{formatCurrency(Math.abs(m.montant))}
        </span>
      ),
    },
    {
      key: 'solde',
      header: 'Solde',
      align: 'right' as const,
      render: (m: BankMovement) => formatCurrency(m.solde_apres_operation),
    },
    {
      key: 'rapproche',
      header: 'Rapproché',
      render: (m: BankMovement) => (
        m.est_rapproche ? (
          <Badge variant="success" size="sm">Oui</Badge>
        ) : (
          <Badge variant="default" size="sm">Non</Badge>
        )
      ),
    },
  ];

  if (loadingSummary) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Trésorerie"
        subtitle="Suivi de vos flux de trésorerie"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Trésorerie' },
        ]}
        actions={
          <Button variant="outline" leftIcon={<Download className="w-4 h-4" />}>
            Exporter
          </Button>
        }
      />

      {/* Résumé */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          title="Solde total"
          value={formatCurrency(summary?.solde_total || 0)}
          icon={<Wallet className="w-6 h-6" />}
        />
        <StatCard
          title="Variation jour"
          value={formatCurrency(summary?.variation_jour || 0)}
          icon={summary?.variation_jour && summary.variation_jour >= 0 ?
            <TrendingUp className="w-6 h-6" /> :
            <TrendingDown className="w-6 h-6" />
          }
          trend={summary?.variation_jour && summary.variation_jour >= 0 ? 'up' : 'down'}
        />
        <StatCard
          title="Variation semaine"
          value={formatCurrency(summary?.variation_semaine || 0)}
          trend={summary?.variation_semaine && summary.variation_semaine >= 0 ? 'up' : 'down'}
        />
        <StatCard
          title="Variation mois"
          value={formatCurrency(summary?.variation_mois || 0)}
          trend={summary?.variation_mois && summary.variation_mois >= 0 ? 'up' : 'down'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Comptes bancaires */}
        <Card>
          <CardHeader>
            <CardTitle>
              <Building2 className="w-5 h-5 inline mr-2" />
              Comptes bancaires
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {accounts?.map((account) => (
                <div
                  key={account.compte_bancaire_id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedAccount === account.compte_bancaire_id
                      ? 'border-primary-500 bg-primary-900/20'
                      : 'border-dark-700 hover:border-dark-600'
                  }`}
                  onClick={() => setSelectedAccount(account.compte_bancaire_id)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-white">{account.libelle}</p>
                      <p className="text-xs text-dark-400">{account.banque_nom}</p>
                      <p className="text-xs text-dark-500 font-mono">{account.iban}</p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-white">
                        {formatCurrency(account.solde_actuel || 0, account.devise_code)}
                      </p>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          importModal.open(account);
                        }}
                      >
                        <Upload className="w-3 h-3 mr-1" />
                        Import
                      </Button>
                    </div>
                  </div>
                </div>
              ))}

              {(!accounts || accounts.length === 0) && (
                <p className="text-dark-400 text-sm text-center py-4">
                  Aucun compte bancaire configuré
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Prévisions */}
        <Card className="lg:col-span-2">
          <CardHeader
            action={
              <Select
                options={[
                  { value: '7', label: '7 jours' },
                  { value: '14', label: '14 jours' },
                  { value: '30', label: '30 jours' },
                  { value: '60', label: '60 jours' },
                  { value: '90', label: '90 jours' },
                ]}
                value={String(forecastDays)}
                onChange={(e) => setForecastDays(Number(e.target.value))}
                className="w-32"
              />
            }
          >
            <CardTitle subtitle="Projection de trésorerie">
              Prévisions
            </CardTitle>
          </CardHeader>
          <CardContent>
            {forecast && forecast.length > 0 ? (
              <div className="space-y-4">
                {/* Graphique simplifié */}
                <div className="h-48 flex items-end gap-1 border-b border-dark-700 pb-2">
                  {forecast.slice(0, 14).map((day, i) => {
                    const minSolde = Math.min(...forecast.map(f => f.solde_prevu));
                    const maxSolde = Math.max(...forecast.map(f => f.solde_prevu));
                    const range = maxSolde - minSolde || 1;
                    const height = ((day.solde_prevu - minSolde) / range) * 100;

                    return (
                      <div
                        key={i}
                        className="flex-1 flex flex-col items-center"
                        title={`${formatDate(day.date)}: ${formatCurrency(day.solde_prevu)}`}
                      >
                        <div
                          className="w-full bg-primary-600/50 rounded-t transition-all hover:bg-primary-500"
                          style={{ height: `${Math.max(height, 5)}%` }}
                        />
                      </div>
                    );
                  })}
                </div>

                {/* Détails */}
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="p-3 bg-dark-700/50 rounded-lg">
                    <p className="text-sm text-dark-400">Encaissements prévus</p>
                    <p className="text-lg font-bold text-green-400">
                      {formatCurrency(forecast.reduce((sum, f) => sum + f.encaissements_prevus, 0))}
                    </p>
                  </div>
                  <div className="p-3 bg-dark-700/50 rounded-lg">
                    <p className="text-sm text-dark-400">Décaissements prévus</p>
                    <p className="text-lg font-bold text-red-400">
                      {formatCurrency(forecast.reduce((sum, f) => sum + f.decaissements_prevus, 0))}
                    </p>
                  </div>
                  <div className="p-3 bg-dark-700/50 rounded-lg">
                    <p className="text-sm text-dark-400">Solde fin de période</p>
                    <p className="text-lg font-bold text-white">
                      {formatCurrency(forecast[forecast.length - 1]?.solde_prevu || 0)}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-dark-400">
                Pas de prévisions disponibles
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Mouvements bancaires */}
      <Card>
        <CardHeader
          action={
            selectedAccount && (
              <Button variant="ghost" size="sm" leftIcon={<RefreshCw className="w-4 h-4" />}>
                Actualiser
              </Button>
            )
          }
        >
          <CardTitle subtitle={selectedAccount ? `Compte sélectionné` : 'Sélectionnez un compte'}>
            Mouvements bancaires
          </CardTitle>
        </CardHeader>
        <CardContent>
          {selectedAccount ? (
            <Table
              data={movements?.items || []}
              columns={movementColumns}
              keyExtractor={(m) => m.mouvement_id}
              loading={loadingMovements}
              emptyMessage="Aucun mouvement pour ce compte"
            />
          ) : (
            <Alert variant="info">
              Sélectionnez un compte bancaire pour voir les mouvements
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Modal d'import */}
      <Modal
        isOpen={importModal.isOpen}
        onClose={importModal.close}
        title="Importer un relevé bancaire"
        description={`Compte: ${importModal.data?.libelle}`}
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={importModal.close}>
              Annuler
            </Button>
            <Button
              onClick={handleImport}
              loading={importMutation.isPending}
              disabled={importFiles.length === 0}
            >
              Importer
            </Button>
          </>
        }
      >
        <FileUpload
          accept=".csv,.ofx,.qif"
          value={importFiles}
          onChange={setImportFiles}
          hint="Formats acceptés: CSV, OFX, QIF"
        />
      </Modal>
    </div>
  );
}
