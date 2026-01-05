import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm, useFieldArray } from 'react-hook-form';
import {
  ArrowLeft,
  Save,
  Plus,
  Trash2,
} from 'lucide-react';
import { useInvoice, useCreateInvoice, useUpdateInvoice, useSuppliers } from '../../hooks/useFinance';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
  Input,
  Textarea,
  Select,
  Spinner,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { useToast } from '../../hooks';
import type { InvoiceType } from '../../types/finance';

interface InvoiceLineForm {
  designation: string;
  description?: string;
  quantite: number;
  prix_unitaire_ht: number;
  taux_tva: number;
}

interface InvoiceFormData {
  numero: string;
  type: InvoiceType;
  fournisseur_id?: number;
  date_facture: string;
  date_echeance: string;
  reference_externe?: string;
  notes?: string;
  lignes: InvoiceLineForm[];
}

const typeOptions = [
  { value: 'achat', label: 'Facture d\'achat' },
  { value: 'vente', label: 'Facture de vente' },
  { value: 'avoir_achat', label: 'Avoir achat' },
  { value: 'avoir_vente', label: 'Avoir vente' },
];

const tvaOptions = [
  { value: '20', label: '20%' },
  { value: '10', label: '10%' },
  { value: '5.5', label: '5.5%' },
  { value: '2.1', label: '2.1%' },
  { value: '0', label: '0%' },
];

