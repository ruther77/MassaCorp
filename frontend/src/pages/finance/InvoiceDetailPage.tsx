import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Edit,
  Trash2,
  Download,
  FileText,
  Calendar,
  CreditCard,
  CheckCircle,
  Clock,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react';
import { useInvoice, useDeleteInvoice, useUpdateInvoiceStatus } from '../../hooks/useFinance';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  Spinner,
  Table,
  DeleteConfirm,
  Alert,
  Avatar,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { useModal, useToast } from '../../hooks';
import { formatDate } from '../../lib/utils';
import type { InvoiceLine, InvoiceStatus } from '../../types/finance';

const statusConfig: Record<InvoiceStatus, { variant: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'; icon: React.ReactNode }> = {
  brouillon: { variant: 'default', icon: <FileText className="w-4 h-4" /> },
  validee: { variant: 'info', icon: <CheckCircle className="w-4 h-4" /> },
  envoyee: { variant: 'primary', icon: <ExternalLink className="w-4 h-4" /> },
  partiellement_payee: { variant: 'warning', icon: <Clock className="w-4 h-4" /> },
  payee: { variant: 'success', icon: <CheckCircle className="w-4 h-4" /> },
  en_litige: { variant: 'danger', icon: <AlertTriangle className="w-4 h-4" /> },
  annulee: { variant: 'default', icon: <Trash2 className="w-4 h-4" /> },
};

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const deleteModal = useModal();

  const { data: invoice, isLoading, error } = useInvoice(Number(id));
  const deleteMutation = useDeleteInvoice();
  const updateStatusMutation = useUpdateInvoiceStatus();

  const formatCurrency = (amount: number, currency = 'EUR') => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency,
    }).format(amount);
  };

  const handleDelete = async () => {
    if (!invoice) return;
    try {
      await deleteMutation.mutateAsync(invoice.facture_id);
      toast.success('Facture supprimee');
      navigate('/finance/factures');
    } catch {
      toast.error('Erreur lors de la suppression');
    }
  };

  const handleStatusChange = async (newStatus: InvoiceStatus) => {
    if (!invoice) return;
    try {
      await updateStatusMutation.mutateAsync({ id: invoice.facture_id, statut: newStatus });
      toast.success('Statut mis a jour');
    } catch {
      toast.error('Erreur lors de la mise a jour');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !invoice) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Facture introuvable"
          breadcrumbs={[
            { label: 'Finance', href: '/finance' },
            { label: 'Factures', href: '/finance/factures' },
            { label: 'Detail' },
          ]}
        />
        <Alert variant="error" title="Erreur">
          Cette facture n'existe pas ou a ete supprimee.
        </Alert>
        <Button variant="outline" leftIcon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate('/finance/factures')}>
          Retour aux factures
        </Button>
      </div>
    );
  }

  const isOverdue = new Date(invoice.date_echeance) < new Date() && invoice.solde_du > 0;
  const canEdit = !['payee', 'annulee'].includes(invoice.statut);
  const canDelete = invoice.statut !== 'payee';

  const lineColumns = [
    {
      key: 'description',
      header: 'Description',
      render: (line: InvoiceLine) => (
        <div>
          <p className="font-medium text-white">{line.designation}</p>
          {line.description && <p className="text-xs text-dark-400">{line.description}</p>}
        </div>
      ),
    },
    {
      key: 'quantite',
      header: 'Qte',
      align: 'right' as const,
      render: (line: InvoiceLine) => line.quantite,
    },
    {
      key: 'prix_unitaire',
      header: 'Prix unit. HT',
      align: 'right' as const,
      render: (line: InvoiceLine) => formatCurrency(line.prix_unitaire_ht),
    },
    {
      key: 'tva',
      header: 'TVA',
      align: 'right' as const,
      render: (line: InvoiceLine) => `${line.taux_tva}%`,
    },
    {
      key: 'total',
      header: 'Total TTC',
      align: 'right' as const,
      render: (line: InvoiceLine) => (
        <span className="font-medium text-white">{formatCurrency(line.montant_ttc)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Facture ${invoice.numero}`}
        subtitle={invoice.type_libelle}
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Factures', href: '/finance/factures' },
          { label: invoice.numero },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" leftIcon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate('/finance/factures')}>
              Retour
            </Button>
            {invoice.fichier_url && (
              <Button variant="outline" leftIcon={<Download className="w-4 h-4" />}>
                Telecharger
              </Button>
            )}
            {canEdit && (
              <Button variant="outline" leftIcon={<Edit className="w-4 h-4" />} onClick={() => navigate(`/finance/factures/${invoice.facture_id}/edit`)}>
                Modifier
              </Button>
            )}
            {canDelete && (
              <Button variant="danger" leftIcon={<Trash2 className="w-4 h-4" />} onClick={() => deleteModal.open()}>
                Supprimer
              </Button>
            )}
          </div>
        }
      />

      {isOverdue && (
        <Alert variant="warning" title="Facture en retard">
          Cette facture a depasse sa date d'echeance. Solde restant: {formatCurrency(invoice.solde_du)}
        </Alert>
      )}

      {/* Info principale */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Details */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Details de la facture</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge variant={statusConfig[invoice.statut]?.variant || 'default'}>
                  {statusConfig[invoice.statut]?.icon}
                  <span className="ml-1">{invoice.statut_libelle}</span>
                </Badge>
                <Badge variant="default">{invoice.type_libelle}</Badge>
              </div>
              {invoice.statut === 'brouillon' && (
                <Button size="sm" onClick={() => handleStatusChange('validee')}>
                  Valider la facture
                </Button>
              )}
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-dark-400 mb-1">Fournisseur / Client</p>
                  <div className="flex items-center gap-2">
                    <Avatar name={invoice.fournisseur_nom || invoice.client_nom || 'N/A'} size="sm" />
                    <span className="font-medium">{invoice.fournisseur_nom || invoice.client_nom || 'Non specifie'}</span>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-dark-400 mb-1">Reference externe</p>
                  <p className="font-medium">{invoice.reference_externe || '-'}</p>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-dark-400" />
                  <div>
                    <p className="text-sm text-dark-400">Date facture</p>
                    <p className="font-medium">{formatDate(invoice.date_facture)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-dark-400" />
                  <div>
                    <p className="text-sm text-dark-400">Echeance</p>
                    <p className={`font-medium ${isOverdue ? 'text-red-400' : ''}`}>
                      {formatDate(invoice.date_echeance)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {invoice.notes && (
              <div>
                <p className="text-sm text-dark-400 mb-1">Notes</p>
                <p className="text-dark-300 bg-dark-900 rounded-lg p-3">{invoice.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Montants */}
        <Card>
          <CardHeader>
            <CardTitle>Montants</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-dark-400">Total HT</span>
              <span>{formatCurrency(invoice.montant_ht)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-dark-400">TVA</span>
              <span>{formatCurrency(invoice.montant_tva)}</span>
            </div>
            <div className="flex justify-between border-t border-dark-700 pt-4">
              <span className="font-medium">Total TTC</span>
              <span className="text-xl font-bold text-primary-400">{formatCurrency(invoice.montant_ttc)}</span>
            </div>

            <div className="border-t border-dark-700 pt-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-dark-400">Deja paye</span>
                <span className="text-green-400">{formatCurrency(invoice.montant_paye)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-dark-400">Reste a payer</span>
                <span className={invoice.solde_du > 0 ? 'text-yellow-400 font-medium' : 'text-green-400'}>
                  {formatCurrency(invoice.solde_du)}
                </span>
              </div>
            </div>

            {invoice.mode_paiement_libelle && (
              <div className="flex items-center gap-2 pt-4 border-t border-dark-700">
                <CreditCard className="w-4 h-4 text-dark-400" />
                <span className="text-dark-400">Mode:</span>
                <span>{invoice.mode_paiement_libelle}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lignes de facture */}
      {invoice.lignes && invoice.lignes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Lignes de facture ({invoice.lignes.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <Table
              data={invoice.lignes}
              columns={lineColumns}
              keyExtractor={(line) => line.ligne_facture_id.toString()}
            />
          </CardContent>
        </Card>
      )}

      {/* Modal suppression */}
      <DeleteConfirm
        isOpen={deleteModal.isOpen}
        onClose={deleteModal.close}
        onConfirm={handleDelete}
        itemName={invoice.numero}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
