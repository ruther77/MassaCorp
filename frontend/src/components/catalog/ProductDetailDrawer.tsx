/**
 * ProductDetailDrawer - Drawer détail produit Data-Viz Native
 *
 * Architecture SID - Restitution décisionnelle:
 * - Données brutes -> KPIs interprétés -> Indicateurs visuels
 * - Support au processus décisionnel (identification, analyse, choix)
 *
 * Sections:
 * 1. Hero: Identité produit + statut global
 * 2. KPIs: Stock, couverture, ventes, marge
 * 3. Prix: Achat, vente, marge détaillée
 * 4. Stock Level: Jauge visuelle avec seuils
 * 5. Mouvements: Historique récent (tendance)
 */
import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import {
  X,
  Package,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  BarChart3,
  ArrowDownCircle,
  ArrowUpCircle,
  RefreshCw,
  ShoppingCart,
  Edit3,
  Loader2,
} from 'lucide-react'
import { useProductDetail } from '@/hooks/useProducts'
import { ProduitListItem, MouvementStock } from '@/api/catalog'

// ============================================================================
// TYPES
// ============================================================================

interface ProductDetailDrawerProps {
  open: boolean
  onClose: () => void
  product: ProduitListItem | null
  onEdit?: (product: ProduitListItem) => void
  onOrder?: (product: ProduitListItem) => void
}

// ============================================================================
// SUB-COMPONENTS - Data Visualization Native
// ============================================================================

/** Carte KPI avec tendance */
function StatItem({
  label,
  value,
  valueColor,
  trend,
  trendType,
  isLoading,
}: {
  label: string
  value: string
  valueColor?: string
  trend?: string
  trendType?: 'up' | 'down' | 'neutral'
  isLoading?: boolean
}) {
  return (
    <div className="p-3 rounded-lg bg-dark-700/50">
      <p className="text-xs text-dark-400 mb-1">{label}</p>
      {isLoading ? (
        <div className="h-7 w-16 bg-dark-600 rounded animate-pulse" />
      ) : (
        <p className={cn('text-lg font-bold', valueColor || 'text-white')}>{value}</p>
      )}
      {trend && !isLoading && (
        <p
          className={cn(
            'text-xs mt-1 flex items-center gap-1',
            trendType === 'up' ? 'text-green-400' : trendType === 'down' ? 'text-red-400' : 'text-dark-400'
          )}
        >
          {trendType === 'up' && <TrendingUp className="w-3 h-3" />}
          {trendType === 'down' && <TrendingDown className="w-3 h-3" />}
          {trend}
        </p>
      )}
    </div>
  )
}

/** Ligne de prix */
function PriceRow({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div className="flex justify-between py-2.5 border-b border-dark-700 last:border-0">
      <span className="text-sm text-dark-400">{label}</span>
      <span className={cn('text-sm font-semibold', valueColor || 'text-white')}>{value}</span>
    </div>
  )
}

/** Jauge niveau de stock - Indicateur décisionnel visuel */
function StockLevelBar({
  current,
  min,
  max,
}: {
  current: number
  min: number
  max: number
}) {
  const percentage = max > 0 ? (current / max) * 100 : 0
  const minPercentage = max > 0 ? (min / max) * 100 : 20

  // Couleur selon règle métier
  let fillColor = 'bg-green-500'
  if (current <= 0) fillColor = 'bg-red-500'
  else if (current <= min) fillColor = 'bg-red-500'
  else if (current <= min * 1.5) fillColor = 'bg-amber-500'

  return (
    <div className="mt-4">
      <div className="flex justify-between text-xs text-dark-500 mb-2">
        <span>0</span>
        <span>Seuil: {min}</span>
        <span>Max: {Math.round(max)}</span>
      </div>
      <div className="h-2 bg-dark-700 rounded-full relative overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all duration-500', fillColor)}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
        {/* Marqueur seuil d'alerte */}
        <div
          className="absolute h-full w-0.5 bg-amber-400"
          style={{ left: `${minPercentage}%` }}
        />
      </div>
    </div>
  )
}

