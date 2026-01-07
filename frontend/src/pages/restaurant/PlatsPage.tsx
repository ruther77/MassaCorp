import { useState } from 'react';
import {
  UtensilsCrossed,
  Plus,
  Edit2,
  Trash2,
  Search,
  Filter,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  ChefHat,
} from 'lucide-react';
import {
  usePlats,
  usePlat,
  useCreatePlat,
  useUpdatePlat,
  useDeletePlat,
  useIngredients,
  useSetPlatIngredients,
} from '../../hooks/useRestaurant';
import type { Plat, PlatCreate, PlatUpdate, PlatIngredientInput } from '../../types/restaurant';
import {
  RestaurantPlatCategory,
  PLAT_CATEGORY_LABELS,
  UNIT_LABELS,
} from '../../types/restaurant';
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
  Modal,
  ModalFooter,
  EmptyState,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency } from '../../lib/utils';

export default function PlatsPage() {
  const [selectedCategory, setSelectedCategory] = useState<RestaurantPlatCategory | undefined>();
  const [menusOnly, setMenusOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingPlat, setEditingPlat] = useState<Plat | null>(null);
  const [selectedPlatId, setSelectedPlatId] = useState<number | null>(null);
  const [isIngredientsModalOpen, setIsIngredientsModalOpen] = useState(false);
  const [platIngredients, setPlatIngredients] = useState<PlatIngredientInput[]>([]);

  const [formData, setFormData] = useState<PlatCreate>({
    name: '',
    prix_vente: 0,
    category: RestaurantPlatCategory.PLAT,
    description: '',
    is_menu: false,
  });

  const { data: plats, isLoading, refetch } = usePlats(selectedCategory, menusOnly);
  const { data: platDetail } = usePlat(selectedPlatId || 0);
  const { data: ingredients } = useIngredients();
  const createPlat = useCreatePlat();
  const updatePlat = useUpdatePlat();
  const deletePlat = useDeletePlat();
  const setIngredients = useSetPlatIngredients();

  const categoryOptions = [
    { value: '', label: 'Toutes les categories' },
    ...Object.entries(PLAT_CATEGORY_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  ];

  const filteredPlats = plats?.filter(plat =>
    plat.name.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const handleCreate = async () => {
    try {
      await createPlat.mutateAsync({
        ...formData,
        prix_vente: Math.round(formData.prix_vente * 100),
      });
      setIsCreateModalOpen(false);
      resetForm();
    } catch (error) {
      console.error('Erreur creation:', error);
    }
  };

  const handleUpdate = async () => {
    if (!editingPlat) return;
    try {
      const updateData: PlatUpdate = {
        name: formData.name,
        prix_vente: Math.round(formData.prix_vente * 100),
        category: formData.category,
        description: formData.description,
        is_menu: formData.is_menu,
      };
      await updatePlat.mutateAsync({ id: editingPlat.id, data: updateData });
      setEditingPlat(null);
      resetForm();
    } catch (error) {
      console.error('Erreur modification:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Desactiver ce plat ?')) return;
    try {
      await deletePlat.mutateAsync(id);
    } catch (error) {
      console.error('Erreur suppression:', error);
    }
  };

  const openEditModal = (plat: Plat) => {
    setEditingPlat(plat);
    setFormData({
      name: plat.name,
      prix_vente: plat.prix_vente / 100,
      category: plat.category,
      description: plat.description || '',
      is_menu: plat.is_menu,
    });
  };

  const openIngredientsModal = (platId: number) => {
    setSelectedPlatId(platId);
    setIsIngredientsModalOpen(true);
  };

  const handleSaveIngredients = async () => {
    if (!selectedPlatId) return;
    try {
      await setIngredients.mutateAsync({
        platId: selectedPlatId,
        ingredients: platIngredients,
      });
      setIsIngredientsModalOpen(false);
      setPlatIngredients([]);
      setSelectedPlatId(null);
    } catch (error) {
      console.error('Erreur sauvegarde ingredients:', error);
    }
  };

  const addIngredientRow = () => {
    setPlatIngredients([...platIngredients, { ingredient_id: 0, quantite: 1 }]);
  };

  const updateIngredientRow = (index: number, field: keyof PlatIngredientInput, value: number | string) => {
    const updated = [...platIngredients];
    updated[index] = { ...updated[index], [field]: value };
    setPlatIngredients(updated);
  };

  const removeIngredientRow = (index: number) => {
    setPlatIngredients(platIngredients.filter((_, i) => i !== index));
  };

  const resetForm = () => {
    setFormData({
      name: '',
      prix_vente: 0,
      category: RestaurantPlatCategory.PLAT,
      description: '',
      is_menu: false,
    });
  };

  // Load ingredients when opening modal
  if (isIngredientsModalOpen && platDetail && platIngredients.length === 0) {
    setPlatIngredients(
      platDetail.ingredients.map(ing => ({
        ingredient_id: ing.ingredient_id,
        quantite: ing.quantite,
        notes: ing.notes || undefined,
      }))
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des plats..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Menu & Plats"
        subtitle="Gestion des plats et menus"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Plats' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouveau plat
            </Button>
          </div>
        }
      />

      {/* Filtres */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-dark-400" />
              <Select
                options={categoryOptions}
                value={selectedCategory || ''}
                onChange={(e) => setSelectedCategory(e.target.value as RestaurantPlatCategory || undefined)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-dark-300">
              <input
                type="checkbox"
                checked={menusOnly}
                onChange={(e) => setMenusOnly(e.target.checked)}
                className="rounded border-dark-600"
              />
              Menus uniquement
            </label>
            <div className="flex-1 min-w-64">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <Input
                  placeholder="Rechercher un plat..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liste des plats */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${filteredPlats.length} plat(s)`}>
            <UtensilsCrossed className="w-5 h-5 inline mr-2" />
            Liste des plats
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredPlats.length === 0 ? (
            <EmptyState
              icon={<UtensilsCrossed className="w-12 h-12" />}
              title="Aucun plat"
              description="Commencez par ajouter vos premiers plats."
              action={{
                label: 'Ajouter un plat',
                onClick: () => setIsCreateModalOpen(true),
              }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-dark-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Nom</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Categorie</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Prix vente</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Cout</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Food Cost</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Rentable</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {filteredPlats.map((plat) => (
                    <tr key={plat.id} className="hover:bg-dark-700/30">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <UtensilsCrossed className="w-4 h-4 text-dark-400" />
                          <div>
                            <span className="font-medium text-white">{plat.name}</span>
                            {plat.is_menu && (
                              <Badge variant="info" size="sm" className="ml-2">Menu</Badge>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="default" size="sm">
                          {PLAT_CATEGORY_LABELS[plat.category]}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-right text-white font-medium">
                        {formatCurrency(plat.prix_vente / 100)}
                      </td>
                      <td className="px-4 py-3 text-right text-dark-300">
                        {formatCurrency(plat.cout_total / 100)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Badge
                          variant={parseFloat(String(plat.food_cost_ratio)) > 35 ? 'danger' : parseFloat(String(plat.food_cost_ratio)) > 30 ? 'warning' : 'success'}
                          size="sm"
                        >
                          {parseFloat(String(plat.food_cost_ratio)).toFixed(1)}%
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {plat.is_profitable ? (
                          <CheckCircle className="w-5 h-5 text-green-500 mx-auto" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 text-red-500 mx-auto" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openIngredientsModal(plat.id)}
                            title="Gerer les ingredients"
                          >
                            <ChefHat className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(plat)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => handleDelete(plat.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal creation/edition plat */}
      <Modal
        isOpen={isCreateModalOpen || !!editingPlat}
        onClose={() => {
          setIsCreateModalOpen(false);
          setEditingPlat(null);
          resetForm();
        }}
        title={editingPlat ? 'Modifier le plat' : 'Nouveau plat'}
        size="md"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsCreateModalOpen(false);
              setEditingPlat(null);
              resetForm();
            }}
            onConfirm={editingPlat ? handleUpdate : handleCreate}
            cancelText="Annuler"
            confirmText={editingPlat ? 'Modifier' : 'Creer'}
            loading={createPlat.isPending || updatePlat.isPending}
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom du plat"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Ex: Entrecote grillee"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Categorie"
              options={Object.entries(PLAT_CATEGORY_LABELS).map(([v, l]) => ({ value: v, label: l }))}
              value={formData.category || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value as RestaurantPlatCategory }))}
            />

            <Input
              type="number"
              label="Prix de vente (EUR)"
              value={formData.prix_vente || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, prix_vente: Number(e.target.value) }))}
              placeholder="0.00"
              step="0.01"
              required
            />
          </div>

          <Input
            label="Description"
            value={formData.description || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
            placeholder="Description du plat..."
          />

          <label className="flex items-center gap-2 text-sm text-dark-300">
            <input
              type="checkbox"
              checked={formData.is_menu}
              onChange={(e) => setFormData(prev => ({ ...prev, is_menu: e.target.checked }))}
              className="rounded border-dark-600"
            />
            C'est un menu compose
          </label>
        </div>
      </Modal>

      {/* Modal gestion ingredients */}
      <Modal
        isOpen={isIngredientsModalOpen}
        onClose={() => {
          setIsIngredientsModalOpen(false);
          setPlatIngredients([]);
          setSelectedPlatId(null);
        }}
        title="Composition du plat"
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsIngredientsModalOpen(false);
              setPlatIngredients([]);
              setSelectedPlatId(null);
            }}
            onConfirm={handleSaveIngredients}
            cancelText="Annuler"
            confirmText="Sauvegarder"
            loading={setIngredients.isPending}
          />
        }
      >
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-dark-400">
              Definissez les ingredients et quantites pour ce plat
            </p>
            <Button variant="secondary" size="sm" onClick={addIngredientRow}>
              <Plus className="w-4 h-4 mr-1" />
              Ajouter
            </Button>
          </div>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {platIngredients.map((ing, index) => (
              <div key={index} className="flex items-center gap-2 p-2 bg-dark-700/50 rounded">
                <Select
                  options={[
                    { value: '', label: 'Selectionnez...' },
                    ...(ingredients?.map(i => ({
                      value: i.id,
                      label: `${i.name} (${UNIT_LABELS[i.unit]})`,
                    })) || []),
                  ]}
                  value={ing.ingredient_id || ''}
                  onChange={(e) => updateIngredientRow(index, 'ingredient_id', Number(e.target.value))}
                  className="flex-1"
                />
                <Input
                  type="number"
                  value={ing.quantite}
                  onChange={(e) => updateIngredientRow(index, 'quantite', Number(e.target.value))}
                  className="w-24"
                  step="0.01"
                  min="0"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-400"
                  onClick={() => removeIngredientRow(index)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}

            {platIngredients.length === 0 && (
              <p className="text-center text-dark-500 py-4">
                Aucun ingredient. Cliquez sur "Ajouter" pour commencer.
              </p>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
