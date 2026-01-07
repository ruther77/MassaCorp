import { useState } from 'react';
import {
  ChefHat,
  Plus,
  Edit2,
  Trash2,
  Search,
  Filter,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import {
  useIngredients,
  useCreateIngredient,
  useUpdateIngredient,
  useDeleteIngredient,
} from '../../hooks/useRestaurant';
import type { Ingredient, IngredientCreate, IngredientUpdate } from '../../types/restaurant';
import {
  RestaurantUnit,
  RestaurantIngredientCategory,
  UNIT_LABELS,
  INGREDIENT_CATEGORY_LABELS,
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

export default function IngredientsPage() {
  const [selectedCategory, setSelectedCategory] = useState<RestaurantIngredientCategory | undefined>();
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingIngredient, setEditingIngredient] = useState<Ingredient | null>(null);
  const [formData, setFormData] = useState<IngredientCreate>({
    name: '',
    unit: RestaurantUnit.KILOGRAMME,
    category: RestaurantIngredientCategory.AUTRE,
    prix_unitaire: 0,
    seuil_alerte: undefined,
    notes: '',
  });

  const { data: ingredients, isLoading, refetch } = useIngredients(selectedCategory);
  const createIngredient = useCreateIngredient();
  const updateIngredient = useUpdateIngredient();
  const deleteIngredient = useDeleteIngredient();

  const categoryOptions = [
    { value: '', label: 'Toutes les categories' },
    ...Object.entries(INGREDIENT_CATEGORY_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  ];

  const unitOptions = Object.entries(UNIT_LABELS).map(([value, label]) => ({
    value,
    label,
  }));

  const filteredIngredients = ingredients?.filter(ing =>
    ing.name.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const handleCreate = async () => {
    try {
      await createIngredient.mutateAsync({
        ...formData,
        prix_unitaire: Math.round(formData.prix_unitaire! * 100), // Convert to centimes
      });
      setIsCreateModalOpen(false);
      resetForm();
    } catch (error) {
      console.error('Erreur creation:', error);
    }
  };

  const handleUpdate = async () => {
    if (!editingIngredient) return;
    try {
      const updateData: IngredientUpdate = {
        name: formData.name,
        unit: formData.unit,
        category: formData.category,
        prix_unitaire: Math.round(formData.prix_unitaire! * 100),
        seuil_alerte: formData.seuil_alerte,
        notes: formData.notes,
      };
      await updateIngredient.mutateAsync({ id: editingIngredient.id, data: updateData });
      setEditingIngredient(null);
      resetForm();
    } catch (error) {
      console.error('Erreur modification:', error);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Desactiver cet ingredient ?')) return;
    try {
      await deleteIngredient.mutateAsync(id);
    } catch (error) {
      console.error('Erreur suppression:', error);
    }
  };

  const openEditModal = (ingredient: Ingredient) => {
    setEditingIngredient(ingredient);
    setFormData({
      name: ingredient.name,
      unit: ingredient.unit,
      category: ingredient.category,
      prix_unitaire: ingredient.prix_unitaire / 100, // Convert from centimes
      seuil_alerte: ingredient.seuil_alerte || undefined,
      notes: ingredient.notes || '',
    });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      unit: RestaurantUnit.KILOGRAMME,
      category: RestaurantIngredientCategory.AUTRE,
      prix_unitaire: 0,
      seuil_alerte: undefined,
      notes: '',
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des ingredients..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Ingredients"
        subtitle="Gestion des ingredients de cuisine"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Ingredients' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Nouvel ingredient
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
                onChange={(e) => setSelectedCategory(e.target.value as RestaurantIngredientCategory || undefined)}
              />
            </div>
            <div className="flex-1 min-w-64">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <Input
                  placeholder="Rechercher un ingredient..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liste des ingredients */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${filteredIngredients.length} ingredient(s)`}>
            <ChefHat className="w-5 h-5 inline mr-2" />
            Liste des ingredients
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredIngredients.length === 0 ? (
            <EmptyState
              icon={<ChefHat className="w-12 h-12" />}
              title="Aucun ingredient"
              description="Commencez par ajouter vos premiers ingredients."
              action={{
                label: 'Ajouter un ingredient',
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
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Unite</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Prix unitaire</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Seuil alerte</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Statut</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {filteredIngredients.map((ingredient) => (
                    <tr key={ingredient.id} className="hover:bg-dark-700/30">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <ChefHat className="w-4 h-4 text-dark-400" />
                          <span className="font-medium text-white">{ingredient.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="default" size="sm">
                          {INGREDIENT_CATEGORY_LABELS[ingredient.category]}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-dark-300">
                        {UNIT_LABELS[ingredient.unit]}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {formatCurrency(ingredient.prix_unitaire / 100)}/{UNIT_LABELS[ingredient.unit]}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {ingredient.seuil_alerte ? (
                          <Badge variant="warning" size="sm">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            {ingredient.seuil_alerte}
                          </Badge>
                        ) : (
                          <span className="text-dark-500">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Badge variant={ingredient.is_active ? 'success' : 'default'} size="sm">
                          {ingredient.is_active ? 'Actif' : 'Inactif'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(ingredient)}
                          >
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400 hover:text-red-300"
                            onClick={() => handleDelete(ingredient.id)}
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

      {/* Modal creation/edition */}
      <Modal
        isOpen={isCreateModalOpen || !!editingIngredient}
        onClose={() => {
          setIsCreateModalOpen(false);
          setEditingIngredient(null);
          resetForm();
        }}
        title={editingIngredient ? 'Modifier l\'ingredient' : 'Nouvel ingredient'}
        size="md"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsCreateModalOpen(false);
              setEditingIngredient(null);
              resetForm();
            }}
            onConfirm={editingIngredient ? handleUpdate : handleCreate}
            cancelText="Annuler"
            confirmText={editingIngredient ? 'Modifier' : 'Creer'}
            loading={createIngredient.isPending || updateIngredient.isPending}
          />
        }
      >
        <div className="space-y-4">
          <Input
            label="Nom de l'ingredient"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="Ex: Tomates fraiches"
            required
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Categorie"
              options={Object.entries(INGREDIENT_CATEGORY_LABELS).map(([v, l]) => ({ value: v, label: l }))}
              value={formData.category || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value as RestaurantIngredientCategory }))}
            />

            <Select
              label="Unite"
              options={unitOptions}
              value={formData.unit}
              onChange={(e) => setFormData(prev => ({ ...prev, unit: e.target.value as RestaurantUnit }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Input
              type="number"
              label="Prix unitaire (EUR)"
              value={formData.prix_unitaire || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, prix_unitaire: Number(e.target.value) }))}
              placeholder="0.00"
              step="0.01"
            />

            <Input
              type="number"
              label="Seuil d'alerte stock"
              value={formData.seuil_alerte || ''}
              onChange={(e) => setFormData(prev => ({ ...prev, seuil_alerte: e.target.value ? Number(e.target.value) : undefined }))}
              placeholder="Ex: 5"
            />
          </div>

          <Input
            label="Notes"
            value={formData.notes || ''}
            onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Notes supplementaires..."
          />
        </div>
      </Modal>
    </div>
  );
}
