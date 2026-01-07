import { Link } from 'react-router-dom';
import {
  Package,
  ShoppingCart,
  TrendingUp,
  AlertTriangle,
  Truck,
  BarChart3,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { useMetroSummary, useMetroProducts } from '@/hooks/useMetro';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Spinner,
} from '@/components/ui';
import { PageHeader } from '@/components/ui/Breadcrumb';
import { formatCurrency } from '@/lib/utils';

export default function EpicerieDashboard() {
  const {
    data: summary,
    isLoading: loadingSummary,
    refetch: refetchSummary,
  } = useMetroSummary();

  const {
    data: productsData,
    isLoading: loadingTop,
    refetch: refetchProducts,
  } = useMetroProducts({
    per_page: 5,
    sort_by: 'montant_total',
    sort_order: 'desc',
  });

  const handleRefresh = () => {
    refetchSummary();
    refetchProducts();
  };

  if (loadingSummary) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Chargement..." />
      </div>
    );
  }

  const totalHT = parseFloat(summary?.total_ht || '0');
  const totalTVA = parseFloat(summary?.total_tva || '0');
  const topProducts = productsData?.items || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Epicerie"
        subtitle="Vue d'ensemble de l'activite epicerie"
        breadcrumbs={[{ label: 'Epicerie' }]}
        actions={
          <Button variant="secondary" onClick={handleRefresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Actualiser
          </Button>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Produits</p>
                <p className="text-3xl font-bold text-white">
                  {summary?.nb_produits || 0}
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
                <p className="text-sm text-dark-400">Chiffre d'affaires HT</p>
                <p className="text-3xl font-bold text-green-400">
                  {formatCurrency(totalHT)}
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
                <p className="text-sm text-dark-400">TVA collectee</p>
                <p className="text-3xl font-bold text-orange-400">
                  {formatCurrency(totalTVA)}
                </p>
              </div>
              <BarChart3 className="w-10 h-10 text-orange-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="py-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-dark-400">Factures</p>
                <p className="text-3xl font-bold text-blue-400">
                  {summary?.nb_factures || 0}
                </p>
              </div>
              <ShoppingCart className="w-10 h-10 text-blue-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Produits */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>
              <TrendingUp className="w-5 h-5 inline mr-2" />
              Top 5 Produits
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loadingTop ? (
              <div className="flex justify-center py-8">
                <Spinner />
              </div>
            ) : (
              <div className="space-y-3">
                {topProducts.map((product, index) => (
                  <div
                    key={product.id}
                    className="flex items-center gap-4 p-3 bg-dark-700/50 rounded-lg"
                  >
                    <div
                      className={`w-8 h-8 flex items-center justify-center rounded-full font-bold text-sm ${
                        index === 0
                          ? 'bg-yellow-500/30 text-yellow-400'
                          : index === 1
                          ? 'bg-slate-400/30 text-slate-300'
                          : index === 2
                          ? 'bg-amber-700/30 text-amber-600'
                          : 'bg-dark-600 text-dark-400'
                      }`}
                    >
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-white truncate">
                        {product.designation}
                      </p>
                      <p className="text-xs text-dark-400">
                        {product.nb_achats} achats
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold text-blue-400">
                        {formatCurrency(parseFloat(product.montant_total_ht))}
                      </p>
                      <p className="text-xs text-dark-400">
                        {parseFloat(product.quantite_unitaire_totale).toFixed(0)} unites
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Actions rapides */}
        <Card>
          <CardHeader>
            <CardTitle>Actions rapides</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link
              to="/epicerie/catalogue"
              className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg hover:bg-dark-700 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Package className="w-5 h-5 text-primary-500" />
                <span className="font-medium text-white">Catalogue produits</span>
              </div>
              <ArrowRight className="w-4 h-4 text-dark-400" />
            </Link>

            <Link
              to="/epicerie/pos"
              className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg hover:bg-dark-700 transition-colors"
            >
              <div className="flex items-center gap-3">
                <ShoppingCart className="w-5 h-5 text-green-500" />
                <span className="font-medium text-white">Vente POS</span>
              </div>
              <ArrowRight className="w-4 h-4 text-dark-400" />
            </Link>

            <Link
              to="/epicerie/fournisseurs"
              className="flex items-center justify-between p-4 bg-dark-700/50 rounded-lg hover:bg-dark-700 transition-colors"
            >
              <div className="flex items-center gap-3">
                <Truck className="w-5 h-5 text-orange-500" />
                <span className="font-medium text-white">Fournisseurs</span>
              </div>
              <ArrowRight className="w-4 h-4 text-dark-400" />
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Alertes stock */}
      <Card>
        <CardHeader>
          <CardTitle>
            <AlertTriangle className="w-5 h-5 inline mr-2 text-orange-500" />
            Alertes stock
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-dark-400">
            <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>Aucune alerte stock pour le moment</p>
            <p className="text-sm">Les produits en rupture apparaitront ici</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
