import { useState } from 'react';
import {
  ChefHat,
  Package,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  DollarSign,
  ShoppingCart,
  Users,
  RefreshCw,
  Calendar,
} from 'lucide-react';
import { useRestaurantDashboard, useLowStock, useChargesSummary } from '../../hooks/useRestaurant';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Badge,
  Spinner,
  Alert,
} from '../../components/ui';
import { PageHeader } from '../../components/ui/Breadcrumb';
import { formatCurrency } from '../../lib/utils';
import { CHARGE_TYPE_LABELS, UNIT_LABELS } from '../../types/restaurant';

export default function RestaurantDashboard() {
  const [selectedDate] = useState<string>(new Date().toISOString().split('T')[0]);

  const { data: dashboard, isLoading, refetch } = useRestaurantDashboard(selectedDate);
  const { data: lowStockAlerts } = useLowStock();
  const { data: chargesSummary } = useChargesSummary();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement du dashboard..." />
      </div>
    );
  }

  const margin = dashboard?.daily?.revenue && dashboard?.daily?.cost
    ? ((dashboard.daily.revenue - dashboard.daily.cost) / dashboard.daily.revenue * 100).toFixed(1)
    : '0';

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard Restaurant"
        subtitle="Vue d'ensemble de votre activite"
        breadcrumbs={[
          { label: 'Restaurant' },
        ]}
        actions={
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Actualiser
          </Button>
        }
      />

      {/* KPIs principaux */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">CA du jour</p>
                <p className="text-3xl font-bold text-green-400">
                  {formatCurrency((dashboard?.daily?.revenue || 0) / 100)}
                </p>
                <p className="text-xs text-dark-500 mt-1">
                  {dashboard?.daily?.sales_count || 0} ventes
                </p>
              </div>
              <TrendingUp className="w-10 h-10 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Couts du jour</p>
                <p className="text-3xl font-bold text-red-400">
                  {formatCurrency((dashboard?.daily?.cost || 0) / 100)}
                </p>
                <p className="text-xs text-dark-500 mt-1">
                  {dashboard?.daily?.losses_count || 0} pertes
                </p>
              </div>
              <TrendingDown className="w-10 h-10 text-red-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Marge brute</p>
                <p className={`text-3xl font-bold ${Number(margin) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {margin}%
                </p>
                <p className="text-xs text-dark-500 mt-1">
                  {formatCurrency((dashboard?.daily?.margin || 0) / 100)}
                </p>
              </div>
              <DollarSign className="w-10 h-10 text-primary-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Valeur stock</p>
                <p className="text-3xl font-bold text-white">
                  {formatCurrency((dashboard?.stock?.total_value || 0) / 100)}
                </p>
                <p className="text-xs text-dark-500 mt-1">
                  {dashboard?.stock?.alerts_count || 0} alertes
                </p>
              </div>
              <Package className="w-10 h-10 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Alertes stock bas */}
      {lowStockAlerts && lowStockAlerts.length > 0 && (
        <Alert variant="warning" title="Alertes de stock bas">
          <div className="mt-2 space-y-2">
            {lowStockAlerts.slice(0, 5).map((alert, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <span>{alert.ingredient_name}</span>
                <Badge variant="warning" size="sm">
                  {alert.quantite_actuelle} {UNIT_LABELS[alert.unit]} (seuil: {alert.seuil_alerte})
                </Badge>
              </div>
            ))}
          </div>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Charges mensuelles */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="Charges fixes et variables">
              <DollarSign className="w-5 h-5 inline mr-2" />
              Charges mensuelles
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-dark-700 rounded-lg">
                <span className="text-dark-300">Total mensuel</span>
                <span className="text-2xl font-bold text-white">
                  {formatCurrency((chargesSummary?.total_mensuel || 0) / 100)}
                </span>
              </div>

              <div className="space-y-2">
                {chargesSummary?.by_type && Object.entries(chargesSummary.by_type).map(([type, montant]) => (
                  montant > 0 && (
                    <div key={type} className="flex items-center justify-between py-2 border-b border-dark-700">
                      <span className="text-sm text-dark-300">
                        {CHARGE_TYPE_LABELS[type as keyof typeof CHARGE_TYPE_LABELS] || type}
                      </span>
                      <span className="text-sm font-medium text-white">
                        {formatCurrency(montant / 100)}
                      </span>
                    </div>
                  )
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Activite du jour */}
        <Card>
          <CardHeader>
            <CardTitle subtitle={selectedDate}>
              <Calendar className="w-5 h-5 inline mr-2" />
              Activite du jour
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-green-900/20 rounded-lg text-center">
                  <ShoppingCart className="w-8 h-8 mx-auto text-green-500 mb-2" />
                  <p className="text-2xl font-bold text-green-400">
                    {dashboard?.daily?.sales_count || 0}
                  </p>
                  <p className="text-xs text-dark-400">Ventes</p>
                </div>

                <div className="p-4 bg-red-900/20 rounded-lg text-center">
                  <AlertTriangle className="w-8 h-8 mx-auto text-red-500 mb-2" />
                  <p className="text-2xl font-bold text-red-400">
                    {dashboard?.daily?.losses_count || 0}
                  </p>
                  <p className="text-xs text-dark-400">Pertes</p>
                </div>
              </div>

              <div className="p-4 bg-dark-700 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-dark-400">Revenus</span>
                  <span className="text-green-400">
                    +{formatCurrency((dashboard?.daily?.revenue || 0) / 100)}
                  </span>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-dark-400">Couts</span>
                  <span className="text-red-400">
                    -{formatCurrency((dashboard?.daily?.cost || 0) / 100)}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-dark-600">
                  <span className="text-sm font-medium text-white">Marge</span>
                  <span className={`font-bold ${(dashboard?.daily?.margin || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency((dashboard?.daily?.margin || 0) / 100)}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Liens rapides */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card hover className="cursor-pointer" onClick={() => window.location.href = '/restaurant/ingredients'}>
          <CardContent className="py-6 text-center">
            <ChefHat className="w-10 h-10 mx-auto text-primary-500 mb-2" />
            <p className="font-medium text-white">Ingredients</p>
            <p className="text-xs text-dark-400">Gerer les ingredients</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => window.location.href = '/restaurant/plats'}>
          <CardContent className="py-6 text-center">
            <ShoppingCart className="w-10 h-10 mx-auto text-green-500 mb-2" />
            <p className="font-medium text-white">Menu</p>
            <p className="text-xs text-dark-400">Plats et menus</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => window.location.href = '/restaurant/stock'}>
          <CardContent className="py-6 text-center">
            <Package className="w-10 h-10 mx-auto text-blue-500 mb-2" />
            <p className="font-medium text-white">Stock</p>
            <p className="text-xs text-dark-400">Gestion des stocks</p>
          </CardContent>
        </Card>

        <Card hover className="cursor-pointer" onClick={() => window.location.href = '/restaurant/ventes'}>
          <CardContent className="py-6 text-center">
            <Users className="w-10 h-10 mx-auto text-yellow-500 mb-2" />
            <p className="font-medium text-white">Ventes</p>
            <p className="text-xs text-dark-400">Enregistrer les ventes</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
