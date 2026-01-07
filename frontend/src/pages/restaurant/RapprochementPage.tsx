import { useState, useMemo } from 'react';
import { useDebounce } from '../../hooks/useDebounce';
import {
  Link2,
  Plus,
  Trash2,
  Search,
  RefreshCw,
  ChefHat,
  Package,
  ArrowRight,
  Check,
  Star,
  AlertCircle,
  Filter,
  X,
  Truck,
  Leaf,
  Globe,
  Pencil,
} from 'lucide-react';
import {
  useIngredientsWithLinks,
  useSearchEpicerieProducts,
  useCreateEpicerieLink,
  useUpdateEpicerieLink,
  useDeleteEpicerieLink,
  useSyncPricesFromEpicerie,
} from '../../hooks/useRestaurant';
import type {
  IngredientWithLinks,
  EpicerieLink,
  EpicerieProduit,
  EpicerieLinkCreate,
  FournisseurType,
  RestaurantIngredientCategory,
} from '../../types/restaurant';
import { UNIT_LABELS, INGREDIENT_CATEGORY_LABELS } from '../../types/restaurant';
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
  Select,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency, cn } from '../../lib/utils';

// Configuration fournisseurs
const FOURNISSEUR_CONFIG: Record<FournisseurType, { label: string; color: string; bgColor: string; icon: React.ComponentType<{ className?: string }> }> = {
  METRO: { label: 'METRO', color: 'text-blue-400', bgColor: 'bg-blue-500/20', icon: Truck },
  TAIYAT: { label: 'TAI YAT', color: 'text-green-400', bgColor: 'bg-green-500/20', icon: Leaf },
  EUROCIEL: { label: 'EUROCIEL', color: 'text-purple-400', bgColor: 'bg-purple-500/20', icon: Globe },
  OTHER: { label: 'Autre', color: 'text-gray-400', bgColor: 'bg-gray-500/20', icon: Package },
};