export default function InvoiceFormPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const isEdit = !!id;

  const { data: invoice, isLoading: loadingInvoice } = useInvoice(Number(id));
  const { data: suppliers } = useSuppliers();
  const createMutation = useCreateInvoice();
  const updateMutation = useUpdateInvoice();

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<InvoiceFormData>({
    defaultValues: {
      numero: '',
      type: 'achat',
      date_facture: new Date().toISOString().split('T')[0],
      date_echeance: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      lignes: [{ designation: '', quantite: 1, prix_unitaire_ht: 0, taux_tva: 20 }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'lignes',
  });

  const lignes = watch('lignes');

  // Load invoice data for edit mode
  useEffect(() => {
    if (isEdit && invoice) {
      setValue('numero', invoice.numero);
      setValue('type', invoice.type);
      setValue('fournisseur_id', invoice.fournisseur_id);
      setValue('date_facture', invoice.date_facture.split('T')[0]);
      setValue('date_echeance', invoice.date_echeance.split('T')[0]);
      setValue('reference_externe', invoice.reference_externe || '');
      setValue('notes', invoice.notes || '');
      if (invoice.lignes && invoice.lignes.length > 0) {
        setValue('lignes', invoice.lignes.map(l => ({
          designation: l.designation,
          description: l.description,
          quantite: l.quantite,
          prix_unitaire_ht: l.prix_unitaire_ht,
          taux_tva: l.taux_tva,
        })));
      }
    }
  }, [isEdit, invoice, setValue]);

  // Calculate totals
  const calculateTotals = () => {
    let totalHT = 0;
    let totalTVA = 0;

    lignes?.forEach(ligne => {
      const ht = (ligne.quantite || 0) * (ligne.prix_unitaire_ht || 0);
      const tva = ht * ((ligne.taux_tva || 0) / 100);
      totalHT += ht;
      totalTVA += tva;
    });

    return {
      totalHT,
      totalTVA,
      totalTTC: totalHT + totalTVA,
    };
  };

  const totals = calculateTotals();

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(amount);
  };

  const onSubmit = async (data: InvoiceFormData) => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const payload: any = {
        ...data,
        montant_ht: totals.totalHT,
        montant_tva: totals.totalTVA,
        montant_ttc: totals.totalTTC,
      };

      if (isEdit) {
        await updateMutation.mutateAsync({ id: Number(id), data: payload });
        toast.success('Facture mise a jour');
      } else {
        await createMutation.mutateAsync(payload);
        toast.success('Facture creee');
      }
      navigate('/finance/factures');
    } catch {
      toast.error(isEdit ? 'Erreur lors de la mise a jour' : 'Erreur lors de la creation');
    }
  };

  if (isEdit && loadingInvoice) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isEdit && !invoice) {
    return (
      <Alert variant="error" title="Facture introuvable">
        Cette facture n'existe pas.
      </Alert>
    );
  }

  const supplierOptions = suppliers?.map(s => ({
    value: s.fournisseur_id.toString(),
    label: s.raison_sociale,
  })) || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={isEdit ? `Modifier ${invoice?.numero}` : 'Nouvelle facture'}
        subtitle={isEdit ? 'Modifiez les informations de la facture' : 'Creez une nouvelle facture'}
        breadcrumbs={[
          { label: 'Finance', href: '/finance' },
          { label: 'Factures', href: '/finance/factures' },
          { label: isEdit ? 'Modifier' : 'Nouvelle' },
        ]}
        actions={
          <Button variant="outline" leftIcon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate('/finance/factures')}>
            Annuler
          </Button>
        }
      />

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Informations generales */}
        <Card>
          <CardHeader>
            <CardTitle>Informations generales</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="label">Numero de facture *</label>
                <Input
                  {...register('numero', { required: 'Numero requis' })}
                  placeholder="FAC-2024-001"
                  error={errors.numero?.message}
                />
              </div>

              <div>
                <label className="label">Type *</label>
                <Select
                  {...register('type', { required: 'Type requis' })}
                  options={typeOptions}
                />
              </div>

              <div>
                <label className="label">Fournisseur</label>
                <Select
                  {...register('fournisseur_id')}
                  options={[{ value: '', label: 'Selectionner...' }, ...supplierOptions]}
                />
              </div>

              <div>
                <label className="label">Date facture *</label>
                <Input
                  type="date"
                  {...register('date_facture', { required: 'Date requise' })}
                  error={errors.date_facture?.message}
                />
              </div>

              <div>
                <label className="label">Date echeance *</label>
                <Input
                  type="date"
                  {...register('date_echeance', { required: 'Echeance requise' })}
                  error={errors.date_echeance?.message}
                />
              </div>

              <div>
                <label className="label">Reference externe</label>
                <Input
                  {...register('reference_externe')}
                  placeholder="Ref. fournisseur..."
                />
              </div>

              <div className="md:col-span-2 lg:col-span-3">
                <label className="label">Notes</label>
                <Textarea
                  {...register('notes')}
                  placeholder="Notes internes..."
                  rows={3}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Lignes de facture */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Lignes de facture</CardTitle>
            <Button
              type="button"
              variant="outline"
              size="sm"
              leftIcon={<Plus className="w-4 h-4" />}
              onClick={() => append({ designation: '', quantite: 1, prix_unitaire_ht: 0, taux_tva: 20 })}
            >
              Ajouter une ligne
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Header */}
              <div className="hidden md:grid md:grid-cols-12 gap-4 text-sm font-medium text-dark-400 pb-2 border-b border-dark-700">
                <div className="col-span-4">Designation</div>
                <div className="col-span-2 text-right">Quantite</div>
                <div className="col-span-2 text-right">Prix unit. HT</div>
                <div className="col-span-2 text-right">TVA</div>
                <div className="col-span-1 text-right">Total HT</div>
                <div className="col-span-1"></div>
              </div>

              {/* Lines */}
              {fields.map((field, index) => {
                const lineHT = (lignes?.[index]?.quantite || 0) * (lignes?.[index]?.prix_unitaire_ht || 0);

                return (
                  <div key={field.id} className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start p-4 bg-dark-900 rounded-lg">
                    <div className="md:col-span-4">
                      <label className="label md:hidden">Designation</label>
                      <Input
                        {...register(`lignes.${index}.designation`, { required: true })}
                        placeholder="Description du produit/service"
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="label md:hidden">Quantite</label>
                      <Input
                        type="number"
                        step="0.01"
                        {...register(`lignes.${index}.quantite`, { valueAsNumber: true })}
                        className="text-right"
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="label md:hidden">Prix unit. HT</label>
                      <Input
                        type="number"
                        step="0.01"
                        {...register(`lignes.${index}.prix_unitaire_ht`, { valueAsNumber: true })}
                        className="text-right"
                      />
                    </div>

                    <div className="md:col-span-2">
                      <label className="label md:hidden">TVA</label>
                      <Select
                        {...register(`lignes.${index}.taux_tva`, { valueAsNumber: true })}
                        options={tvaOptions}
                      />
                    </div>

                    <div className="md:col-span-1 flex items-center justify-end">
                      <span className="text-sm font-medium">{formatCurrency(lineHT)}</span>
                    </div>

                    <div className="md:col-span-1 flex items-center justify-end">
                      {fields.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => remove(index)}
                        >
                          <Trash2 className="w-4 h-4 text-red-400" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>

          {/* Totaux */}
          <CardFooter className="border-t border-dark-700">
            <div className="ml-auto space-y-2 text-right">
              <div className="flex justify-between gap-8">
                <span className="text-dark-400">Total HT</span>
                <span className="font-medium">{formatCurrency(totals.totalHT)}</span>
              </div>
              <div className="flex justify-between gap-8">
                <span className="text-dark-400">Total TVA</span>
                <span className="font-medium">{formatCurrency(totals.totalTVA)}</span>
              </div>
              <div className="flex justify-between gap-8 pt-2 border-t border-dark-700">
                <span className="font-medium">Total TTC</span>
                <span className="text-xl font-bold text-primary-400">{formatCurrency(totals.totalTTC)}</span>
              </div>
            </div>
          </CardFooter>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-4">
          <Button type="button" variant="outline" onClick={() => navigate('/finance/factures')}>
            Annuler
          </Button>
          <Button type="submit" leftIcon={<Save className="w-4 h-4" />} loading={isSubmitting}>
            {isEdit ? 'Enregistrer les modifications' : 'Creer la facture'}
          </Button>
        </div>
      </form>
    </div>
  );
}