/** Item mouvement stock - Historique pour analyse tendance */
function MovementItem({
  movement,
}: {
  movement: MouvementStock
}) {
  const isEntry = movement.type_mouvement === 'ENTREE'
  const isInventory = movement.type_mouvement === 'INVENTAIRE'

  const config = {
    icon: isEntry ? ArrowDownCircle : isInventory ? RefreshCw : ArrowUpCircle,
    bg: isEntry ? 'bg-green-500/20' : isInventory ? 'bg-blue-500/20' : 'bg-red-500/20',
    color: isEntry ? 'text-green-400' : isInventory ? 'text-blue-400' : 'text-red-400',
  }

  const Icon = config.icon
  const dateFormatted = new Date(movement.date).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-dark-700 last:border-0">
      <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', config.bg)}>
        <Icon className={cn('w-4 h-4', config.color)} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-white truncate">
          {movement.source || movement.type_mouvement}
        </p>
        <p className="text-xs text-dark-500">{dateFormatted}</p>
      </div>
      <span className={cn('text-sm font-semibold', config.color)}>
        {isEntry ? '+' : '-'}
        {Math.abs(movement.quantite)}
      </span>
    </div>
  )
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function ProductDetailDrawer({
  open,
  onClose,
  product,
  onEdit,
  onOrder,
}: ProductDetailDrawerProps) {
  // Fetch enriched data from DWH
  const { data: enrichedProduct, isLoading } = useProductDetail(product?.produit_sk ?? null)

  // Merge base product with enriched data
  const productData = useMemo(() => {
    if (!product) return null
    return {
      ...product,
      ...enrichedProduct,
    }
  }, [product, enrichedProduct])

  // Calcul statut stock - Règle métier -> Indicateur décisionnel
  const stockStatus = useMemo(() => {
    if (!productData) return { status: 'ok', label: 'OK', color: 'text-green-400', bg: 'bg-green-500/20' }

    const stock = productData.stock_actuel || 0
    const min = productData.seuil_alerte || 10

    if (stock === 0) return { status: 'critical', label: 'Rupture', color: 'text-red-400', bg: 'bg-red-500/20' }
    if (stock <= min) return { status: 'low', label: 'Stock bas', color: 'text-amber-400', bg: 'bg-amber-500/20' }
    return { status: 'ok', label: 'OK', color: 'text-green-400', bg: 'bg-green-500/20' }
  }, [productData])

  // Calcul marge - Mesure calculée
  const margin = useMemo(() => {
    if (!productData?.prix_vente || !productData?.prix_achat) return null
    const marginValue = Number(productData.prix_vente) - Number(productData.prix_achat)
    const marginPercent = ((marginValue / Number(productData.prix_vente)) * 100).toFixed(0)
    return { value: marginValue.toFixed(2), percent: marginPercent }
  }, [productData])

  // Format couverture stock
  const joursStockDisplay = useMemo(() => {
    if (!productData) return '—'
    const jours = productData.jours_stock || 0
    if (jours >= 999) return '∞'
    if (jours === 0) return '0j'
    return `${Math.round(jours)}j`
  }, [productData])

  // Format currency
  const formatCurrency = (value: number | null | undefined) => {
    if (value === null || value === undefined) return '—'
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(Number(value))
  }

  if (!open || !product) return null

  return (
    <>
      {/* Overlay */}
      <div
        className={cn(
          'fixed inset-0 bg-black/50 backdrop-blur-sm z-40 transition-opacity duration-300',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        )}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          'fixed top-0 right-0 w-full sm:w-[450px] h-full bg-dark-800 border-l border-dark-700 z-50 flex flex-col transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-dark-700 bg-gradient-to-r from-primary-500/10 to-transparent">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-primary-500" />
            Detail Produit
            {isLoading && <Loader2 className="w-4 h-4 animate-spin text-dark-400" />}
          </h2>
          <div className="flex gap-2">
            {onEdit && (
              <button
                className="w-9 h-9 rounded-lg bg-dark-700 hover:bg-dark-600 flex items-center justify-center text-dark-400 hover:text-white transition-colors"
                onClick={() => onEdit(product)}
                title="Modifier"
              >
                <Edit3 className="w-4 h-4" />
              </button>
            )}
            <button
              className="w-9 h-9 rounded-lg bg-dark-700 hover:bg-dark-600 flex items-center justify-center text-dark-400 hover:text-white transition-colors"
              onClick={onClose}
              title="Fermer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Body - Scrollable */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Hero Section - Identité produit */}
          <div className="flex gap-4">
            <div className="w-20 h-20 rounded-2xl bg-dark-700 border border-dark-600 flex items-center justify-center text-4xl">
              📦
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-xl font-semibold text-white truncate">{product.nom}</h3>
              <p className="text-sm text-dark-500 mt-1">
                ID #{product.produit_id} • SK {product.produit_sk}
              </p>
              <div className="flex gap-2 mt-3">
                {productData?.categorie_nom && (
                  <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-primary-500/20 text-primary-400">
                    {productData.categorie_nom}
                  </span>
                )}
                <span className={cn('px-2.5 py-1 rounded-md text-xs font-medium', stockStatus.bg, stockStatus.color)}>
                  {stockStatus.label}
                </span>
              </div>
            </div>
          </div>

          {/* KPIs Section - Information interprétée */}
          <div className="rounded-xl bg-dark-700/30 p-4">
            <h4 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-dark-400" />
              KPIs
            </h4>
            <div className="grid grid-cols-2 gap-3">
              <StatItem
                label="Stock actuel"
                value={`${productData?.stock_actuel || 0} u`}
                valueColor={stockStatus.color}
                isLoading={isLoading}
              />
              <StatItem
                label="Couverture"
                value={joursStockDisplay}
                trendType={productData?.jours_stock && productData.jours_stock < 7 ? 'down' : 'neutral'}
                trend={productData?.jours_stock && productData.jours_stock < 7 ? 'Attention' : undefined}
                isLoading={isLoading}
              />
              <StatItem
                label="Conso. moy 30j"
                value={productData?.conso_moy_30j ? `${Number(productData.conso_moy_30j).toFixed(1)} u/j` : '—'}
                isLoading={isLoading}
              />
              <StatItem
                label="Marge"
                value={margin ? `${margin.percent}%` : 'N/A'}
                valueColor={margin && parseInt(margin.percent) < 20 ? 'text-amber-400' : 'text-white'}
                trendType={margin && parseInt(margin.percent) >= 30 ? 'up' : margin && parseInt(margin.percent) < 20 ? 'down' : 'neutral'}
                trend={margin && parseInt(margin.percent) < 20 ? 'Sous objectif' : margin ? 'OK' : undefined}
              />
            </div>
          </div>

          {/* Prix Section - Données factuelles */}
          <div className="rounded-xl bg-dark-700/30 p-4">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              💰 Prix
            </h4>
            <PriceRow
              label="Prix d'achat HT"
              value={formatCurrency(productData?.prix_achat)}
            />
            <PriceRow
              label="Prix de vente TTC"
              value={formatCurrency(productData?.prix_vente)}
            />
            {margin && (
              <PriceRow
                label="Marge brute"
                value={`${formatCurrency(parseFloat(margin.value))} (${margin.percent}%)`}
                valueColor="text-green-400"
              />
            )}
            {productData?.tva_pct && (
              <PriceRow label="TVA" value={`${Number(productData.tva_pct).toFixed(1)}%`} />
            )}
          </div>

          {/* Stock Level - Jauge décisionnelle */}
          <div className="rounded-xl bg-dark-700/30 p-4">
            <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
              <Package className="w-4 h-4 text-dark-400" />
              Niveau de stock
            </h4>
            <StockLevelBar
              current={productData?.stock_actuel || 0}
              min={productData?.seuil_alerte || 10}
              max={Math.max((productData?.stock_actuel || 0) * 2, 100)}
            />
            {productData?.stock_valeur && (
              <p className="text-sm text-dark-400 mt-3">
                Valeur stock: <span className="text-white font-medium">{formatCurrency(productData.stock_valeur)}</span>
              </p>
            )}
          </div>

          {/* Mouvements récents - Historique pour tendance */}
          <div className="rounded-xl bg-dark-700/30 p-4">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              📋 Mouvements recents
            </h4>
            <div className="max-h-52 overflow-y-auto">
              {isLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 bg-dark-600 rounded animate-pulse" />
                  ))}
                </div>
              ) : productData?.mouvements_recents && productData.mouvements_recents.length > 0 ? (
                productData.mouvements_recents.map((movement, idx) => (
                  <MovementItem key={idx} movement={movement} />
                ))
              ) : (
                <p className="text-sm text-dark-500 text-center py-4">
                  Aucun mouvement recent
                </p>
              )}
            </div>
          </div>

          {/* Alertes décisionnelles */}
          {stockStatus.status !== 'ok' && (
            <div className={cn('rounded-xl p-4 flex items-center gap-3', stockStatus.bg)}>
              <AlertTriangle className={cn('w-5 h-5', stockStatus.color)} />
              <div>
                <p className={cn('font-medium', stockStatus.color)}>
                  {stockStatus.status === 'critical' ? 'Rupture de stock' : 'Stock bas'}
                </p>
                <p className="text-sm text-dark-300">
                  {stockStatus.status === 'critical'
                    ? 'Commander immediatement'
                    : 'Planifier un reapprovisionnement'}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer - Actions */}
        <div className="flex gap-3 px-6 py-5 border-t border-dark-700">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-lg bg-dark-700 text-dark-300 hover:bg-dark-600 hover:text-white transition-colors flex items-center justify-center gap-2"
          >
            <BarChart3 className="w-4 h-4" />
            Historique
          </button>
          {onOrder && (
            <button
              onClick={() => onOrder(product)}
              className="flex-1 px-4 py-2.5 rounded-lg bg-primary-500 text-white hover:bg-primary-600 transition-colors flex items-center justify-center gap-2"
            >
              <ShoppingCart className="w-4 h-4" />
              Commander
            </button>
          )}
        </div>
      </div>
    </>
  )
}
