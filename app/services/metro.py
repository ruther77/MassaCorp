"""
Service METRO pour MassaCorp
Logique métier pour les factures fournisseur METRO

Fonctionnalités:
- Import des données JSON vers PostgreSQL
- Calcul des agrégats produits avec TVA
- Requêtes catalogue et dashboard
"""
import json
import time
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc
from sqlalchemy.dialects.postgresql import insert

from app.models.metro import (
    MetroFacture,
    MetroLigne,
    MetroProduitAgregat,
    DimProduit,
    get_categorie,
    METRO_CATEGORIES
)
from app.schemas.metro import (
    MetroSummary,
    MetroCategoryStats,
    MetroTvaStats,
    MetroDashboard,
    MetroProduitResponse,
    MetroFactureResponse,
    MetroFactureListItem,
    MetroLigneResponse,
    MetroImportResult,
    MetroDataImport,
)


class MetroService:
    """
    Service pour la gestion des données METRO

    Contient la logique métier pour:
    - Import et parsing des factures
    - Calcul des agrégats produits
    - Calcul de la TVA
    - Requêtes catalogue et dashboard
    """

    # Taux de TVA français standards
    TVA_RATES = {
        20.0: "Taux normal",
        10.0: "Taux intermédiaire",
        5.5: "Taux réduit",
        2.1: "Taux super-réduit",
        0.0: "Exonéré",
    }

    def __init__(self, db: Session, tenant_id: int):
        """
        Initialise le service

        Args:
            db: Session SQLAlchemy
            tenant_id: ID du tenant
        """
        self.db = db
        self.tenant_id = tenant_id

    # =========================================================================
    # CALCULS TVA
    # =========================================================================

    @staticmethod
    def calculer_tva(montant_ht: Decimal, taux_tva: Decimal) -> Decimal:
        """
        Calcule le montant de TVA

        Args:
            montant_ht: Montant hors taxes
            taux_tva: Taux de TVA en pourcentage

        Returns:
            Montant de TVA arrondi à 2 décimales
        """
        tva = montant_ht * (taux_tva / Decimal(100))
        return tva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculer_ttc(montant_ht: Decimal, taux_tva: Decimal) -> Decimal:
        """
        Calcule le montant TTC

        Args:
            montant_ht: Montant hors taxes
            taux_tva: Taux de TVA en pourcentage

        Returns:
            Montant TTC arrondi à 2 décimales
        """
        ttc = montant_ht * (1 + taux_tva / Decimal(100))
        return ttc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def extraire_ht_depuis_ttc(montant_ttc: Decimal, taux_tva: Decimal) -> Decimal:
        """
        Extrait le montant HT à partir du TTC

        Args:
            montant_ttc: Montant TTC
            taux_tva: Taux de TVA en pourcentage

        Returns:
            Montant HT arrondi à 2 décimales
        """
        ht = montant_ttc / (1 + taux_tva / Decimal(100))
        return ht.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # =========================================================================
    # IMPORT DES DONNÉES
    # =========================================================================

    def importer_depuis_json(self, json_path: str) -> MetroImportResult:
        """
        Importe les données depuis un fichier JSON

        Args:
            json_path: Chemin vers le fichier metro_data.json

        Returns:
            Résultat de l'import
        """
        start_time = time.time()
        erreurs: List[str] = []

        try:
            # Lire le fichier JSON
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            nb_factures = 0
            nb_lignes = 0

            # Importer chaque facture
            for facture_data in data.get("factures", []):
                try:
                    facture, lignes_count = self._importer_facture(facture_data)
                    if facture:
                        nb_factures += 1
                        nb_lignes += lignes_count
                except Exception as e:
                    erreurs.append(f"Erreur facture {facture_data.get('numero', '?')}: {str(e)}")

            # Commit les factures
            self.db.commit()

            # Recalculer les agrégats
            nb_produits = self.recalculer_agregats()

            duree_ms = int((time.time() - start_time) * 1000)

            return MetroImportResult(
                success=True,
                nb_factures_importees=nb_factures,
                nb_lignes_importees=nb_lignes,
                nb_produits_agreges=nb_produits,
                erreurs=erreurs,
                duree_ms=duree_ms,
            )

        except Exception as e:
            self.db.rollback()
            duree_ms = int((time.time() - start_time) * 1000)
            return MetroImportResult(
                success=False,
                nb_factures_importees=0,
                nb_lignes_importees=0,
                nb_produits_agreges=0,
                erreurs=[f"Erreur globale: {str(e)}"],
                duree_ms=duree_ms,
            )

    def _importer_facture(self, facture_data: Dict) -> Tuple[Optional[MetroFacture], int]:
        """
        Importe une facture et ses lignes

        Args:
            facture_data: Données de la facture

        Returns:
            Tuple (facture créée, nombre de lignes)
        """
        numero = facture_data.get("numero", "")
        if not numero:
            return None, 0

        # Vérifier si la facture existe déjà
        existing = self.db.query(MetroFacture).filter(
            MetroFacture.tenant_id == self.tenant_id,
            MetroFacture.numero == numero
        ).first()

        if existing:
            # Mettre à jour ou ignorer
            return existing, len(existing.lignes)

        # Parser la date
        date_str = facture_data.get("date", "")
        try:
            date_facture = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            date_facture = date.today()

        # Calculer les totaux TVA
        lignes_data = facture_data.get("lignes", [])
        total_ht = Decimal(str(facture_data.get("total_ht", 0)))
        total_tva = Decimal(0)

        for ligne in lignes_data:
            montant = Decimal(str(ligne.get("montant", 0)))
            taux = Decimal(str(ligne.get("taux_tva", 20)))
            total_tva += self.calculer_tva(montant, taux)

        total_ttc = total_ht + total_tva

        # Créer la facture
        facture = MetroFacture(
            tenant_id=self.tenant_id,
            numero=numero,
            date_facture=date_facture,
            magasin=facture_data.get("magasin", "METRO"),
            total_ht=total_ht,
            total_tva=total_tva,
            total_ttc=total_ttc,
        )
        self.db.add(facture)
        self.db.flush()  # Pour obtenir l'ID

        # Ajouter les lignes
        for ligne_data in lignes_data:
            ligne = self._creer_ligne(facture.id, ligne_data)
            self.db.add(ligne)

        return facture, len(lignes_data)

    def _creer_ligne(self, facture_id: int, ligne_data: Dict) -> MetroLigne:
        """
        Crée une ligne de facture

        Args:
            facture_id: ID de la facture
            ligne_data: Données de la ligne

        Returns:
            Ligne créée
        """
        montant_ht = Decimal(str(ligne_data.get("montant", 0)))
        taux_tva = Decimal(str(ligne_data.get("taux_tva", 20)))
        montant_tva = self.calculer_tva(montant_ht, taux_tva)

        return MetroLigne(
            tenant_id=self.tenant_id,
            facture_id=facture_id,
            ean=ligne_data.get("ean", ""),
            article_numero=ligne_data.get("article_numero"),
            designation=ligne_data.get("designation", ""),
            quantite=Decimal(str(ligne_data.get("quantite", 0))),
            prix_unitaire=Decimal(str(ligne_data.get("prix_unitaire", 0))),
            montant_ht=montant_ht,
            taux_tva=taux_tva,
            code_tva=ligne_data.get("code_tva"),
            montant_tva=montant_tva,
            regie=ligne_data.get("regie"),
            vol_alcool=Decimal(str(ligne_data.get("vol_alcool", 0))) if ligne_data.get("vol_alcool") else None,
        )

    # =========================================================================
    # CALCUL DES AGRÉGATS
    # =========================================================================

    def recalculer_agregats(self) -> int:
        """
        Recalcule tous les agrégats produits à partir des lignes

        Returns:
            Nombre de produits agrégés
        """
        # Supprimer les anciens agrégats
        self.db.query(MetroProduitAgregat).filter(
            MetroProduitAgregat.tenant_id == self.tenant_id
        ).delete()

        # Calculer les nouveaux agrégats avec SQL
        query = text("""
            INSERT INTO dwh.metro_produit_agregat (
                tenant_id, ean, designation,
                quantite_totale, montant_total_ht, montant_total_tva, montant_total,
                nb_achats, prix_moyen, prix_min, prix_max, taux_tva,
                regie, vol_alcool, categorie,
                premier_achat, dernier_achat, calcule_le
            )
            SELECT
                l.tenant_id,
                l.ean,
                MAX(l.designation) as designation,
                SUM(l.quantite) as quantite_totale,
                SUM(l.montant_ht) as montant_total_ht,
                SUM(l.montant_tva) as montant_total_tva,
                SUM(l.montant_ht + l.montant_tva) as montant_total,
                COUNT(*) as nb_achats,
                AVG(l.prix_unitaire) as prix_moyen,
                MIN(l.prix_unitaire) as prix_min,
                MAX(l.prix_unitaire) as prix_max,
                MAX(l.taux_tva) as taux_tva,
                MAX(l.regie) as regie,
                MAX(l.vol_alcool) as vol_alcool,
                CASE
                    WHEN MAX(l.regie) = 'S' THEN 'Spiritueux'
                    WHEN MAX(l.regie) = 'B' THEN 'Bières'
                    WHEN MAX(l.regie) = 'T' THEN 'Vins'
                    WHEN MAX(l.regie) = 'M' THEN 'Alcools'
                    ELSE 'Epicerie'
                END as categorie,
                MIN(f.date_facture) as premier_achat,
                MAX(f.date_facture) as dernier_achat,
                NOW() as calcule_le
            FROM dwh.metro_ligne l
            JOIN dwh.metro_facture f ON l.facture_id = f.id
            WHERE l.tenant_id = :tenant_id
              AND l.ean IS NOT NULL
              AND l.ean != ''
            GROUP BY l.tenant_id, l.ean
        """)

        self.db.execute(query, {"tenant_id": self.tenant_id})
        self.db.commit()

        # Retourner le nombre de produits
        count = self.db.query(func.count(MetroProduitAgregat.id)).filter(
            MetroProduitAgregat.tenant_id == self.tenant_id
        ).scalar()

        return count or 0

    # =========================================================================
    # REQUÊTES CATALOGUE
    # =========================================================================

    def get_produits(
        self,
        page: int = 1,
        per_page: int = 50,
        q: Optional[str] = None,
        categorie: Optional[str] = None,
        taux_tva: Optional[Decimal] = None,
        sort_by: str = "montant_total",
        sort_order: str = "desc",
    ) -> Tuple[List[DimProduit], int]:
        """
        Récupère la liste des produits depuis dim_produit (référentiel maître)

        Args:
            page: Numéro de page
            per_page: Produits par page
            q: Recherche texte
            categorie: Filtre catégorie
            taux_tva: Filtre taux TVA
            sort_by: Colonne de tri
            sort_order: Ordre de tri

        Returns:
            Tuple (liste produits, total)
        """
        query = self.db.query(DimProduit).filter(DimProduit.actif == True)

        # Filtres
        if q:
            search = f"%{q.lower()}%"
            query = query.filter(
                (func.lower(DimProduit.designation_brute).like(search)) |
                (func.lower(DimProduit.nom_court).like(search)) |
                (func.lower(DimProduit.marque).like(search)) |
                (DimProduit.ean.like(search))
            )

        if categorie:
            query = query.filter(DimProduit.categorie == categorie)

        if taux_tva is not None:
            query = query.filter(DimProduit.taux_tva == taux_tva)

        # Total
        total = query.count()

        # Mapping des colonnes pour le tri
        sort_mapping = {
            "montant_total": DimProduit.montant_total_achats,
            "montant_total_ht": DimProduit.montant_total_achats,
            "prix_unitaire_moyen": DimProduit.prix_achat_unitaire,
            "quantite_unitaire_totale": DimProduit.quantite_totale_achetee,
            "nb_achats": DimProduit.nb_achats,
            "designation": DimProduit.nom_court,
        }
        sort_column = sort_mapping.get(sort_by, DimProduit.montant_total_achats)

        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        offset = (page - 1) * per_page
        produits = query.offset(offset).limit(per_page).all()

        return produits, total

    def get_produit(self, produit_id: int) -> Optional[DimProduit]:
        """
        Récupère un produit par ID

        Args:
            produit_id: ID du produit

        Returns:
            Produit ou None
        """
        return self.db.query(DimProduit).filter(
            DimProduit.id == produit_id,
            DimProduit.actif == True
        ).first()

    def get_produit_par_ean(self, ean: str) -> Optional[DimProduit]:
        """
        Récupère un produit par EAN

        Args:
            ean: Code EAN

        Returns:
            Produit ou None
        """
        return self.db.query(DimProduit).filter(
            DimProduit.ean == ean,
            DimProduit.actif == True
        ).first()

    # =========================================================================
    # REQUÊTES FACTURES
    # =========================================================================

    def get_factures(
        self,
        page: int = 1,
        per_page: int = 50,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
    ) -> Tuple[List[MetroFacture], int]:
        """
        Récupère la liste des factures

        Args:
            page: Numéro de page
            per_page: Factures par page
            date_debut: Date de début
            date_fin: Date de fin

        Returns:
            Tuple (liste factures, total)
        """
        query = self.db.query(MetroFacture).filter(
            MetroFacture.tenant_id == self.tenant_id
        )

        if date_debut:
            query = query.filter(MetroFacture.date_facture >= date_debut)
        if date_fin:
            query = query.filter(MetroFacture.date_facture <= date_fin)

        total = query.count()

        factures = query.order_by(desc(MetroFacture.date_facture)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        return factures, total

    def get_facture(self, facture_id: int) -> Optional[MetroFacture]:
        """
        Récupère une facture avec ses lignes

        Args:
            facture_id: ID de la facture

        Returns:
            Facture ou None
        """
        return self.db.query(MetroFacture).filter(
            MetroFacture.tenant_id == self.tenant_id,
            MetroFacture.id == facture_id
        ).first()

    # =========================================================================
    # DASHBOARD & STATISTIQUES
    # =========================================================================

    def get_summary(self) -> MetroSummary:
        """
        Récupère le résumé global

        Returns:
            Résumé METRO
        """
        # Compter les factures
        nb_factures = self.db.query(func.count(MetroFacture.id)).filter(
            MetroFacture.tenant_id == self.tenant_id
        ).scalar() or 0

        # Compter les produits depuis dim_produit
        nb_produits = self.db.query(func.count(DimProduit.id)).filter(
            DimProduit.actif == True
        ).scalar() or 0

        # Compter les lignes
        nb_lignes = self.db.query(func.count(MetroLigne.id)).filter(
            MetroLigne.tenant_id == self.tenant_id
        ).scalar() or 0

        # Totaux
        totaux = self.db.query(
            func.sum(MetroFacture.total_ht),
            func.sum(MetroFacture.total_tva),
            func.sum(MetroFacture.total_ttc),
            func.min(MetroFacture.date_facture),
            func.max(MetroFacture.date_facture),
        ).filter(
            MetroFacture.tenant_id == self.tenant_id
        ).first()

        return MetroSummary(
            nb_factures=nb_factures,
            nb_produits=nb_produits,
            nb_lignes=nb_lignes,
            total_ht=totaux[0] or Decimal(0),
            total_tva=totaux[1] or Decimal(0),
            total_ttc=totaux[2] or Decimal(0),
            date_premiere_facture=totaux[3],
            date_derniere_facture=totaux[4],
        )

    def get_stats_par_categorie(self) -> List[MetroCategoryStats]:
        """
        Récupère les statistiques par catégorie depuis dim_produit

        Returns:
            Liste des stats par catégorie
        """
        # Total global pour calculer les pourcentages
        total_global = self.db.query(
            func.sum(DimProduit.montant_total_achats)
        ).filter(
            DimProduit.actif == True
        ).scalar() or Decimal(1)

        # Stats par catégorie
        stats = self.db.query(
            DimProduit.categorie,
            func.count(DimProduit.id),
            func.sum(DimProduit.quantite_totale_achetee),
            func.sum(DimProduit.montant_total_achats),
        ).filter(
            DimProduit.actif == True
        ).group_by(
            DimProduit.categorie
        ).order_by(
            desc(func.sum(DimProduit.montant_total_achats))
        ).all()

        return [
            MetroCategoryStats(
                categorie=row[0],
                nb_produits=row[1],
                quantite_totale=row[2] or Decimal(0),
                montant_total_ht=row[3] or Decimal(0),
                montant_total_tva=Decimal(0),  # dim_produit n'a pas de TVA détaillée
                pct_ca=((row[3] or Decimal(0)) / total_global * 100).quantize(Decimal("0.1")),
            )
            for row in stats
        ]

    def get_stats_par_tva(self) -> List[MetroTvaStats]:
        """
        Récupère les statistiques par taux de TVA

        Returns:
            Liste des stats par taux TVA
        """
        total_global = self.db.query(
            func.sum(MetroLigne.montant_ht)
        ).filter(
            MetroLigne.tenant_id == self.tenant_id
        ).scalar() or Decimal(1)

        stats = self.db.query(
            MetroLigne.taux_tva,
            func.count(func.distinct(MetroLigne.ean)),
            func.sum(MetroLigne.montant_ht),
            func.sum(MetroLigne.montant_tva),
        ).filter(
            MetroLigne.tenant_id == self.tenant_id
        ).group_by(
            MetroLigne.taux_tva
        ).order_by(
            desc(MetroLigne.taux_tva)
        ).all()

        return [
            MetroTvaStats(
                taux_tva=row[0],
                nb_produits=row[1],
                montant_ht=row[2] or Decimal(0),
                montant_tva=row[3] or Decimal(0),
                pct_total=((row[2] or Decimal(0)) / total_global * 100).quantize(Decimal("0.1")),
            )
            for row in stats
        ]

    def get_top_produits(self, limit: int = 10) -> List[DimProduit]:
        """
        Récupère les top produits par montant depuis dim_produit

        Args:
            limit: Nombre de produits

        Returns:
            Liste des top produits
        """
        return self.db.query(DimProduit).filter(
            DimProduit.actif == True
        ).order_by(
            desc(DimProduit.montant_total_achats)
        ).limit(limit).all()

    def get_dashboard(self) -> MetroDashboard:
        """
        Récupère le dashboard complet

        Returns:
            Dashboard METRO
        """
        summary = self.get_summary()
        categories = self.get_stats_par_categorie()
        tva_breakdown = self.get_stats_par_tva()
        top_produits = self.get_top_produits(10)

        return MetroDashboard(
            summary=summary,
            categories=categories,
            tva_breakdown=tva_breakdown,
            top_produits=[
                MetroProduitResponse(
                    id=p.id,
                    ean=p.ean,
                    article_numero=p.article_numero,
                    designation=p.nom_court or p.designation_brute,
                    colisage_moyen=p.colisage_standard,
                    unite="U",
                    volume_unitaire=p.contenance_cl,
                    quantite_colis_totale=p.quantite_totale_achetee / p.colisage_standard if p.colisage_standard > 0 else p.quantite_totale_achetee,
                    quantite_unitaire_totale=p.quantite_totale_achetee,
                    montant_total_ht=p.montant_total_achats,
                    montant_total_tva=p.montant_total_achats * p.taux_tva / 100,
                    montant_total=p.montant_total_achats * (1 + p.taux_tva / 100),
                    nb_achats=p.nb_achats,
                    prix_unitaire_moyen=p.prix_achat_unitaire or Decimal(0),
                    prix_unitaire_min=p.prix_achat_unitaire or Decimal(0),
                    prix_unitaire_max=p.prix_achat_unitaire or Decimal(0),
                    prix_colis_moyen=p.prix_achat_colis or Decimal(0),
                    taux_tva=p.taux_tva,
                    famille=p.famille,
                    categorie=p.categorie,
                    sous_categorie=p.sous_categorie,
                    regie=p.regie,
                    vol_alcool=p.degre_alcool,
                    premier_achat=None,
                    dernier_achat=p.date_dernier_prix,
                )
                for p in top_produits
            ],
        )

    # =========================================================================
    # CATÉGORIES
    # =========================================================================

    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Récupère la liste des catégories avec compteurs depuis dim_produit

        Returns:
            Liste des catégories
        """
        stats = self.db.query(
            DimProduit.categorie,
            func.count(DimProduit.id),
        ).filter(
            DimProduit.actif == True
        ).group_by(
            DimProduit.categorie
        ).order_by(
            desc(func.count(DimProduit.id))
        ).all()

        return [
            {"categorie": row[0], "count": row[1]}
            for row in stats
        ]
