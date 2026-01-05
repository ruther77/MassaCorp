/**
 * Hook pour les produits METRO extraits des factures fournisseur
 *
 * Charge les données depuis le fichier JSON généré par l'ETL METRO
 * et les transforme en format compatible avec le catalogue.
 */
import { useQuery } from '@tanstack/react-query'
import { ProduitListItem } from '@/api/catalog'

// Types METRO
interface MetroLigne {
  ean: string
  article_numero: string
  designation: string
  quantite: number
  prix_unitaire: number
  montant: number
  taux_tva: number
  code_tva: string
  regie: string | null
  vol_alcool: number | null
}

interface MetroFacture {
  numero: string
  date: string
  magasin: string
  total_ht: number
  lignes: MetroLigne[]
}

interface MetroData {
  summary: {
    nb_factures: number
    total_ht: number
    total_ttc: number
    total_lignes: number
  }
  factures: MetroFacture[]
}

export interface MetroProduit {
  ean: string
  designation: string
  prix_moyen: number
  quantite_totale: number
  montant_total: number
  nb_achats: number
  regie: string | null
  vol_alcool: number | null
  categorie: string
}

// Mapping régie -> catégorie
function getCategorie(regie: string | null): string {
  switch (regie) {
    case 'S': return 'Spiritueux'
    case 'B': return 'Bières'
    case 'T': return 'Vins'
    case 'M': return 'Alcools mixtes'
    default: return 'Epicerie'
  }
}

/**
 * Charge et agrège les produits METRO depuis le fichier JSON
 */
export function useMetroProducts() {
  return useQuery({
    queryKey: ['metro', 'products'],
    queryFn: async (): Promise<{ products: MetroProduit[]; summary: MetroData['summary'] }> => {
      const response = await fetch('/data/metro_data.json')
      if (!response.ok) {
        throw new Error('Impossible de charger les données METRO')
      }
      const data: MetroData = await response.json()

      // Agrégation des produits par EAN
      const produitMap = new Map<string, MetroProduit>()

      data.factures.forEach(f => {
        f.lignes.forEach(l => {
          const key = l.ean || l.article_numero
          const existing = produitMap.get(key)

          if (existing) {
            existing.quantite_totale += l.quantite
            existing.montant_total += l.montant || 0
            existing.nb_achats++
            existing.prix_moyen = existing.montant_total / existing.quantite_totale
          } else {
            produitMap.set(key, {
              ean: l.ean,
              designation: l.designation,
              prix_moyen: l.prix_unitaire,
              quantite_totale: l.quantite,
              montant_total: l.montant || 0,
              nb_achats: 1,
              regie: l.regie,
              vol_alcool: l.vol_alcool,
              categorie: getCategorie(l.regie),
            })
          }
        })
      })

      // Tri par montant total décroissant
      const products = Array.from(produitMap.values())
        .sort((a, b) => b.montant_total - a.montant_total)

      return { products, summary: data.summary }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  })
}

/**
 * Transforme les produits METRO en format ProduitListItem
 * pour compatibilité avec le catalogue existant
 */
export function useMetroProductsAsCatalog() {
  const { data, isLoading, isError, error } = useMetroProducts()

  const products: ProduitListItem[] = data?.products.map((p, idx) => ({
    produit_sk: idx + 10000, // Offset pour éviter collision avec produits DWH
    produit_id: parseInt(p.ean) || idx + 10000,
    nom: p.designation,
    categorie_id: null,
    categorie_nom: p.categorie,
    famille: p.regie ? `METRO - ${p.categorie}` : 'METRO - Epicerie',
    prix_achat: p.prix_moyen,
    prix_vente: null, // Pas de prix de vente dans les factures fournisseur
    marge_pct: null,
    stock_actuel: p.quantite_totale, // Quantité achetée
    seuil_alerte: null,
    est_rupture: false,
    jours_stock: null,
  })) || []

  const meta = {
    total: products.length,
    page: 1,
    pages: 1,
    per_page: products.length,
  }

  return {
    data: products,
    meta,
    summary: data?.summary,
    isLoading,
    isError,
    error,
  }
}

export default useMetroProducts
