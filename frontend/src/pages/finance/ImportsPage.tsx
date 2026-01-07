import { useState, useCallback } from 'react';
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Building2,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { useBankAccounts, useImportBankStatement } from '../../hooks/useFinance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Select,
  Badge,
  Modal,
  ModalFooter,
  EmptyState,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatDate } from '../../lib/utils';

// Type pour l'historique des imports
interface ImportHistory {
  id: number;
  account_id: number;
  account_name: string;
  filename: string;
  imported_at: string;
  status: 'success' | 'partial' | 'error';
  lines_imported: number;
  lines_error: number;
  errors: string[];
}

// Donnees mockees
const mockHistory: ImportHistory[] = [
  {
    id: 1,
    account_id: 1,
    account_name: 'Compte courant BNP',
    filename: 'releve_janvier_2025.csv',
    imported_at: '2025-01-05T10:30:00',
    status: 'success',
    lines_imported: 45,
    lines_error: 0,
    errors: [],
  },
  {
    id: 2,
    account_id: 1,
    account_name: 'Compte courant BNP',
    filename: 'releve_decembre_2024.csv',
    imported_at: '2025-01-02T14:15:00',
    status: 'partial',
    lines_imported: 38,
    lines_error: 2,
    errors: ['Ligne 15: Format de date invalide', 'Ligne 28: Montant manquant'],
  },
  {
    id: 3,
    account_id: 2,
    account_name: 'Compte epargne',
    filename: 'releve_q4_2024.xlsx',
    imported_at: '2025-01-01T09:00:00',
    status: 'error',
    lines_imported: 0,
    lines_error: 1,
    errors: ['Format de fichier non supporte'],
  },
];

