import { useState } from 'react';
import {
  Package,
  Plus,
  Minus,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  History,
  Search,
} from 'lucide-react';
import {
  useStocks,
  useLowStock,
  useStockTotalValue,
  useCreateStockMovement,
  useAdjustStock,
  useStockMovements,
} from '../../hooks/useRestaurant';
import type { Stock, StockMovementCreate, StockAdjustment } from '../../types/restaurant';
import {
  RestaurantStockMovementType,
  STOCK_MOVEMENT_TYPE_LABELS,
  UNIT_LABELS,
} from '../../types/restaurant';
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
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency, formatDate } from '../../lib/utils';

export default function StockPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isMovementModalOpen, setIsMovementModalOpen] = useState(false);
  const [isAdjustModalOpen, setIsAdjustModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [movementType, setMovementType] = useState<'entree' | 'sortie'>('entree');

  const [movementData, setMovementData] = useState<StockMovementCreate>({
    ingredient_id: 0,
    quantite: 0,
    movement_type: RestaurantStockMovementType.ENTREE,
    reference: '',
    notes: '',
    cout_unitaire: undefined,
  });

  const [adjustData, setAdjustData] = useState<StockAdjustment>({
    ingredient_id: 0,
    nouvelle_quantite: 0,
    notes: '',
  });

  const { data: stocks, isLoading, refetch } = useStocks();
  const { data: lowStockAlerts } = useLowStock();
  const { data: totalValue } = useStockTotalValue();
  const createMovement = useCreateStockMovement();
  const adjustStock = useAdjustStock();
  const { data: movements } = useStockMovements(selectedStock?.ingredient_id || 0);

  const filteredStocks = stocks?.filter(stock =>
    stock.ingredient_name.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const openMovementModal = (stock: Stock, type: 'entree' | 'sortie') => {
    setSelectedStock(stock);
    setMovementType(type);
    setMovementData({
      ingredient_id: stock.ingredient_id,
      quantite: 0,
      movement_type: type === 'entree' ? RestaurantStockMovementType.ENTREE : RestaurantStockMovementType.SORTIE,
      reference: '',
      notes: '',
      cout_unitaire: undefined,
    });
    setIsMovementModalOpen(true);
  };

  const openAdjustModal = (stock: Stock) => {
    setSelectedStock(stock);
    setAdjustData({
      ingredient_id: stock.ingredient_id,
      nouvelle_quantite: Number(stock.quantite_actuelle),
      notes: '',
    });
    setIsAdjustModalOpen(true);
  };

  const openHistoryModal = (stock: Stock) => {
    setSelectedStock(stock);
    setIsHistoryModalOpen(true);
  };

  const handleMovement = async () => {
    try {
      await createMovement.mutateAsync({
        ...movementData,
        cout_unitaire: movementData.cout_unitaire ? Math.round(movementData.cout_unitaire * 100) : undefined,
      });
      setIsMovementModalOpen(false);
      setSelectedStock(null);
    } catch (error) {
      console.error('Erreur mouvement:', error);
    }
  };

  const handleAdjust = async () => {
    try {
      await adjustStock.mutateAsync(adjustData);
      setIsAdjustModalOpen(false);
      setSelectedStock(null);
    } catch (error) {
      console.error('Erreur ajustement:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement des stocks..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Gestion des stocks"
        subtitle="Suivi et mouvements de stock"
        breadcrumbs={[
          { label: 'Restaurant', href: '/restaurant' },
          { label: 'Stock' },
        ]}
        actions={
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Actualiser
          </Button>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Valeur totale</p>
                <p className="text-3xl font-bold text-white">
                  {formatCurrency((totalValue?.total_value || 0) / 100)}
                </p>
              </div>
              <Package className="w-10 h-10 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">References</p>
                <p className="text-3xl font-bold text-white">{stocks?.length || 0}</p>
              </div>
              <Package className="w-10 h-10 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Alertes stock bas</p>
                <p className="text-3xl font-bold text-yellow-400">
                  {lowStockAlerts?.length || 0}
                </p>
              </div>
              <AlertTriangle className="w-10 h-10 text-yellow-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Alertes */}
      {lowStockAlerts && lowStockAlerts.length > 0 && (
        <Alert variant="warning" title="Attention: Stock bas">
          <div className="mt-2 flex flex-wrap gap-2">
            {lowStockAlerts.map((alert, idx) => (
              <Badge key={idx} variant="warning" size="sm">
                {alert.ingredient_name}: {alert.quantite_actuelle} {UNIT_LABELS[alert.unit]}
              </Badge>
            ))}
          </div>
        </Alert>
      )}

      {/* Recherche */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center gap-4">
            <div className="flex-1">
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

      {/* Liste des stocks */}
      <Card>
        <CardHeader>
          <CardTitle subtitle={`${filteredStocks.length} reference(s)`}>
            <Package className="w-5 h-5 inline mr-2" />
            Etat des stocks
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredStocks.length === 0 ? (
            <EmptyState
              icon={<Package className="w-12 h-12" />}
              title="Aucun stock"
              description="Les stocks seront crees automatiquement avec les ingredients."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-dark-700/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-dark-400 uppercase">Ingredient</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Quantite</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Dernier prix</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-dark-400 uppercase">Valeur</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Statut</th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-dark-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700">
                  {filteredStocks.map((stock) => (
                    <tr key={stock.id} className="hover:bg-dark-700/30">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Package className="w-4 h-4 text-dark-400" />
                          <span className="font-medium text-white">{stock.ingredient_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`font-medium ${stock.is_low_stock ? 'text-red-400' : 'text-white'}`}>
                          {stock.quantite_actuelle}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-dark-300">
                        {stock.dernier_prix_achat
                          ? formatCurrency(stock.dernier_prix_achat / 100)
                          : '-'}
                      </td>
                      <td className="px-4 py-3 text-right text-white">
                        {formatCurrency(stock.valeur_stock / 100)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {stock.is_low_stock ? (
                          <Badge variant="danger" size="sm">
                            <AlertTriangle className="w-3 h-3 mr-1" />
                            Bas
                          </Badge>
                        ) : (
                          <Badge variant="success" size="sm">OK</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-green-400"
                            onClick={() => openMovementModal(stock, 'entree')}
                            title="Entree de stock"
                          >
                            <Plus className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-400"
                            onClick={() => openMovementModal(stock, 'sortie')}
                            title="Sortie de stock"
                          >
                            <Minus className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openAdjustModal(stock)}
                            title="Ajustement inventaire"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openHistoryModal(stock)}
                            title="Historique"
                          >
                            <History className="w-4 h-4" />
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

      {/* Modal mouvement */}
      <Modal
        isOpen={isMovementModalOpen}
        onClose={() => setIsMovementModalOpen(false)}
        title={movementType === 'entree' ? 'Entree de stock' : 'Sortie de stock'}
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsMovementModalOpen(false)}
            onConfirm={handleMovement}
            cancelText="Annuler"
            confirmText="Enregistrer"
            loading={createMovement.isPending}
          />
        }
      >
        <div className="space-y-4">
          <div className="p-3 bg-dark-700 rounded-lg">
            <p className="text-sm text-dark-400">Ingredient</p>
            <p className="font-medium text-white">{selectedStock?.ingredient_name}</p>
            <p className="text-sm text-dark-400 mt-1">
              Stock actuel: {selectedStock?.quantite_actuelle}
            </p>
          </div>

          <Input
            type="number"
            label="Quantite"
            value={movementData.quantite || ''}
            onChange={(e) => setMovementData(prev => ({ ...prev, quantite: Number(e.target.value) }))}
            placeholder="0"
            min="0"
            step="0.01"
            required
          />

          {movementType === 'entree' && (
            <Input
              type="number"
              label="Cout unitaire (EUR)"
              value={movementData.cout_unitaire || ''}
              onChange={(e) => setMovementData(prev => ({ ...prev, cout_unitaire: e.target.value ? Number(e.target.value) : undefined }))}
              placeholder="0.00"
              step="0.01"
            />
          )}

          <Input
            label="Reference"
            value={movementData.reference || ''}
            onChange={(e) => setMovementData(prev => ({ ...prev, reference: e.target.value }))}
            placeholder="Ex: BL-12345"
          />

          <Input
            label="Notes"
            value={movementData.notes || ''}
            onChange={(e) => setMovementData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Notes..."
          />
        </div>
      </Modal>

      {/* Modal ajustement */}
      <Modal
        isOpen={isAdjustModalOpen}
        onClose={() => setIsAdjustModalOpen(false)}
        title="Ajustement inventaire"
        size="md"
        footer={
          <ModalFooter
            onCancel={() => setIsAdjustModalOpen(false)}
            onConfirm={handleAdjust}
            cancelText="Annuler"
            confirmText="Ajuster"
            loading={adjustStock.isPending}
          />
        }
      >
        <div className="space-y-4">
          <div className="p-3 bg-dark-700 rounded-lg">
            <p className="text-sm text-dark-400">Ingredient</p>
            <p className="font-medium text-white">{selectedStock?.ingredient_name}</p>
            <p className="text-sm text-dark-400 mt-1">
              Stock actuel: {selectedStock?.quantite_actuelle}
            </p>
          </div>

          <Input
            type="number"
            label="Nouvelle quantite"
            value={adjustData.nouvelle_quantite || ''}
            onChange={(e) => setAdjustData(prev => ({ ...prev, nouvelle_quantite: Number(e.target.value) }))}
            placeholder="0"
            min="0"
            step="0.01"
            required
          />

          <Input
            label="Notes (raison de l'ajustement)"
            value={adjustData.notes || ''}
            onChange={(e) => setAdjustData(prev => ({ ...prev, notes: e.target.value }))}
            placeholder="Ex: Inventaire physique"
          />
        </div>
      </Modal>

      {/* Modal historique */}
      <Modal
        isOpen={isHistoryModalOpen}
        onClose={() => {
          setIsHistoryModalOpen(false);
          setSelectedStock(null);
        }}
        title={`Historique - ${selectedStock?.ingredient_name}`}
        size="lg"
        footer={
          <ModalFooter
            onCancel={() => {
              setIsHistoryModalOpen(false);
              setSelectedStock(null);
            }}
            cancelText="Fermer"
          />
        }
      >
        <div className="max-h-96 overflow-y-auto">
          {movements && movements.length > 0 ? (
            <table className="w-full">
              <thead className="bg-dark-700/50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-dark-400">Date</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-dark-400">Type</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-dark-400">Qte</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-dark-400">Avant</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-dark-400">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-700">
                {movements.map((mov) => (
                  <tr key={mov.id}>
                    <td className="px-3 py-2 text-sm text-white">
                      {formatDate(mov.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        variant={mov.type === RestaurantStockMovementType.ENTREE ? 'success' : 'danger'}
                        size="sm"
                      >
                        {mov.type === RestaurantStockMovementType.ENTREE && <TrendingUp className="w-3 h-3 mr-1" />}
                        {mov.type === RestaurantStockMovementType.SORTIE && <TrendingDown className="w-3 h-3 mr-1" />}
                        {STOCK_MOVEMENT_TYPE_LABELS[mov.type]}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-right text-sm">
                      <span className={mov.type === RestaurantStockMovementType.ENTREE ? 'text-green-400' : 'text-red-400'}>
                        {mov.type === RestaurantStockMovementType.ENTREE ? '+' : '-'}{mov.quantite}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-sm text-dark-400">
                      {mov.quantite_avant}
                    </td>
                    <td className="px-3 py-2 text-sm text-dark-300">
                      {mov.reference || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-center text-dark-400 py-8">Aucun mouvement enregistre</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
