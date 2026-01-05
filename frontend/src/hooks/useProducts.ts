/**
 * Hooks Catalogue Produits
 *
 * Architecture SID - Couche Restitution:
 * - Données brutes (DWH) -> TanStack Query (cache) -> UI Components
 * - Normalisation automatique des formats API
 * - Gestion optimiste pour UX réactive
 */
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { catalogApi, CatalogFilters } from '@/api/catalog'

// ============================================================================
// QUERY KEYS - Clés de cache cohérentes
// ============================================================================

export const catalogKeys = {
  all: ['catalog'] as const,
  products: () => [...catalogKeys.all, 'products'] as const,
  productList: (filters: CatalogFilters) => [...catalogKeys.products(), filters] as const,
  productDetail: (id: number) => [...catalogKeys.all, 'product', id] as const,
  families: () => [...catalogKeys.all, 'families'] as const,
}

// ============================================================================
// HOOKS
// ============================================================================

/**
 * Hook pour la liste des produits avec pagination et filtres
 *
 * Transformation données -> information:
 * - Normalise la réponse API paginée
 * - Conserve les données précédentes pendant le chargement (UX fluide)
 * - Cache 2 minutes (données DWH stables)
 *
 * @param filters - Critères de filtrage (pagination, recherche, famille, stock, marge)
 * @returns Query avec liste produits normalisée et métadonnées pagination
 *
 * @example
 * const { data, isLoading, meta } = useProducts({
 *   page: 1,
 *   per_page: 20,
 *   stock_status: 'rupture'
 * })
 */
export function useProducts(filters: CatalogFilters = {}) {
  const query = useQuery({
    queryKey: catalogKeys.productList(filters),
    queryFn: () => catalogApi.getProducts(filters),
    placeholderData: (previousData) => previousData, // keepPreviousData v5
    staleTime: 2 * 60 * 1000, // 2 minutes - données DWH relativement stables
    refetchOnWindowFocus: false,
  })

  // Normalisation: extraction items et meta
  const data = query.data?.items || []
  const meta = query.data
    ? {
        total: query.data.total,
        page: query.data.page,
        pages: query.data.pages,
        per_page: query.data.per_page,
      }
    : { total: 0, page: 1, pages: 0, per_page: filters.per_page || 50 }

  return {
    ...query,
    data,
    meta,
  }
}

/**
 * Hook pour le détail enrichi d'un produit
 *
 * Information interprétée pour décision:
 * - KPIs stock (couverture, rupture, surstock)
 * - Performance (marge, ventes 30j)
 * - Historique mouvements (tendance)
 *
 * @param produitSk - Surrogate key du produit (DWH)
 * @returns Query avec détail produit enrichi
 *
 * @example
 * const { data: product, isLoading } = useProductDetail(42)
 *
 * // Indicateurs décisionnels
 * if (product?.est_rupture) showAlert('Rupture stock!')
 * if (product?.marge_pct && product.marge_pct < 20) showWarning('Marge faible')
 */
export function useProductDetail(produitSk: number | null) {
  return useQuery({
    queryKey: catalogKeys.productDetail(produitSk!),
    queryFn: () => catalogApi.getProductDetail(produitSk!),
    enabled: produitSk !== null && produitSk !== undefined,
    staleTime: 30 * 1000, // 30 secondes - données plus dynamiques
    refetchOnWindowFocus: true, // Rafraîchir au retour sur l'onglet
  })
}

/**
 * Hook pour la liste des familles (dimension hiérarchique)
 *
 * Utilisé pour:
 * - Filtres SmartFilters
 * - Navigation par catégorie
 * - Analyse par famille
 */
export function useFamilies() {
  return useQuery({
    queryKey: catalogKeys.families(),
    queryFn: () => catalogApi.getFamilies(),
    staleTime: 5 * 60 * 1000, // 5 minutes - dimension stable
    refetchOnWindowFocus: false,
  })
}

/**
 * Hook pour invalider le cache catalogue
 *
 * Utilisé après mutations (création, modification, suppression)
 * pour garantir la cohérence des données affichées.
 */
export function useInvalidateCatalog() {
  const queryClient = useQueryClient()

  return {
    invalidateProducts: () =>
      queryClient.invalidateQueries({ queryKey: catalogKeys.products() }),
    invalidateProduct: (id: number) =>
      queryClient.invalidateQueries({ queryKey: catalogKeys.productDetail(id) }),
    invalidateAll: () =>
      queryClient.invalidateQueries({ queryKey: catalogKeys.all }),
  }
}

export default useProducts
