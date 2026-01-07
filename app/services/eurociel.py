"""
Service EUROCIEL pour MassaCorp
Logique metier pour les factures fournisseur EUROCIEL

Fournisseur: EUROCIEL (grossiste alimentaire africain/tropical)
SIRET: 510154313
TVA: FR55510154313

Fonctionnalites:
- Import des donnees extraites par ETL vers PostgreSQL
- Calcul des agregats produits
- Requetes catalogue et dashboard
"""
import time
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text, func, desc, asc

from app.models.eurociel import (
    EurocielFacture,
    EurocielLigne,
    EurocielProduitAgregat,
    categoriser_produit_eurociel,
    EUROCIEL_TVA_CODES
)
from app.models.metro import DimProduit


class EurocielService:
    """
    Service pour la gestion des donnees EUROCIEL

    Contient la logique metier pour:
    - Import des factures
    - Calcul des agregats produits
    - Requetes catalogue et dashboard
    """

    # Taux de TVA EUROCIEL
    TVA_RATES = {
        5.5: "TVA reduite (alimentaire)",
        20.0: "TVA normale",
    }

    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id

    # =========================================================================
    # CALCULS TVA
    # =========================================================================

    @staticmethod
    def calculer_tva(montant_ht: Decimal, taux_tva: Decimal) -> Decimal:
        """Calcule le montant TVA a partir du HT"""
        tva = montant_ht * taux_tva / Decimal(100)
        return tva.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def calculer_ttc(montant_ht: Decimal, taux_tva: Decimal) -> Decimal:
        """Calcule le montant TTC a partir du HT"""
        ttc = montant_ht * (1 + taux_tva / Decimal(100))
        return ttc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # =========================================================================
    # IMPORT DES DONNEES
    # =========================================================================

    def importer_facture(self, facture_data: Dict[str, Any]) -> EurocielFacture:
        """
        Importe une facture EUROCIEL extraite par ETL.

        Args:
            facture_data: Dictionnaire avec les donnees de la facture

        Returns:
            EurocielFacture creee
        """
        # Verifier si facture existe deja
        existing = self.db.query(EurocielFacture).filter(
            EurocielFacture.tenant_id == self.tenant_id,
            EurocielFacture.numero == facture_data.get('numero_facture')
        ).first()

        if existing:
            # Supprimer pour reimporter
            self.db.delete(existing)
            self.db.flush()

        # Calculer totaux depuis les lignes
        lignes = facture_data.get('lignes', [])
        total_ht = sum(Decimal(str(l.get('montant_ht') or 0)) for l in lignes)
        total_poids = sum(Decimal(str(l.get('poids') or 0)) for l in lignes)
        total_quantite = sum(Decimal(str(l.get('quantite') or 0)) for l in lignes)

        # Calculer TVA par code
        total_tva = Decimal(0)
        for l in lignes:
            montant_ht = Decimal(str(l.get('montant_ht') or 0))
            taux_tva = Decimal(str(l.get('taux_tva') or 5.5))
            total_tva += self.calculer_tva(montant_ht, taux_tva)

        total_ttc = total_ht + total_tva

        # Creer la facture
        facture = EurocielFacture(
            tenant_id=self.tenant_id,
            numero=facture_data.get('numero_facture'),
            type_document=facture_data.get('type_document', 'FA'),
            date_facture=datetime.strptime(facture_data.get('date_facture'), '%Y-%m-%d').date() if facture_data.get('date_facture') else None,
            client_nom=facture_data.get('client_nom', 'INCONNU'),
            client_code=facture_data.get('client_code'),
            client_adresse=facture_data.get('client_adresse'),
            client_telephone=facture_data.get('client_telephone'),
            total_ht=total_ht,
            total_tva=total_tva,
            total_ttc=facture_data.get('total_ttc') or total_ttc,
            poids_total=total_poids if total_poids > 0 else None,
            quantite_totale=total_quantite if total_quantite > 0 else None,
            fichier_source=facture_data.get('source_file'),
            page_source=facture_data.get('page_source'),
        )
        self.db.add(facture)
        self.db.flush()

        # Importer les lignes
        for idx, ligne_data in enumerate(lignes, 1):
            taux_tva = Decimal(str(ligne_data.get('taux_tva', 5.5)))
            montant_ht = Decimal(str(ligne_data.get('montant_ht') or 0))
            montant_tva = self.calculer_tva(montant_ht, taux_tva)
            montant_ttc = self.calculer_ttc(montant_ht, taux_tva)

            ligne = EurocielLigne(
                tenant_id=self.tenant_id,
                facture_id=facture.id,
                numero_ligne=idx,
                designation=ligne_data.get('designation', ''),
                designation_clean=self._normaliser_designation(ligne_data.get('designation', '')),
                quantite=Decimal(str(ligne_data.get('quantite') or 1)),
                poids=Decimal(str(ligne_data.get('poids') or 0)) if ligne_data.get('poids') else None,
                prix_unitaire=Decimal(str(ligne_data.get('prix_unitaire') or 0)),
                montant_ht=montant_ht,
                code_tva=ligne_data.get('code_tva', 'C07'),
                taux_tva=taux_tva,
                montant_tva=montant_tva,
                montant_ttc=montant_ttc,
                est_promo=ligne_data.get('est_promo', False),
            )
            self.db.add(ligne)

        return facture

    def _normaliser_designation(self, designation: str) -> str:
        """Normalise une designation pour regroupement."""
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
        """Retourne le resume des donnees EUROCIEL."""
        stats = self.db.query(
            func.count(EurocielFacture.id).label('nb_factures'),
            func.sum(EurocielFacture.total_ht).label('total_ht'),
            func.sum(EurocielFacture.total_ttc).label('total_ttc'),
            func.sum(EurocielFacture.poids_total).label('poids_total'),
            func.min(EurocielFacture.date_facture).label('premiere_facture'),
            func.max(EurocielFacture.date_facture).label('derniere_facture'),
        ).filter(
            EurocielFacture.tenant_id == self.tenant_id
        ).first()

        nb_lignes = self.db.query(func.count(EurocielLigne.id)).filter(
            EurocielLigne.tenant_id == self.tenant_id
        ).scalar() or 0

        nb_produits = self.db.query(
            func.count(func.distinct(EurocielLigne.designation_clean))
        ).filter(
            EurocielLigne.tenant_id == self.tenant_id
        ).scalar() or 0

        # Compter factures et avoirs
        nb_factures_fa = self.db.query(func.count(EurocielFacture.id)).filter(
            EurocielFacture.tenant_id == self.tenant_id,
            EurocielFacture.type_document == 'FA'
        ).scalar() or 0

        nb_avoirs = self.db.query(func.count(EurocielFacture.id)).filter(
            EurocielFacture.tenant_id == self.tenant_id,
            EurocielFacture.type_document == 'AV'
        ).scalar() or 0

        return {
            "fournisseur": "EUROCIEL",
            "siret": "510154313",
            "tva_intra": "FR55510154313",
            "nb_factures": stats.nb_factures or 0,
            "nb_factures_fa": nb_factures_fa,
            "nb_avoirs": nb_avoirs,
            "nb_lignes": nb_lignes,
            "nb_produits": nb_produits,
            "total_ht": float(stats.total_ht or 0),
            "total_ttc": float(stats.total_ttc or 0),
            "poids_total_kg": float(stats.poids_total or 0),
            "premiere_facture": stats.premiere_facture.isoformat() if stats.premiere_facture else None,
            "derniere_facture": stats.derniere_facture.isoformat() if stats.derniere_facture else None,
        }

    def get_stats_par_client(self) -> Dict[str, Any]:
        """Retourne les statistiques par client (NOUTAM, INCONTOURNABLE)."""
        stats = self.db.query(
            EurocielFacture.client_nom,
            func.count(EurocielFacture.id).label('count'),
            func.sum(EurocielFacture.total_ht).label('total_ht'),
            func.sum(EurocielFacture.total_ttc).label('total_ttc'),
            func.sum(EurocielFacture.poids_total).label('poids_total'),
        ).filter(
            EurocielFacture.tenant_id == self.tenant_id
        ).group_by(
            EurocielFacture.client_nom
        ).order_by(desc(func.sum(EurocielFacture.total_ht))).all()

        clients = [
            {
                "client_nom": row.client_nom or "Non identifie",
                "count": row.count,
                "total_ht": float(row.total_ht or 0),
                "total_ttc": float(row.total_ttc or 0),
                "poids_total_kg": float(row.poids_total or 0),
            }
            for row in stats
        ]
        return {"clients": clients}

    def get_stats_par_categorie(self) -> Dict[str, Any]:
        """Retourne les statistiques par categorie de produit."""
        stats = self.db.query(
            EurocielProduitAgregat.categorie,
            func.count(EurocielProduitAgregat.id).label('count'),
            func.sum(EurocielProduitAgregat.montant_total_ht).label('total_ht'),
            func.sum(EurocielProduitAgregat.poids_total).label('poids_total'),
        ).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        ).group_by(
            EurocielProduitAgregat.categorie
        ).order_by(desc(func.sum(EurocielProduitAgregat.montant_total_ht))).all()

        categories = [
            {
                "categorie": row.categorie,
                "count": row.count,
                "total_ht": float(row.total_ht or 0),
                "poids_total_kg": float(row.poids_total or 0),
            }
            for row in stats
        ]
        return {"categories": categories}

    def get_factures(
        self,
        page: int = 1,
        per_page: int = 20,
        client: Optional[str] = None,
        type_document: Optional[str] = None,
        date_debut: Optional[date] = None,
        date_fin: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Retourne la liste des factures avec pagination."""
        query = self.db.query(EurocielFacture).filter(
            EurocielFacture.tenant_id == self.tenant_id
        )

        if client:
            query = query.filter(EurocielFacture.client_nom.ilike(f"%{client}%"))
        if type_document:
            query = query.filter(EurocielFacture.type_document == type_document)
        if date_debut:
            query = query.filter(EurocielFacture.date_facture >= date_debut)
        if date_fin:
            query = query.filter(EurocielFacture.date_facture <= date_fin)

        total = query.count()
        factures = query.order_by(desc(EurocielFacture.date_facture)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        return {
            "items": [
                {
                    "id": f.id,
                    "numero": f.numero,
                    "type_document": f.type_document,
                    "date_facture": f.date_facture.isoformat() if f.date_facture else None,
                    "client_nom": f.client_nom,
                    "total_ht": float(f.total_ht or 0),
                    "total_ttc": float(f.total_ttc or 0),
                    "poids_total": float(f.poids_total or 0) if f.poids_total else None,
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
        """Retourne le detail d'une facture avec ses lignes."""
        facture = self.db.query(EurocielFacture).filter(
            EurocielFacture.tenant_id == self.tenant_id,
            EurocielFacture.id == facture_id
        ).first()

        if not facture:
            return None

        return {
            "id": facture.id,
            "numero": facture.numero,
            "type_document": facture.type_document,
            "date_facture": facture.date_facture.isoformat() if facture.date_facture else None,
            "client_nom": facture.client_nom,
            "client_code": facture.client_code,
            "client_adresse": facture.client_adresse,
            "client_telephone": facture.client_telephone,
            "total_ht": float(facture.total_ht or 0),
            "total_tva": float(facture.total_tva or 0),
            "total_ttc": float(facture.total_ttc or 0),
            "poids_total": float(facture.poids_total or 0) if facture.poids_total else None,
            "quantite_totale": float(facture.quantite_totale or 0) if facture.quantite_totale else None,
            "fichier_source": facture.fichier_source,
            "page_source": facture.page_source,
            "lignes": [
                {
                    "id": l.id,
                    "numero_ligne": l.numero_ligne,
                    "ean": l.ean,
                    "designation": l.designation,
                    "quantite": float(l.quantite or 0),
                    "poids": float(l.poids or 0) if l.poids else None,
                    "prix_unitaire": float(l.prix_unitaire or 0),
                    "montant_ht": float(l.montant_ht or 0),
                    "code_tva": l.code_tva,
                    "taux_tva": float(l.taux_tva or 0),
                    "montant_tva": float(l.montant_tva or 0) if l.montant_tva else None,
                    "montant_ttc": float(l.montant_ttc or 0) if l.montant_ttc else None,
                    "est_promo": l.est_promo,
                }
                for l in facture.lignes
            ],
        }

    def get_top_produits(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne les produits les plus achetes."""
        stats = self.db.query(
            EurocielLigne.designation_clean,
            func.count(EurocielLigne.id).label('nb_achats'),
            func.sum(EurocielLigne.quantite).label('total_quantite'),
            func.sum(EurocielLigne.poids).label('total_poids'),
            func.sum(EurocielLigne.montant_ht).label('total_ht'),
            func.avg(EurocielLigne.prix_unitaire).label('prix_moyen'),
        ).filter(
            EurocielLigne.tenant_id == self.tenant_id,
            EurocielLigne.designation_clean.isnot(None),
        ).group_by(
            EurocielLigne.designation_clean
        ).order_by(desc(func.sum(EurocielLigne.montant_ht))).limit(limit).all()

        return [
            {
                "designation": row.designation_clean,
                "nb_achats": row.nb_achats,
                "total_quantite": float(row.total_quantite or 0),
                "total_poids_kg": float(row.total_poids or 0),
                "total_ht": float(row.total_ht or 0),
                "prix_moyen": float(row.prix_moyen or 0),
            }
            for row in stats
        ]

    def get_products(
        self,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None,
        categorie: Optional[str] = None,
        sort_by: str = "montant_total",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Retourne la liste paginee des produits agreges."""
        query = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        )

        # Filtres - recherche multi-champs et multi-mots
        if search:
            # Normaliser et splitter les termes de recherche
            search_terms = search.strip().lower().split()
            for term in search_terms:
                pattern = f"%{term}%"
                query = query.filter(
                    (EurocielProduitAgregat.designation_clean.ilike(pattern)) |
                    (EurocielProduitAgregat.designation_brute.ilike(pattern)) |
                    (EurocielProduitAgregat.ean.ilike(pattern)) |
                    (EurocielProduitAgregat.categorie.ilike(pattern))
                )
        if categorie:
            query = query.filter(EurocielProduitAgregat.categorie == categorie)

        # Tri
        sort_column = getattr(EurocielProduitAgregat, sort_by, EurocielProduitAgregat.montant_total)
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
                    "quantite_totale": float(p.quantite_totale or 0),
                    "poids_total_kg": float(p.poids_total or 0) if p.poids_total else None,
                    "nb_achats": p.nb_achats,
                    "montant_total_ht": float(p.montant_total_ht or 0),
                    "montant_total_tva": float(p.montant_total_tva or 0) if p.montant_total_tva else None,
                    "montant_total": float(p.montant_total or 0),
                    "prix_moyen": float(p.prix_moyen or 0),
                    "prix_min": float(p.prix_min or 0),
                    "prix_max": float(p.prix_max or 0),
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
        """Retourne un produit agrege par son ID."""
        p = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id,
            EurocielProduitAgregat.id == product_id
        ).first()

        if not p:
            return None

        return {
            "id": p.id,
            "ean": p.ean,
            "designation": p.designation_brute,
            "designation_clean": p.designation_clean,
            "categorie": p.categorie,
            "prix_moyen": float(p.prix_moyen or 0),
            "montant_total": float(p.montant_total or 0),
        }

    # =========================================================================
    # CALCUL DES AGREGATS
    # =========================================================================

    def recalculer_agregats(self) -> int:
        """
        Recalcule tous les agregats produits a partir des lignes EUROCIEL.

        Returns:
            Nombre de produits agreges
        """
        # Supprimer les anciens agregats
        self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        ).delete()

        # Calculer les nouveaux agregats avec SQL
        query = text("""
            INSERT INTO dwh.eurociel_produit_agregat (
                tenant_id, ean, designation_brute, designation_clean,
                quantite_totale, poids_total, nb_achats,
                montant_total_ht, montant_total_tva, montant_total,
                prix_moyen, prix_min, prix_max,
                taux_tva, categorie_id, famille, categorie, sous_categorie,
                premier_achat, dernier_achat, calcule_le
            )
            SELECT
                l.tenant_id,
                -- EAN: prendre celui renseigne (le plus recent non-null)
                (SELECT l2.ean FROM dwh.eurociel_ligne l2
                 JOIN dwh.eurociel_facture f2 ON l2.facture_id = f2.id
                 WHERE l2.designation_clean = l.designation_clean AND l2.tenant_id = l.tenant_id
                   AND l2.ean IS NOT NULL
                 ORDER BY f2.date_facture DESC LIMIT 1) as ean,
                -- Prendre la designation originale la plus frequente
                (SELECT l2.designation FROM dwh.eurociel_ligne l2
                 WHERE l2.designation_clean = l.designation_clean AND l2.tenant_id = l.tenant_id
                 GROUP BY l2.designation ORDER BY COUNT(*) DESC LIMIT 1) as designation_brute,
                l.designation_clean,
                COALESCE(SUM(l.quantite), 0) as quantite_totale,
                SUM(l.poids) as poids_total,
                COUNT(*) as nb_achats,
                SUM(l.montant_ht) as montant_total_ht,
                SUM(l.montant_tva) as montant_total_tva,
                SUM(l.montant_ttc) as montant_total,
                AVG(l.prix_unitaire) as prix_moyen,
                MIN(l.prix_unitaire) as prix_min,
                MAX(l.prix_unitaire) as prix_max,
                MAX(l.taux_tva) as taux_tva,
                NULL as categorie_id,
                'EPICERIE' as famille,
                'Alimentaire' as categorie,
                NULL as sous_categorie,
                MIN(f.date_facture) as premier_achat,
                MAX(f.date_facture) as dernier_achat,
                NOW() as calcule_le
            FROM dwh.eurociel_ligne l
            JOIN dwh.eurociel_facture f ON l.facture_id = f.id
            WHERE l.tenant_id = :tenant_id
              AND l.designation_clean IS NOT NULL
              AND l.designation_clean != ''
            GROUP BY l.tenant_id, l.designation_clean
        """)

        self.db.execute(query, {"tenant_id": self.tenant_id})
        self.db.commit()

        # Compter les resultats
        count = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        ).count()

        # Appliquer la categorisation automatique basee sur les mots-cles
        self._appliquer_categorisation()

        return count

    def _appliquer_categorisation(self) -> None:
        """Applique la categorisation automatique basee sur la designation."""
        produits = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        ).all()

        for produit in produits:
            famille, categorie, sous_cat = categoriser_produit_eurociel(produit.designation_brute)
            produit.famille = famille
            produit.categorie = categorie
            produit.sous_categorie = sous_cat

        self.db.commit()

    # =========================================================================
    # GESTION EAN
    # =========================================================================

    def set_product_ean(self, produit_id: int, ean: Optional[str]) -> Optional[EurocielProduitAgregat]:
        """
        Met a jour l'EAN d'un produit agrege.

        Args:
            produit_id: ID du produit agrege
            ean: Code EAN (ou None pour supprimer)

        Returns:
            Le produit mis a jour ou None si non trouve
        """
        produit = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id,
            EurocielProduitAgregat.id == produit_id
        ).first()

        if not produit:
            return None

        # Valider le format EAN si fourni
        if ean:
            ean = ean.strip()
            if len(ean) < 8 or len(ean) > 14:
                raise ValueError("L'EAN doit faire entre 8 et 14 caracteres")

        produit.ean = ean
        self.db.commit()

        return produit

    def get_produit_by_id(self, produit_id: int) -> Optional[Dict[str, Any]]:
        """Retourne les details d'un produit agrege."""
        produit = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id,
            EurocielProduitAgregat.id == produit_id
        ).first()

        if not produit:
            return None

        return {
            "id": produit.id,
            "ean": produit.ean,
            "designation": produit.designation_brute,
            "designation_clean": produit.designation_clean,
            "quantite_totale": float(produit.quantite_totale or 0),
            "poids_total_kg": float(produit.poids_total or 0) if produit.poids_total else None,
            "nb_achats": produit.nb_achats,
            "montant_total_ht": float(produit.montant_total_ht or 0),
            "montant_total_tva": float(produit.montant_total_tva or 0) if produit.montant_total_tva else None,
            "montant_total": float(produit.montant_total or 0),
            "prix_moyen": float(produit.prix_moyen or 0),
            "prix_min": float(produit.prix_min or 0),
            "prix_max": float(produit.prix_max or 0),
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
        Synchronise les produits EUROCIEL vers la table dim_produit.

        Pour chaque produit agrege EUROCIEL:
        - Si EAN renseigne: verifie s'il existe dans dim_produit, cree ou met a jour
        - Si EAN absent: cree une entree avec EAN genere (EURO-{id})

        Returns:
            Statistiques de synchronisation
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}

        produits = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id
        ).all()

        for produit in produits:
            # Generer un EAN si absent
            ean_to_use = produit.ean
            if not ean_to_use:
                # Generer un identifiant unique pour les produits sans EAN
                ean_to_use = f"EURO{produit.id:010d}"

            # Chercher si le produit existe deja dans dim_produit
            dim_produit = self.db.query(DimProduit).filter(
                DimProduit.ean == ean_to_use
            ).first()

            if dim_produit:
                # Mettre a jour les agregats
                dim_produit.nb_achats = (dim_produit.nb_achats or 0) + produit.nb_achats
                dim_produit.quantite_totale_achetee = (
                    (dim_produit.quantite_totale_achetee or Decimal(0)) +
                    produit.quantite_totale
                )
                dim_produit.montant_total_achats = (
                    (dim_produit.montant_total_achats or Decimal(0)) +
                    (produit.montant_total_ht or Decimal(0))
                )
                # Mettre a jour le prix si plus recent
                if produit.dernier_achat and (
                    not dim_produit.date_dernier_prix or
                    produit.dernier_achat > dim_produit.date_dernier_prix
                ):
                    dim_produit.prix_achat_unitaire = produit.prix_moyen
                    dim_produit.date_dernier_prix = produit.dernier_achat

                # Lier le produit EUROCIEL a dim_produit
                produit.dim_produit_id = dim_produit.id
                stats["updated"] += 1
            else:
                # Creer une nouvelle entree dans dim_produit
                nouveau_produit = DimProduit(
                    ean=ean_to_use,
                    designation_brute=produit.designation_brute,
                    designation_clean=produit.designation_clean,
                    famille=produit.famille,
                    categorie=produit.categorie,
                    sous_categorie=produit.sous_categorie,
                    taux_tva=produit.taux_tva,
                    colisage_standard=1,
                    prix_achat_unitaire=produit.prix_moyen,
                    date_dernier_prix=produit.dernier_achat,
                    nb_achats=produit.nb_achats,
                    quantite_totale_achetee=produit.quantite_totale,
                    montant_total_achats=produit.montant_total_ht or Decimal(0),
                    source="EUROCIEL",
                    actif=True,
                )
                self.db.add(nouveau_produit)
                self.db.flush()

                # Lier le produit EUROCIEL a dim_produit
                produit.dim_produit_id = nouveau_produit.id
                stats["created"] += 1

        self.db.commit()
        return stats

    def get_products_without_ean(self) -> List[Dict[str, Any]]:
        """Retourne la liste des produits sans EAN (a renseigner manuellement)."""
        produits = self.db.query(EurocielProduitAgregat).filter(
            EurocielProduitAgregat.tenant_id == self.tenant_id,
            EurocielProduitAgregat.ean.is_(None)
        ).order_by(desc(EurocielProduitAgregat.montant_total)).all()

        return [
            {
                "id": p.id,
                "designation": p.designation_brute,
                "designation_clean": p.designation_clean,
                "categorie": p.categorie,
                "nb_achats": p.nb_achats,
                "montant_total": float(p.montant_total or 0),
                "poids_total_kg": float(p.poids_total or 0) if p.poids_total else None,
            }
            for p in produits
        ]

    # ==========================================================================
    # Méthodes Catalogue Produits
    # ==========================================================================

    def get_catalogue_produits(
        self,
        page: int = 1,
        per_page: int = 50,
        categorie: Optional[str] = None,
        origine: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retourne les produits du catalogue avec pagination et filtres."""
        from app.models.eurociel import EurocielCatalogueProduit

        query = self.db.query(EurocielCatalogueProduit).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True
        )

        # Filtres
        if categorie:
            query = query.filter(EurocielCatalogueProduit.categorie == categorie)
        if origine:
            query = query.filter(EurocielCatalogueProduit.origine == origine)
        if search:
            query = query.filter(
                EurocielCatalogueProduit.designation_clean.ilike(f"%{search.upper()}%")
            )

        # Total
        total = query.count()

        # Pagination
        query = query.order_by(
            EurocielCatalogueProduit.categorie,
            EurocielCatalogueProduit.designation
        )
        query = query.offset((page - 1) * per_page).limit(per_page)
        produits = query.all()

        return {
            "items": [
                {
                    "id": p.id,
                    "reference": p.reference,
                    "designation": p.designation,
                    "categorie": p.categorie,
                    "taille": p.taille,
                    "conditionnement": p.conditionnement,
                    "poids_kg": float(p.poids_kg) if p.poids_kg else None,
                    "origine": p.origine,
                }
                for p in produits
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }

    def get_catalogue_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du catalogue."""
        from app.models.eurociel import EurocielCatalogueProduit
        from sqlalchemy import func

        # Total
        total = self.db.query(func.count(EurocielCatalogueProduit.id)).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True
        ).scalar()

        # Par categorie
        par_categorie = self.db.query(
            EurocielCatalogueProduit.categorie,
            func.count(EurocielCatalogueProduit.id).label("count")
        ).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True
        ).group_by(
            EurocielCatalogueProduit.categorie
        ).order_by(desc("count")).all()

        # Par origine
        par_origine = self.db.query(
            EurocielCatalogueProduit.origine,
            func.count(EurocielCatalogueProduit.id).label("count")
        ).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True,
            EurocielCatalogueProduit.origine.isnot(None)
        ).group_by(
            EurocielCatalogueProduit.origine
        ).order_by(desc("count")).all()

        return {
            "total_references": total,
            "par_categorie": {row[0]: row[1] for row in par_categorie},
            "par_origine": {row[0]: row[1] for row in par_origine},
        }

    def get_catalogue_categories(self) -> List[str]:
        """Retourne la liste des categories du catalogue."""
        from app.models.eurociel import EurocielCatalogueProduit

        categories = self.db.query(EurocielCatalogueProduit.categorie).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True
        ).distinct().order_by(EurocielCatalogueProduit.categorie).all()

        return [c[0] for c in categories]

    def get_catalogue_origines(self) -> List[str]:
        """Retourne la liste des pays d'origine du catalogue."""
        from app.models.eurociel import EurocielCatalogueProduit

        origines = self.db.query(EurocielCatalogueProduit.origine).filter(
            EurocielCatalogueProduit.tenant_id == self.tenant_id,
            EurocielCatalogueProduit.actif == True,
            EurocielCatalogueProduit.origine.isnot(None)
        ).distinct().order_by(EurocielCatalogueProduit.origine).all()

        return [o[0] for o in origines]