export default function ImportsPage() {
  const [selectedAccount, setSelectedAccount] = useState<number | undefined>();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [history] = useState<ImportHistory[]>(mockHistory);
  const [selectedImport, setSelectedImport] = useState<ImportHistory | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

  const { data: bankAccounts } = useBankAccounts();
  const importStatement = useImportBankStatement();

  const accountOptions = bankAccounts?.map(account => ({
    value: account.compte_bancaire_id,
    label: `${account.libelle} (${account.banque_nom})`,
  })) || [];

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setSelectedFile(files[0]);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    }
  };

  const handleImport = async () => {
    if (!selectedAccount || !selectedFile) return;
    try {
      await importStatement.mutateAsync({
        accountId: selectedAccount,
        file: selectedFile,
      });
      setSelectedFile(null);
    } catch (error) {
      console.error('Erreur import:', error);
    }
  };

  const getStatusBadge = (status: ImportHistory['status']) => {
    switch (status) {
      case 'success':
        return <Badge variant="success" size="sm"><CheckCircle className="w-3 h-3 mr-1" />Succes</Badge>;
      case 'partial':
        return <Badge variant="warning" size="sm"><AlertCircle className="w-3 h-3 mr-1" />Partiel</Badge>;
      case 'error':
        return <Badge variant="danger" size="sm"><XCircle className="w-3 h-3 mr-1" />Erreur</Badge>;
    }
  };

  const openDetails = (item: ImportHistory) => {
    setSelectedImport(item);
    setIsDetailsModalOpen(true);
  };

  const stats = {
    total: history.length,
    success: history.filter(h => h.status === 'success').length,
    partial: history.filter(h => h.status === 'partial').length,
    error: history.filter(h => h.status === 'error').length,
    totalLines: history.reduce((sum, h) => sum + h.lines_imported, 0),
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Import de releves"
        subtitle="Importez vos releves bancaires"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Imports' },
        ]}
      />

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Imports totaux</p>
                <p className="text-2xl font-bold text-white">{stats.total}</p>
              </div>
              <FileText className="w-8 h-8 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Reussis</p>
                <p className="text-2xl font-bold text-green-400">{stats.success}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Partiels</p>
                <p className="text-2xl font-bold text-yellow-400">{stats.partial}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-yellow-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Lignes importees</p>
                <p className="text-2xl font-bold text-white">{stats.totalLines}</p>
              </div>
              <Upload className="w-8 h-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Zone d'import */}
      <Card>
        <CardHeader>
          <CardTitle subtitle="Formats supportes: CSV, OFX, QIF">
            <Upload className="w-5 h-5 inline mr-2" />
            Importer un releve
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Selection du compte */}
            <Select
              label="Compte bancaire cible"
              options={[{ value: '', label: 'Selectionnez un compte' }, ...accountOptions]}
              value={selectedAccount?.toString() || ''}
              onChange={(e) => setSelectedAccount(e.target.value ? Number(e.target.value) : undefined)}
            />

            {/* Zone de drop */}
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging
                  ? 'border-primary-500 bg-primary-500/10'
                  : 'border-dark-600 hover:border-dark-500'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {selectedFile ? (
                <div className="flex items-center justify-center gap-4">
                  <FileText className="w-10 h-10 text-primary-500" />
                  <div className="text-left">
                    <p className="font-medium text-white">{selectedFile.name}</p>
                    <p className="text-sm text-dark-400">
                      {(selectedFile.size / 1024).toFixed(2)} Ko
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400"
                    onClick={() => setSelectedFile(null)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <>
                  <Upload className="w-12 h-12 mx-auto text-dark-400 mb-4" />
                  <p className="text-dark-300 mb-2">
                    Glissez-deposez votre fichier ici
                  </p>
                  <p className="text-sm text-dark-500 mb-4">ou</p>
                  <label className="cursor-pointer inline-block">
                    <input
                      type="file"
                      className="hidden"
                      accept=".csv,.ofx,.qif,.xlsx"
                      onChange={handleFileSelect}
                    />
                    <span className="inline-flex items-center justify-center px-4 py-2 bg-dark-600 hover:bg-dark-500 text-white rounded-lg transition-colors">
                      Parcourir
                    </span>
                  </label>
                </>
              )}
            </div>

            {/* Bouton import */}
            <div className="flex justify-end">
              <Button
                onClick={handleImport}
                disabled={!selectedAccount || !selectedFile || importStatement.isPending}
              >
                {importStatement.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Import en cours...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Importer le releve
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Historique des imports */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${history.length} import(s)`}>
            <Clock className="w-5 h-5 inline mr-2" />
            Historique des imports
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {history.length === 0 ? (
            <EmptyState
              icon={<Upload className="w-12 h-12" />}
              title="Aucun import"
              description="Vous n'avez pas encore importe de releve bancaire."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-dark-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Compte</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Fichier</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Lignes</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Statut</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {history.map((item) => (
                    <tr key={item.id} className="hover:bg-dark-700/30">
                      <td className="px-4 py-3">
                        <p className="text-sm text-white">{formatDate(item.imported_at)}</p>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Building2 className="w-4 h-4 text-dark-400" />
                          <span className="text-sm text-white">{item.account_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-dark-400" />
                          <span className="text-sm text-white">{item.filename}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-sm text-white">{item.lines_imported}</span>
                        {item.lines_error > 0 && (
                          <span className="text-sm text-red-400 ml-1">
                            ({item.lines_error} erreurs)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {getStatusBadge(item.status)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openDetails(item)}
                        >
                          Details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal details */}
      <Modal
        isOpen={isDetailsModalOpen}
        onClose={() => setIsDetailsModalOpen(false)}
        title="Details de l'import"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsDetailsModalOpen(false)}
            cancelText="Fermer"
          />
        }
      >
        {selectedImport && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-dark-400">Fichier</p>
                <p className="text-white">{selectedImport.filename}</p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Date</p>
                <p className="text-white">{formatDate(selectedImport.imported_at)}</p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Compte</p>
                <p className="text-white">{selectedImport.account_name}</p>
              </div>
              <div>
                <p className="text-sm text-dark-400">Statut</p>
                {getStatusBadge(selectedImport.status)}
              </div>
            </div>

            <div className="p-4 bg-dark-700 rounded-lg">
              <div className="flex justify-between mb-2">
                <span className="text-dark-400">Lignes importees</span>
                <span className="text-green-400 font-medium">{selectedImport.lines_imported}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">Lignes en erreur</span>
                <span className="text-red-400 font-medium">{selectedImport.lines_error}</span>
              </div>
            </div>

            {selectedImport.errors.length > 0 && (
              <div>
                <p className="text-sm text-dark-400 mb-2">Erreurs:</p>
                <div className="space-y-2">
                  {selectedImport.errors.map((error, i) => (
                    <Alert key={i} variant="error">
                      {error}
                    </Alert>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