export default function RapprochementPage() {
  const [searchIngredient, setSearchIngredient] = useState('');
  const [searchProduct, setSearchProduct] = useState('');
  const [selectedIngredient, setSelectedIngredient] = useState<IngredientWithLinks | null>(null);
  const [isLinkModalOpen, setIsLinkModalOpen] = useState(false);
  const [linkFormData, setLinkFormData] = useState<{ produit?: EpicerieProduit; ratio: number }>({
    ratio: 1,
  });
  const [syncResult, setSyncResult] = useState<{
    show: boolean;
    updated: number;
    skipped: number;
    errors: number;
  } | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<'all' | 'linked' | 'unlinked'>('all');
  const [fournisseurFilter, setFournisseurFilter] = useState<string>('all');
  const [editingLink, setEditingLink] = useState<EpicerieLink | null>(null);
  const [editFormData, setEditFormData] = useState<{ ratio: number }>({ ratio: 1 });

  // Debounce de la recherche pour eviter trop de requetes
  const debouncedSearchProduct = useDebounce(searchProduct, 300);

  const { data: ingredientsWithLinks, isLoading, refetch } = useIngredientsWithLinks();
  const { data: searchResults, isLoading: isSearching } = useSearchEpicerieProducts(
    debouncedSearchProduct,
    100, // Plus de resultats pour une meilleure recherche
    fournisseurFilter === 'all' ? undefined : fournisseurFilter
  );
  const createLink = useCreateEpicerieLink();
  const updateLink = useUpdateEpicerieLink();
  const deleteLink = useDeleteEpicerieLink();
  const syncPrices = useSyncPricesFromEpicerie();

  // Categories disponibles
  const categories = useMemo(() => {
    if (!ingredientsWithLinks) return [];
    const cats = new Set(ingredientsWithLinks.map(ing => ing.category));
    return Array.from(cats);
  }, [ingredientsWithLinks]);

  // Filtrage des ingredients
  const filteredIngredients = useMemo(() => {
    if (!ingredientsWithLinks) return [];
    return ingredientsWithLinks.filter(ing => {
      // Filtre recherche
      if (searchIngredient && !ing.name.toLowerCase().includes(searchIngredient.toLowerCase())) {
        return false;
      }
      // Filtre categorie
      if (filterCategory !== 'all' && ing.category !== filterCategory) {
        return false;
      }
      // Filtre statut
      if (filterStatus === 'linked' && ing.epicerie_links.length === 0) {
        return false;
      }
      if (filterStatus === 'unlinked' && ing.epicerie_links.length > 0) {
        return false;
      }
      return true;
    });
  }, [ingredientsWithLinks, searchIngredient, filterCategory, filterStatus]);

  // Stats
  const stats = useMemo(() => {
    if (!ingredientsWithLinks) return { total: 0, linked: 0, unlinked: 0, percentage: 0 };
    const total = ingredientsWithLinks.length;
    const linked = ingredientsWithLinks.filter(ing => ing.epicerie_links.length > 0).length;
    return {
      total,
      linked,
      unlinked: total - linked,
      percentage: total > 0 ? Math.round((linked / total) * 100) : 0,
    };
  }, [ingredientsWithLinks]);

  const handleOpenLinkModal = (ingredient: IngredientWithLinks) => {
    setSelectedIngredient(ingredient);
    setSearchProduct('');
    setLinkFormData({ ratio: 1 });
    setFournisseurFilter('all');
    setIsLinkModalOpen(true);
  };

  const handleCreateLink = async () => {
    if (!selectedIngredient || !linkFormData.produit) return;

    try {
      const data: EpicerieLinkCreate = {
        ingredient_id: selectedIngredient.id,
        produit_id: linkFormData.produit.id,
        fournisseur: linkFormData.produit.fournisseur,
        ratio: linkFormData.ratio,
        is_primary: selectedIngredient.epicerie_links.length === 0,
      };
      await createLink.mutateAsync(data);
      setIsLinkModalOpen(false);
      setLinkFormData({ ratio: 1 });
      setSearchProduct('');
    } catch (error) {
      console.error('Erreur creation lien:', error);
    }
  };

  const handleSetPrimary = async (link: EpicerieLink) => {
    try {
      await updateLink.mutateAsync({
        linkId: link.id,
        data: { is_primary: true },
      });
    } catch (error) {
      console.error('Erreur mise a jour:', error);
    }
  };

  const handleOpenEditModal = (link: EpicerieLink) => {
    setEditingLink(link);
    setEditFormData({ ratio: link.ratio });
  };

  const handleUpdateLink = async () => {
    if (!editingLink) return;
    try {
      await updateLink.mutateAsync({
        linkId: editingLink.id,
        data: { ratio: editFormData.ratio },
      });
      setEditingLink(null);
    } catch (error) {
      console.error('Erreur mise a jour:', error);
    }
  };

  const handleDeleteLink = async (link: EpicerieLink) => {
    if (!confirm('Supprimer ce lien ?')) return;
    try {
      await deleteLink.mutateAsync(link.id);
    } catch (error) {
      console.error('Erreur suppression:', error);
    }
  };

  const handleSyncPrices = async () => {
    try {
      const result = await syncPrices.mutateAsync({});
      setSyncResult({
        show: true,
        updated: result.updated,
        skipped: result.skipped,
        errors: result.errors.length,
      });
      setTimeout(() => setSyncResult(null), 5000);
    } catch (error) {
      console.error('Erreur synchronisation:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des donnees..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rapprochement Produits"
        subtitle="Lier les ingredients restaurant aux produits fournisseurs"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Rapprochement' },
        ]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Actualiser
            </Button>
            <Button
              onClick={handleSyncPrices}
              disabled={syncPrices.isPending}
            >
              {syncPrices.isPending ? (
                <Spinner size="sm" className="mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 mr-2" />
              )}
              Synchroniser les prix
            </Button>
          </div>
        }
      />

      {/* Notification sync */}
      {syncResult?.show && (
        <Card className="bg-green-500/20 border-green-500">
          <CardContent className="py-3">
            <div className="flex items-center gap-3">
              <Check className="w-5 h-5 text-green-400" />
              <span className="text-white">
                Synchronisation terminee: {syncResult.updated} mis a jour, {syncResult.skipped} ignores
                {syncResult.errors > 0 && `, ${syncResult.errors} erreurs`}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats avec jauge de progression */}
      <Card className="overflow-hidden">
        <CardContent className="py-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-8">
              <div>
                <p className="text-dark-400 text-sm mb-1">Progression du rapprochement</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold text-white">{stats.percentage}%</span>
                  <span className="text-dark-400">({stats.linked}/{stats.total} ingredients lies)</span>
                </div>
              </div>
            </div>
            <div className="flex gap-6">
              <div className="text-center">
                <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-green-500/20 mb-2 mx-auto">
                  <Link2 className="w-6 h-6 text-green-400" />
                </div>
                <p className="text-2xl font-bold text-green-400">{stats.linked}</p>
                <p className="text-xs text-dark-400">Lies</p>
              </div>
              <div className="text-center">
                <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-orange-500/20 mb-2 mx-auto">
                  <AlertCircle className="w-6 h-6 text-orange-400" />
                </div>
                <p className="text-2xl font-bold text-orange-400">{stats.unlinked}</p>
                <p className="text-xs text-dark-400">Non lies</p>
              </div>
            </div>
          </div>
          {/* Barre de progression */}
          <div className="h-3 bg-dark-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-500"
              style={{ width: `${stats.percentage}%` }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Filtres */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                <Input
                  placeholder="Rechercher un ingredient..."
                  value={searchIngredient}
                  onChange={(e) => setSearchIngredient(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-dark-400" />
              <Select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="min-w-[160px]"
                options={[
                  { value: 'all', label: 'Toutes categories' },
                  ...categories.map(cat => ({
                    value: cat,
                    label: INGREDIENT_CATEGORY_LABELS[cat as RestaurantIngredientCategory] || cat
                  }))
                ]}
              />
            </div>
            <div className="flex rounded-lg border border-dark-600 overflow-hidden">
              <button
                onClick={() => setFilterStatus('all')}
                className={cn(
                  'px-3 py-1.5 text-sm transition-colors',
                  filterStatus === 'all' ? 'bg-primary-600 text-white' : 'text-dark-400 hover:text-white hover:bg-dark-700'
                )}
              >
                Tous
              </button>
              <button
                onClick={() => setFilterStatus('linked')}
                className={cn(
                  'px-3 py-1.5 text-sm transition-colors border-l border-dark-600',
                  filterStatus === 'linked' ? 'bg-green-600 text-white' : 'text-dark-400 hover:text-white hover:bg-dark-700'
                )}
              >
                Lies
              </button>
              <button
                onClick={() => setFilterStatus('unlinked')}
                className={cn(
                  'px-3 py-1.5 text-sm transition-colors border-l border-dark-600',
                  filterStatus === 'unlinked' ? 'bg-orange-600 text-white' : 'text-dark-400 hover:text-white hover:bg-dark-700'
                )}
              >
                Non lies
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Liste des ingredients */}
      <Card>
        <CardHeader className="border-b border-dark-700">
          <CardTitle subtitle={`${filteredIngredients.length} ingredient(s) affiches`}>
            <ChefHat className="w-5 h-5 inline mr-2" />
            Ingredients
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredIngredients.length === 0 ? (
            <EmptyState
              icon={<ChefHat className="w-12 h-12" />}
              title="Aucun ingredient"
              description="Aucun ingredient ne correspond a vos filtres."
            />
          ) : (
            <div className="divide-y divide-dark-700">
              {filteredIngredients.map((ingredient) => {
                const hasLinks = ingredient.epicerie_links.length > 0;
                return (
                  <div
                    key={ingredient.id}
                    className={cn(
                      'p-4 transition-colors',
                      !hasLinks ? 'bg-orange-500/5' : 'hover:bg-dark-700/30'
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 flex-1">
                        <div className={cn(
                          'p-2.5 rounded-xl',
                          hasLinks ? 'bg-green-500/20' : 'bg-orange-500/20'
                        )}>
                          <ChefHat className={cn(
                            'w-5 h-5',
                            hasLinks ? 'text-green-400' : 'text-orange-400'
                          )} />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-1">
                            <h4 className="font-medium text-white">{ingredient.name}</h4>
                            {hasLinks ? (
                              <Badge variant="success" size="sm">
                                <Link2 className="w-3 h-3 mr-1" />
                                {ingredient.epicerie_links.length} lien(s)
                              </Badge>
                            ) : (
                              <Badge variant="warning" size="sm">
                                Non lie
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-sm text-dark-400">
                            <Badge variant="default" size="sm">
                              {INGREDIENT_CATEGORY_LABELS[ingredient.category]}
                            </Badge>
                            <span>{UNIT_LABELS[ingredient.unit]}</span>
                            <span className="text-dark-500">|</span>
                            <span className="font-medium text-white">
                              {formatCurrency(ingredient.prix_unitaire / 100)}/{UNIT_LABELS[ingredient.unit]}
                            </span>
                          </div>

                          {/* Liens existants */}
                          {hasLinks && (
                            <div className="mt-3 space-y-2">
                              {ingredient.epicerie_links.map((link) => {
                                const fournisseur = link.fournisseur || 'METRO';
                                const config = FOURNISSEUR_CONFIG[fournisseur] || FOURNISSEUR_CONFIG.OTHER;
                                const Icon = config.icon;
                                return (
                                  <div
                                    key={link.id}
                                    className="flex items-center justify-between p-2.5 bg-dark-700/50 rounded-lg group"
                                  >
                                    <div className="flex items-center gap-3">
                                      <ArrowRight className="w-4 h-4 text-dark-500" />
                                      <div className={cn('p-1.5 rounded-lg', config.bgColor)}>
                                        <Icon className={cn('w-4 h-4', config.color)} />
                                      </div>
                                      <div>
                                        <div className="flex items-center gap-2">
                                          <Badge variant="default" size="sm" className={config.bgColor}>
                                            <span className={config.color}>{config.label}</span>
                                          </Badge>
                                          <span className="text-white font-medium">
                                            {link.produit_nom || `Produit #${link.produit_id}`}
                                          </span>
                                          {link.is_primary && (
                                            <Badge variant="warning" size="sm">
                                              <Star className="w-3 h-3 mr-1" />
                                              Principal
                                            </Badge>
                                          )}
                                        </div>
                                        <div className="text-sm text-dark-400 mt-0.5">
                                          {link.produit_prix !== null && (
                                            <span>Prix: {formatCurrency(link.produit_prix / 100)}</span>
                                          )}
                                          {link.ratio !== 1 && (
                                            <span className="ml-2">| Ratio: x{link.ratio}</span>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                      {!link.is_primary && (
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => handleSetPrimary(link)}
                                          title="Definir comme principal"
                                        >
                                          <Star className="w-4 h-4" />
                                        </Button>
                                      )}
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleOpenEditModal(link)}
                                        title="Modifier le ratio"
                                      >
                                        <Pencil className="w-4 h-4" />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-red-400 hover:text-red-300"
                                        onClick={() => handleDeleteLink(link)}
                                      >
                                        <Trash2 className="w-4 h-4" />
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                      <Button
                        variant={hasLinks ? 'secondary' : 'primary'}
                        size="sm"
                        onClick={() => handleOpenLinkModal(ingredient)}
                      >
                        <Plus className="w-4 h-4 mr-1" />
                        Lier
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal de liaison ameliore */}
      <Modal
        isOpen={isLinkModalOpen}
        onClose={() => {
          setIsLinkModalOpen(false);
          setSelectedIngredient(null);
          setSearchProduct('');
          setLinkFormData({ ratio: 1 });
        }}
        title={`Lier un produit fournisseur${selectedIngredient ? ` - ${selectedIngredient.name}` : ''}`}
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsLinkModalOpen(false);
              setSelectedIngredient(null);
            }}
            onConfirm={linkFormData.produit ? handleCreateLink : undefined}
            cancelText="Annuler"
            confirmText="Creer le lien"
            loading={createLink.isPending}
          />
        }
      >
        <div className="space-y-5">
          {/* Filtre fournisseur */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Fournisseur
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setFournisseurFilter('all')}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
                  fournisseurFilter === 'all'
                    ? 'border-primary-500 bg-primary-500/20 text-white'
                    : 'border-dark-600 text-dark-400 hover:text-white hover:border-dark-500'
                )}
              >
                <Package className="w-4 h-4" />
                Tous
              </button>
              {Object.entries(FOURNISSEUR_CONFIG).map(([key, config]) => {
                const Icon = config.icon;
                return (
                  <button
                    key={key}
                    onClick={() => setFournisseurFilter(key.toLowerCase())}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors',
                      fournisseurFilter === key.toLowerCase()
                        ? `border-current ${config.bgColor} ${config.color}`
                        : 'border-dark-600 text-dark-400 hover:text-white hover:border-dark-500'
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    {config.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Recherche produit */}
          <div>
            <label className="block text-sm font-medium text-dark-300 mb-2">
              Rechercher un produit
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
              <Input
                placeholder="Tapez au moins 2 caracteres..."
                value={searchProduct}
                onChange={(e) => setSearchProduct(e.target.value)}
                className="pl-10"
              />
              {searchProduct && (
                <button
                  onClick={() => setSearchProduct('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Resultats */}
          {searchProduct.length >= 2 && (
            <div className="border border-dark-600 rounded-lg overflow-hidden">
              <div className="bg-dark-700/50 px-3 py-2 border-b border-dark-600 flex items-center justify-between">
                <span className="text-sm text-dark-400">
                  {isSearching ? 'Recherche...' : `${searchResults?.length || 0} resultat(s)`}
                </span>
                {searchResults && searchResults.length > 0 && (
                  <span className="text-xs text-dark-500">
                    Triés par pertinence
                  </span>
                )}
              </div>
              <div className="max-h-[400px] overflow-y-auto">
                {isSearching ? (
                  <div className="p-6 text-center">
                    <Spinner size="sm" />
                  </div>
                ) : searchResults && searchResults.length > 0 ? (
                  <div className="divide-y divide-dark-700">
                    {searchResults.map((produit) => {
                      const fournisseur = produit.fournisseur || 'METRO';
                      const config = FOURNISSEUR_CONFIG[fournisseur] || FOURNISSEUR_CONFIG.OTHER;
                      const Icon = config.icon;
                      const isSelected = linkFormData.produit?.id === produit.id &&
                                        linkFormData.produit?.fournisseur === produit.fournisseur;
                      return (
                        <button
                          key={`${produit.fournisseur}-${produit.id}`}
                          className={cn(
                            'w-full p-3 text-left transition-colors',
                            isSelected ? 'bg-primary-500/20' : 'hover:bg-dark-700/50'
                          )}
                          onClick={() => setLinkFormData(prev => ({ ...prev, produit }))}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              <div className={cn('p-1.5 rounded-lg flex-shrink-0', config.bgColor)}>
                                <Icon className={cn('w-4 h-4', config.color)} />
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <Badge variant="default" size="sm" className={cn('flex-shrink-0', config.bgColor)}>
                                    <span className={config.color}>{config.label}</span>
                                  </Badge>
                                </div>
                                <p className="text-white font-medium truncate mt-1">{produit.designation}</p>
                                <p className="text-sm text-dark-400 truncate">
                                  {produit.famille} {produit.categorie && `> ${produit.categorie}`}
                                </p>
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              {produit.prix_unitaire_moyen !== null && (
                                <p className="text-primary-400 font-medium">
                                  {formatCurrency(produit.prix_unitaire_moyen / 100)}
                                  {produit.unite && <span className="text-dark-400">/{produit.unite}</span>}
                                </p>
                              )}
                              {isSelected && (
                                <Check className="w-5 h-5 text-green-400 mt-1 ml-auto" />
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-6 text-center text-dark-400">
                    Aucun produit trouve
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Produit selectionne */}
          {linkFormData.produit && (
            <div className="p-4 bg-primary-500/10 border border-primary-500/30 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    'p-2 rounded-lg',
                    FOURNISSEUR_CONFIG[linkFormData.produit.fournisseur]?.bgColor || 'bg-dark-700'
                  )}>
                    {(() => {
                      const Icon = FOURNISSEUR_CONFIG[linkFormData.produit.fournisseur]?.icon || Package;
                      return <Icon className={cn(
                        'w-5 h-5',
                        FOURNISSEUR_CONFIG[linkFormData.produit.fournisseur]?.color || 'text-dark-400'
                      )} />;
                    })()}
                  </div>
                  <div>
                    <p className="text-sm text-dark-400">Produit selectionne</p>
                    <p className="text-white font-medium">{linkFormData.produit.designation}</p>
                  </div>
                </div>
                <button
                  onClick={() => setLinkFormData(prev => ({ ...prev, produit: undefined }))}
                  className="text-dark-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}

          {/* Ratio */}
          <div>
            <Input
              type="number"
              label="Ratio de conversion"
              value={linkFormData.ratio}
              onChange={(e) => setLinkFormData(prev => ({ ...prev, ratio: Number(e.target.value) }))}
              placeholder="1"
              step="0.01"
              min="0.01"
            />
            <p className="text-xs text-dark-400 mt-1.5">
              Multiplicateur pour convertir le prix fournisseur vers l'ingredient (ex: 1 = prix identique, 0.5 = moitie du prix)
            </p>
          </div>
        </div>
      </Modal>

      {/* Modal d'edition du lien */}
      <Modal
        isOpen={!!editingLink}
        onClose={() => setEditingLink(null)}
        title="Modifier le lien"
        size="sm"
        footer={
          <ModalFooter
            onCancel={() => setEditingLink(null)}
            onConfirm={handleUpdateLink}
            cancelText="Annuler"
            confirmText="Enregistrer"
            loading={updateLink.isPending}
          />
        }
      >
        {editingLink && (
          <div className="space-y-4">
            <div className="p-3 bg-dark-700/50 rounded-lg">
              <p className="text-sm text-dark-400 mb-1">Produit lie</p>
              <p className="text-white font-medium">
                {editingLink.produit_nom || `Produit #${editingLink.produit_id}`}
              </p>
              <Badge variant="default" size="sm" className="mt-2">
                {FOURNISSEUR_CONFIG[editingLink.fournisseur]?.label || editingLink.fournisseur}
              </Badge>
            </div>
            <div>
              <Input
                type="number"
                label="Ratio de conversion"
                value={editFormData.ratio}
                onChange={(e) => setEditFormData({ ratio: Number(e.target.value) })}
                placeholder="1"
                step="0.01"
                min="0.01"
              />
              <p className="text-xs text-dark-400 mt-1.5">
                Multiplicateur pour convertir le prix fournisseur vers l'ingredient
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
