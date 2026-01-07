"""
Service TAIYAT pour MassaCorp
Logique métier pour les factures fournisseur TAI YAT DISTRIBUTION

Fonctionnalités:
- Import des données extraites par ETL vers PostgreSQL
- Calcul des agrégats produits
- Requêtes catalogue et dashboard
"""
import json
import time
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc
from sqlalchemy.dialects.postgresql import insert

from app.models.taiyat import (
    TaiyatFacture,
    TaiyatLigne,
    TaiyatProduitAgregat,
    categoriser_produit,
    TAIYAT_TVA_CODES
)
from app.models.metro import DimProduit


class TaiyatService:
    """
    Service pour la gestion des données TAIYAT

    Contient la logique métier pour:
    - Import des factures
    - Calcul des agrégats produits
    - Requêtes catalogue et dashboard
    """

    # Taux de TVA TAIYAT
    TVA_RATES = {
        5.5: "TVA réduite (alimentaire)",
        20.0: "TVA normale",
    }

    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id

    # =========================================================================
    # CALCULS TVA
    # =========================================================================

    @staticmethod
    def extraire_ht_depuis_ttc(montant_ttc: Decimal, taux_tva: Decimal) -> Decimal:
        """Extrait le montant HT à partir du TTC"""
        ht = montant_ttc / (1 + taux_tva / Decimal(100))
        return ht.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # =========================================================================
    # IMPORT DES DONNÉES
    # =========================================================================

    def importer_facture(self, facture_data: Dict[str, Any]) -> TaiyatFacture:
        """
        Importe une facture TAIYAT extraite par ETL.

        Args:
            facture_data: Dictionnaire avec les données de la facture

        Returns:
            TaiyatFacture créée
        """
        # Vérifier si facture existe déjà
        existing = self.db.query(TaiyatFacture).filter(
            TaiyatFacture.tenant_id == self.tenant_id,
            TaiyatFacture.numero == facture_data.get('numero_facture')
        ).first()

        if existing:
            # Supprimer pour réimporter
            self.db.delete(existing)
            self.db.flush()

        # Créer la facture
        facture = TaiyatFacture(
            tenant_id=self.tenant_id,
            numero=facture_data.get('numero_facture'),
            date_facture=datetime.strptime(facture_data.get('date_facture'), '%Y-%m-%d').date() if facture_data.get('date_facture') else None,
            client_nom=facture_data.get('client_nom', 'INCONNU'),
            client_code=facture_data.get('client_code'),
            total_ttc=Decimal(str(facture_data.get('total_ttc') or 0)),
            fichier_source=facture_data.get('source_file'),
        )
        self.db.add(facture)
        self.db.flush()

        # Importer les lignes
        for ligne_data in facture_data.get('lignes', []):
            taux_tva = Decimal(str(ligne_data.get('taux_tva', 5.5)))
            montant_ttc = Decimal(str(ligne_data.get('montant_ttc') or 0))
            montant_ht = self.extraire_ht_depuis_ttc(montant_ttc, taux_tva)

            ligne = TaiyatLigne(
                tenant_id=self.tenant_id,
                facture_id=facture.id,
                designation=ligne_data.get('designation', ''),
                designation_clean=self._normaliser_designation(ligne_data.get('designation', '')),
                provenance=ligne_data.get('provenance'),
                colis=ligne_data.get('colis', 1),
                pieces=ligne_data.get('pieces'),
                unite=ligne_data.get('unite', 'c'),
                prix_unitaire_ht=Decimal(str(ligne_data.get('prix_unitaire_ht') or 0)),
                prix_unitaire_ttc=Decimal(str(ligne_data.get('prix_unitaire_ttc') or 0)) if ligne_data.get('prix_unitaire_ttc') else None,
                montant_ttc=montant_ttc,
                montant_ht=montant_ht,
                code_tva=ligne_data.get('code_tva'),
                taux_tva=taux_tva,
                est_remise=ligne_data.get('est_remise', False),
            )
            self.db.add(ligne)

        return facture

    def _normaliser_designation(self, designation: str) -> str:
        """Normalise une désignation pour regroupement."""
        if not designation:
            return ""
        # Nettoyer et normaliser
        clean = designation.upper().strip()
        # Supprimer les chiffres de calibre/lot
        import re
        clean = re.sub(r'\d+[xX]\d+\s*(gr|g|kg|ml|l|cl)\b', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean[:200]

    def importer_depuis_etl(self, factures: List[Dict]) -> Dict[str, Any]:
        """
        Importe les factures depuis l'ETL.

        Args:
            factures: Liste de dictionnaires de factures

        Returns:
            Statistiques d'import
        """
        start_time = time.time()
        nb_factures = 0
        nb_lignes = 0
        erreurs = []

        for facture_data in factures:
            try:
                facture = self.importer_facture(facture_data)
                nb_factures += 1
                nb_lignes += len(facture_data.get('lignes', []))
            except Exception as e:
                erreurs.append(f"Facture {facture_data.get('numero_facture')}: {str(e)}")

        self.db.commit()

        return {
            "factures_importees": nb_factures,
            "lignes_importees": nb_lignes,
            "erreurs": erreurs,
            "duree_secondes": round(time.time() - start_time, 2)
        }

    # =========================================================================
    # STATISTIQUES ET DASHBOARD
    # =========================================================================

    def get_summary(self) -> Dict[str, Any]:
        """Retourne le résumé des données TAIYAT."""
        stats = self.db.query(
            func.count(TaiyatFacture.id).label('nb_factures'),
            func.sum(TaiyatFacture.total_ttc).label('total_ttc'),
            func.min(TaiyatFacture.date_facture).label('premiere_facture'),
            func.max(TaiyatFacture.date_facture).label('derniere_facture'),
        ).filter(
            TaiyatFacture.tenant_id == self.tenant_id
        ).first()

        nb_lignes = self.db.query(func.count(TaiyatLigne.id)).filter(
            TaiyatLigne.tenant_id == self.tenant_id
        ).scalar() or 0

        nb_produits = self.db.query(
            func.count(func.distinct(TaiyatLigne.designation_clean))
        ).filter(
            TaiyatLigne.tenant_id == self.tenant_id
        ).scalar() or 0

        return {
            "fournisseur": "TAI YAT DISTRIBUTION",
            "siret": "443695598",
            "nb_factures": stats.nb_factures or 0,
            "nb_lignes": nb_lignes,
            "nb_produits": nb_produits,
            "total_ttc": float(stats.total_ttc or 0),
            "premiere_facture": stats.premiere_facture.isoformat() if stats.premiere_facture else None,
            "derniere_facture": stats.derniere_facture.isoformat() if stats.derniere_facture else None,
        }

    def get_stats_par_client(self) -> Dict[str, Any]:
        """Retourne les statistiques par client (NOUTAM, INCONTOURNABLE)."""
        stats = self.db.query(
            TaiyatFacture.client_nom,
            func.count(TaiyatFacture.id).label('count'),
            func.sum(TaiyatFacture.total_ttc).label('total_ttc'),
        ).filter(
            TaiyatFacture.tenant_id == self.tenant_id
        ).group_by(
            TaiyatFacture.client_nom
        ).order_by(desc(func.sum(TaiyatFacture.total_ttc))).all()

        clients = [
            {
                "client_nom": row.client_nom or "Non identifié",
                "count": row.count,
                "total_ttc": float(row.total_ttc or 0)
            }
            for row in stats
        ]
        return {"clients": clients}

    def get_stats_par_provenance(self) -> Dict[str, Any]:
        """Retourne les statistiques par pays d'origine."""
        stats = self.db.query(
            TaiyatLigne.provenance,
            func.count(TaiyatLigne.id).label('count'),
            func.sum(TaiyatLigne.montant_ttc).label('total_ttc'),
        ).filter(
            TaiyatLigne.tenant_id == self.tenant_id,
            TaiyatLigne.provenance.isnot(None)
        ).group_by(
            TaiyatLigne.provenance
        ).order_by(desc(func.sum(TaiyatLigne.montant_ttc))).all()

        provenances = [
            {
                "provenance": row.provenance,
                "count": row.count,
                "total_ttc": float(row.total_ttc or 0)
            }
            for row in stats
        ]
        return {"provenances": provenances}

    def get_factures(
        self,
        page: int = 1,
        per_page: int = 20,
        client: Optional[str] = None,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Retourne la liste des factures avec pagination."""
        query = self.db.query(TaiyatFacture).filter(
            TaiyatFacture.tenant_id == self.tenant_id
        )

        if client:
            query = query.filter(TaiyatFacture.client_nom == client)
        if date_debut:
            query = query.filter(TaiyatFacture.date_facture >= date_debut)
        if date_fin:
            query = query.filter(TaiyatFacture.date_facture <= date_fin)

        total = query.count()
        factures = query.order_by(desc(TaiyatFacture.date_facture)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        return {
            "items": [
                {
                    "id": f.id,
                    "numero": f.numero,
                    "date_facture": f.date_facture.isoformat() if f.date_facture else None,
                    "client_nom": f.client_nom,
                    "total_ttc": float(f.total_ttc or 0),
                    "nb_lignes": len(f.lignes),
                    "fichier_source": f.fichier_source,
                }
                for f in factures
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }

    def get_facture_detail(self, facture_id: int) -> Optional[Dict[str, Any]]:
        """Retourne le détail d'une facture avec ses lignes."""
        facture = self.db.query(TaiyatFacture).filter(
            TaiyatFacture.tenant_id == self.tenant_id,
            TaiyatFacture.id == facture_id
        ).first()

        if not facture:
            return None

        return {
            "id": facture.id,
            "numero": facture.numero,
            "date_facture": facture.date_facture.isoformat() if facture.date_facture else None,
            "echeance": facture.echeance.isoformat() if facture.echeance else None,
            "client_nom": facture.client_nom,
            "client_code": facture.client_code,
            "total_ht": float(facture.total_ht or 0),
            "total_tva": float(facture.total_tva or 0),
            "total_ttc": float(facture.total_ttc or 0),
            "fichier_source": facture.fichier_source,
            "lignes": [
                {
                    "id": l.id,
                    "designation": l.designation,
                    "provenance": l.provenance,
                    "colis": l.colis,
                    "pieces": l.pieces,
                    "prix_unitaire_ht": float(l.prix_unitaire_ht or 0),
                    "montant_ttc": float(l.montant_ttc or 0),
                    "taux_tva": float(l.taux_tva or 0),
                    "est_remise": l.est_remise,
                }
                for l in facture.lignes
            ],
        }

    def get_top_produits(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne les produits les plus achetés."""
        stats = self.db.query(
            TaiyatLigne.designation_clean,
            TaiyatLigne.provenance,
            func.count(TaiyatLigne.id).label('nb_achats'),
            func.sum(TaiyatLigne.colis).label('total_colis'),
            func.sum(TaiyatLigne.montant_ttc).label('total_ttc'),
            func.avg(TaiyatLigne.prix_unitaire_ht).label('prix_moyen'),
        ).filter(
            TaiyatLigne.tenant_id == self.tenant_id,
            TaiyatLigne.designation_clean.isnot(None),
            TaiyatLigne.est_remise == False,
        ).group_by(
            TaiyatLigne.designation_clean,
            TaiyatLigne.provenance
        ).order_by(desc(func.sum(TaiyatLigne.montant_ttc))).limit(limit).all()

        return [
            {
                "designation": row.designation_clean,
                "provenance": row.provenance,
                "nb_achats": row.nb_achats,
                "total_colis": int(row.total_colis or 0),
                "total_ttc": float(row.total_ttc or 0),
                "prix_moyen": float(row.prix_moyen or 0),
            }
            for row in stats
        ]

    def get_products(
        self,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        provenance: Optional[str] = None,
        sort_by: str = "montant_total",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Retourne la liste paginée des produits agrégés."""
        query = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id
        )

        # Filtres - recherche multi-champs et multi-mots
        if search:
            # Normaliser et splitter les termes de recherche
            search_terms = search.strip().lower().split()
            for term in search_terms:
                pattern = f"%{term}%"
                query = query.filter(
                    (TaiyatProduitAgregat.designation_clean.ilike(pattern)) |
                    (TaiyatProduitAgregat.designation_brute.ilike(pattern)) |
                    (TaiyatProduitAgregat.ean.ilike(pattern)) |
                    (TaiyatProduitAgregat.provenance.ilike(pattern))
                )
        if provenance:
            query = query.filter(TaiyatProduitAgregat.provenance == provenance)

        # Tri
        sort_column = getattr(TaiyatProduitAgregat, sort_by, TaiyatProduitAgregat.montant_total)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        total = query.count()
        products = query.offset((page - 1) * per_page).limit(per_page).all()

        return {
            "items": [
                {
                    "id": p.id,
                    "ean": p.ean,
                    "designation": p.designation_brute,
                    "designation_clean": p.designation_clean,
                    "provenance": p.provenance,
                    "quantite_colis": float(p.quantite_colis_totale or 0),
                    "quantite_pieces": float(p.quantite_pieces_totale or 0) if p.quantite_pieces_totale else None,
                    "nb_achats": p.nb_achats,
                    "montant_total_ht": float(p.montant_total_ht or 0),
                    "montant_total_tva": float(p.montant_total_tva or 0),
                    "montant_total": float(p.montant_total or 0),
                    "prix_moyen_ht": float(p.prix_moyen_ht or 0),
                    "prix_min_ht": float(p.prix_min_ht or 0),
                    "prix_max_ht": float(p.prix_max_ht or 0),
                    "taux_tva": float(p.taux_tva or 5.5),
                    "famille": p.famille,
                    "categorie": p.categorie,
                    "sous_categorie": p.sous_categorie,
                    "dim_produit_id": p.dim_produit_id,
                    "premier_achat": p.premier_achat.isoformat() if p.premier_achat else None,
                    "dernier_achat": p.dernier_achat.isoformat() if p.dernier_achat else None,
                }
                for p in products
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }

    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Retourne un produit agrégé par son ID."""
        p = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id,
            TaiyatProduitAgregat.id == product_id
        ).first()

        if not p:
            return None

        return {
            "id": p.id,
            "ean": p.ean,
            "designation": p.designation_brute,
            "designation_clean": p.designation_clean,
            "provenance": p.provenance,
            "prix_moyen_kg": float(p.prix_moyen_ht or 0),
            "montant_total": float(p.montant_total or 0),
        }

    # =========================================================================
    # CALCUL DES AGRÉGATS
    # =========================================================================

    def recalculer_agregats(self) -> int:
        """
        Recalcule tous les agrégats produits à partir des lignes TAIYAT.

        Returns:
            Nombre de produits agrégés
        """
        # Supprimer les anciens agrégats
        self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id
        ).delete()

        # Calculer les nouveaux agrégats avec SQL
        # Inclut EAN si renseigné dans les lignes, et catégorisation automatique
        query = text("""
            INSERT INTO dwh.taiyat_produit_agregat (
                tenant_id, ean, designation_brute, designation_clean, provenance,
                quantite_colis_totale, quantite_pieces_totale, nb_achats,
                montant_total_ht, montant_total_tva, montant_total,
                prix_moyen_ht, prix_min_ht, prix_max_ht,
                taux_tva, categorie_id, famille, categorie, sous_categorie,
                premier_achat, dernier_achat, calcule_le
            )
            SELECT
                l.tenant_id,
                -- EAN: prendre celui renseigné (le plus récent non-null)
                (SELECT l2.ean FROM dwh.taiyat_ligne l2
                 JOIN dwh.taiyat_facture f2 ON l2.facture_id = f2.id
                 WHERE l2.designation_clean = l.designation_clean AND l2.tenant_id = l.tenant_id
                   AND l2.ean IS NOT NULL
                 ORDER BY f2.date_facture DESC LIMIT 1) as ean,
                -- Prendre la désignation originale la plus fréquente
                (SELECT l2.designation FROM dwh.taiyat_ligne l2
                 WHERE l2.designation_clean = l.designation_clean AND l2.tenant_id = l.tenant_id
                 GROUP BY l2.designation ORDER BY COUNT(*) DESC LIMIT 1) as designation_brute,
                l.designation_clean,
                -- Provenance la plus fréquente
                (SELECT l2.provenance FROM dwh.taiyat_ligne l2
                 WHERE l2.designation_clean = l.designation_clean AND l2.tenant_id = l.tenant_id
                   AND l2.provenance IS NOT NULL
                 GROUP BY l2.provenance ORDER BY COUNT(*) DESC LIMIT 1) as provenance,
                COALESCE(SUM(l.colis), 0) as quantite_colis_totale,
                SUM(l.pieces) as quantite_pieces_totale,
                COUNT(*) as nb_achats,
                SUM(l.montant_ht) as montant_total_ht,
                SUM(l.montant_ttc - l.montant_ht) as montant_total_tva,
                SUM(l.montant_ttc) as montant_total,
                AVG(l.prix_unitaire_ht) as prix_moyen_ht,
                MIN(l.prix_unitaire_ht) as prix_min_ht,
                MAX(l.prix_unitaire_ht) as prix_max_ht,
                MAX(l.taux_tva) as taux_tva,
                NULL as categorie_id,
                'EPICERIE' as famille,
                'Alimentaire' as categorie,
                NULL as sous_categorie,
                MIN(f.date_facture) as premier_achat,
                MAX(f.date_facture) as dernier_achat,
                NOW() as calcule_le
            FROM dwh.taiyat_ligne l
            JOIN dwh.taiyat_facture f ON l.facture_id = f.id
            WHERE l.tenant_id = :tenant_id
              AND l.designation_clean IS NOT NULL
              AND l.designation_clean != ''
              AND l.est_remise = false
            GROUP BY l.tenant_id, l.designation_clean
        """)

        self.db.execute(query, {"tenant_id": self.tenant_id})
        self.db.commit()

        # Compter les résultats
        count = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id
        ).count()

        # Appliquer la catégorisation automatique basée sur les mots-clés
        self._appliquer_categorisation()

        return count

    def _appliquer_categorisation(self) -> None:
        """Applique la catégorisation automatique basée sur la désignation."""
        produits = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id
        ).all()

        for produit in produits:
            famille, categorie, sous_cat = categoriser_produit(produit.designation_brute)
            produit.famille = famille
            produit.categorie = categorie
            produit.sous_categorie = sous_cat

        self.db.commit()

    # =========================================================================
    # GESTION EAN
    # =========================================================================

    def set_product_ean(self, produit_id: int, ean: Optional[str]) -> Optional[TaiyatProduitAgregat]:
        """
        Met à jour l'EAN d'un produit agrégé.

        Args:
            produit_id: ID du produit agrégé
            ean: Code EAN (ou None pour supprimer)

        Returns:
            Le produit mis à jour ou None si non trouvé
        """
        produit = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id,
            TaiyatProduitAgregat.id == produit_id
        ).first()

        if not produit:
            return None

        # Valider le format EAN si fourni
        if ean:
            ean = ean.strip()
            if len(ean) < 8 or len(ean) > 14:
                raise ValueError("L'EAN doit faire entre 8 et 14 caractères")

        produit.ean = ean
        self.db.commit()

        return produit

    def get_produit_by_id(self, produit_id: int) -> Optional[Dict[str, Any]]:
        """Retourne les détails d'un produit agrégé."""
        produit = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id,
            TaiyatProduitAgregat.id == produit_id
        ).first()

        if not produit:
            return None

        return {
            "id": produit.id,
            "ean": produit.ean,
            "designation": produit.designation_brute,
            "designation_clean": produit.designation_clean,
            "provenance": produit.provenance,
            "quantite_colis": float(produit.quantite_colis_totale or 0),
            "quantite_pieces": float(produit.quantite_pieces_totale or 0) if produit.quantite_pieces_totale else None,
            "nb_achats": produit.nb_achats,
            "montant_total_ht": float(produit.montant_total_ht or 0),
            "montant_total_tva": float(produit.montant_total_tva or 0),
            "montant_total": float(produit.montant_total or 0),
            "prix_moyen_ht": float(produit.prix_moyen_ht or 0),
            "prix_min_ht": float(produit.prix_min_ht or 0),
            "prix_max_ht": float(produit.prix_max_ht or 0),
            "taux_tva": float(produit.taux_tva or 5.5),
            "famille": produit.famille,
            "categorie": produit.categorie,
            "sous_categorie": produit.sous_categorie,
            "dim_produit_id": produit.dim_produit_id,
            "premier_achat": produit.premier_achat.isoformat() if produit.premier_achat else None,
            "dernier_achat": produit.dernier_achat.isoformat() if produit.dernier_achat else None,
        }

    # =========================================================================
    # SYNCHRONISATION VERS DIM_PRODUIT
    # =========================================================================

    def sync_to_dim_produit(self) -> Dict[str, int]:
        """
        Synchronise les produits TAIYAT vers la table dim_produit.

        Pour chaque produit agrégé TAIYAT:
        - Si EAN renseigné: vérifie s'il existe dans dim_produit, crée ou met à jour
        - Si EAN absent: crée une entrée avec EAN généré (TAIY-{id})

        Returns:
            Statistiques de synchronisation
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}

        produits = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id
        ).all()

        for produit in produits:
            # Générer un EAN si absent
            ean_to_use = produit.ean
            if not ean_to_use:
                # Générer un identifiant unique pour les produits sans EAN
                ean_to_use = f"TAIY{produit.id:010d}"

            # Chercher si le produit existe déjà dans dim_produit
            dim_produit = self.db.query(DimProduit).filter(
                DimProduit.ean == ean_to_use
            ).first()

            if dim_produit:
                # Mettre à jour les agrégats
                dim_produit.nb_achats = (dim_produit.nb_achats or 0) + produit.nb_achats
                dim_produit.quantite_totale_achetee = (
                    (dim_produit.quantite_totale_achetee or Decimal(0)) +
                    produit.quantite_colis_totale
                )
                dim_produit.montant_total_achats = (
                    (dim_produit.montant_total_achats or Decimal(0)) +
                    (produit.montant_total_ht or Decimal(0))
                )
                # Mettre à jour le prix si plus récent
                if produit.dernier_achat and (
                    not dim_produit.date_dernier_prix or
                    produit.dernier_achat > dim_produit.date_dernier_prix
                ):
                    dim_produit.prix_achat_unitaire = produit.prix_moyen_ht
                    dim_produit.date_dernier_prix = produit.dernier_achat

                # Lier le produit TAIYAT à dim_produit
                produit.dim_produit_id = dim_produit.id
                stats["updated"] += 1
            else:
                # Créer une nouvelle entrée dans dim_produit
                nouveau_produit = DimProduit(
                    ean=ean_to_use,
                    designation_brute=produit.designation_brute,
                    designation_clean=produit.designation_clean,
                    famille=produit.famille,
                    categorie=produit.categorie,
                    sous_categorie=produit.sous_categorie,
                    taux_tva=produit.taux_tva,
                    colisage_standard=1,
                    prix_achat_unitaire=produit.prix_moyen_ht,
                    date_dernier_prix=produit.dernier_achat,
                    nb_achats=produit.nb_achats,
                    quantite_totale_achetee=produit.quantite_colis_totale,
                    montant_total_achats=produit.montant_total_ht or Decimal(0),
                    source="TAIYAT",
                    actif=True,
                )
                self.db.add(nouveau_produit)
                self.db.flush()

                # Lier le produit TAIYAT à dim_produit
                produit.dim_produit_id = nouveau_produit.id
                stats["created"] += 1

        self.db.commit()
        return stats

    def get_products_without_ean(self) -> List[Dict[str, Any]]:
        """Retourne la liste des produits sans EAN (à renseigner manuellement)."""
        produits = self.db.query(TaiyatProduitAgregat).filter(
            TaiyatProduitAgregat.tenant_id == self.tenant_id,
            TaiyatProduitAgregat.ean.is_(None)
        ).order_by(desc(TaiyatProduitAgregat.montant_total)).all()

        return [
            {
                "id": p.id,
                "designation": p.designation_brute,
                "designation_clean": p.designation_clean,
                "provenance": p.provenance,
                "nb_achats": p.nb_achats,
                "montant_total": float(p.montant_total or 0),
            }
            for p in produits
        ]
