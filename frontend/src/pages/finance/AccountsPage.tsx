import { useState } from 'react';
import {
  Building2,
  Plus,
  Edit2,
  Trash2,
  CreditCard,
  Eye,
  EyeOff,
  TrendingUp,
  TrendingDown,
  RefreshCw,
} from 'lucide-react';
import { useBankAccounts, useCreateBankAccount } from '../../hooks/useFinance';
import type { BankAccount } from '../../types/finance';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Input,
  Badge,
  Spinner,
  Modal,
  ModalFooter,
  EmptyState,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency } from '../../lib/utils';

export default function AccountsPage() {
  const [showIban, setShowIban] = useState<Record<number, boolean>>({});
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    banque_nom: '',
    libelle: '',
    iban: '',
    bic: '',
    devise_code: 'EUR',
  });

  const { data: accounts, isLoading, refetch } = useBankAccounts();
  const createAccount = useCreateBankAccount();

  const toggleIban = (id: number) => {
    setShowIban(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const maskIban = (iban: string) => {
    if (!iban) return '';
    return iban.slice(0, 4) + ' **** **** ' + iban.slice(-4);
  };

  const formatIbanDisplay = (iban: string) => {
    if (!iban) return '';
    return iban.replace(/(.{4})/g, '$1 ').trim();
  };

  const getTotalBalance = () => {
    if (!accounts) return 0;
    return accounts.reduce((sum, acc) => sum + (acc.solde_actuel || 0), 0);
  };

  const handleCreateAccount = async () => {
    try {
      await createAccount.mutateAsync(formData);
      setIsCreateModalOpen(false);
      setFormData({
        banque_nom: '',
        libelle: '',
        iban: '',
        bic: '',
        devise_code: 'EUR',
      });
      refetch();
    } catch (error) {
      console.error('Erreur creation compte:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des comptes..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Comptes bancaires"
        subtitle="Gestion de vos comptes bancaires"
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Comptes' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouveau compte
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
                <p className="text-sm text-dark-400">Nombre de comptes</p>
                <p className="text-3xl font-bold text-white">{accounts?.length || 0}</p>
              </div>
              <Building2 className="w-10 h-10 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Solde total</p>
                <p className={`text-3xl font-bold ${getTotalBalance() >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {formatCurrency(getTotalBalance())}
                </p>
              </div>
              {getTotalBalance() >= 0 ? (
                <TrendingUp className="w-10 h-10 text-green-500" />
              ) : (
                <TrendingDown className="w-10 h-10 text-red-500" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Comptes actifs</p>
                <p className="text-3xl font-bold text-white">
                  {accounts?.filter(a => a.est_actif).length || 0}
                </p>
              </div>
              <CreditCard className="w-10 h-10 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Liste des comptes */}
      {!accounts?.length ? (
        <Card>
          <CardContent>
            <EmptyState
              icon={<Building2 className="w-12 h-12" />}
              title="Aucun compte bancaire"
              description="Commencez par ajouter votre premier compte bancaire."
              action={{
                label: 'Ajouter un compte',
                onClick: () => setIsCreateModalOpen(true),
              }}
            />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account: BankAccount) => (
            <Card key={account.compte_bancaire_id} hover>
              <CardHeader
                action={
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm">
                      <Edit2 className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                }
              >
                <CardTitle subtitle={account.banque_nom}>
                  <div className="flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-primary-500" />
                    {account.libelle}
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Solde */}
                  <div>
                    <p className="text-sm text-dark-400 mb-1">Solde actuel</p>
                    <p className={`text-2xl font-bold ${
                      (account.solde_actuel || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatCurrency(account.solde_actuel || 0)}
                    </p>
                  </div>

                  {/* IBAN */}
                  <div>
                    <p className="text-sm text-dark-400 mb-1">IBAN</p>
                    <div className="flex items-center gap-2">
                      <code className="text-sm text-white bg-dark-700 px-2 py-1 rounded font-mono">
                        {showIban[account.compte_bancaire_id]
                          ? formatIbanDisplay(account.iban)
                          : maskIban(account.iban)}
                      </code>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleIban(account.compte_bancaire_id)}
                      >
                        {showIban[account.compte_bancaire_id] ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* BIC */}
                  {account.bic && (
                    <div>
                      <p className="text-sm text-dark-400 mb-1">BIC</p>
                      <code className="text-sm text-white bg-dark-700 px-2 py-1 rounded font-mono">
                        {account.bic}
                      </code>
                    </div>
                  )}

                  {/* Statut et devise */}
                  <div className="flex items-center justify-between pt-2 border-t border-dark-700">
                    <Badge variant={account.est_actif ? 'success' : 'default'}>
                      {account.est_actif ? 'Actif' : 'Inactif'}
                    </Badge>
                    <Badge variant="default">
                      {account.devise_code}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modal creation compte */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Nouveau compte bancaire"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsCreateModalOpen(false)}
            onConfirm={handleCreateAccount}
            cancelText="Annuler"
            confirmText={createAccount.isPending ? 'Creation...' : 'Creer le compte'}
            loading={createAccount.isPending}
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom de la banque"
            value={formData.banque_nom}
            onChange={(e) => setFormData(prev => ({ ...prev, banque_nom: e.target.value }))}
            placeholder="Ex: BNP Paribas"
            required
          />
          <Input
            label="Libelle du compte"
            value={formData.libelle}
            onChange={(e) => setFormData(prev => ({ ...prev, libelle: e.target.value }))}
            placeholder="Ex: Compte courant principal"
            required
          />
          <Input
            label="IBAN"
            value={formData.iban}
            onChange={(e) => setFormData(prev => ({ ...prev, iban: e.target.value.replace(/\s/g, '').toUpperCase() }))}
            placeholder="FR76XXXXXXXXXXXXXXXXXXXXXXX"
            required
          />
          <Input
            label="BIC"
            value={formData.bic}
            onChange={(e) => setFormData(prev => ({ ...prev, bic: e.target.value.toUpperCase() }))}
            placeholder="BNPAFRPP"
          />
          <Input
            label="Devise"
            value={formData.devise_code}
            onChange={(e) => setFormData(prev => ({ ...prev, devise_code: e.target.value.toUpperCase() }))}
            placeholder="EUR"
          />
        </div>
      </Modal>
    </div>
  );
}
