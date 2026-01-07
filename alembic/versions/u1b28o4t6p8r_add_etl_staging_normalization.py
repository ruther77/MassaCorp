"""Add ETL staging schema and normalization functions.

Revision ID: u1b28o4t6p8r
Revises: t0a17n3s5o7q
Create Date: 2026-01-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'u1b28o4t6p8r'
down_revision: Union[str, None] = 't0a17n3s5o7q'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create staging schema
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")

    # Create extraction status enum (if not exists)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'extraction_status' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'staging')) THEN
                CREATE TYPE staging.extraction_status AS ENUM (
                    'BRUT', 'NORMALISE', 'VALIDE', 'ERREUR_NORM', 'ERREUR_VALID'
                );
            END IF;
        END$$;
    """)

    # Create staging table for invoice lines
    op.execute("""
        CREATE TABLE IF NOT EXISTS staging.stg_facture_ligne (
            id SERIAL PRIMARY KEY,
            batch_id UUID NOT NULL,
            source_file VARCHAR(500) NOT NULL,
            extraction_status staging.extraction_status DEFAULT 'BRUT',

            -- En-tete facture
            numero_facture VARCHAR(50),
            numero_interne VARCHAR(50),
            date_facture DATE,
            fournisseur_nom VARCHAR(200),
            fournisseur_siret VARCHAR(20),
            magasin_nom VARCHAR(200),
            client_nom VARCHAR(200),
            client_numero VARCHAR(50),

            -- Ligne article
            ligne_numero INTEGER,
            ean VARCHAR(20),
            article_numero VARCHAR(20),
            designation TEXT,
            categorie_source VARCHAR(100),
            regie VARCHAR(10),
            vol_alcool NUMERIC(5,2),
            vap NUMERIC(10,4),
            poids_volume NUMERIC(10,4),
            unite VARCHAR(10) DEFAULT 'L',
            prix_unitaire NUMERIC(14,4),
            colisage INTEGER,
            quantite INTEGER,
            montant_ligne NUMERIC(14,2),
            code_tva VARCHAR(5),
            taux_tva NUMERIC(5,2),
            est_promo BOOLEAN DEFAULT FALSE,
            cotis_secu NUMERIC(14,4),

            -- Metadonnees
            raw_line TEXT,
            validation_errors JSONB DEFAULT '[]',
            created_at TIMESTAMP DEFAULT NOW(),

            -- Index
            CONSTRAINT stg_facture_ligne_batch_idx UNIQUE (batch_id, source_file, ligne_numero)
        )
    """)

    # Create mapping tables
    op.execute("""
        CREATE TABLE IF NOT EXISTS staging.mapping_categorie (
            id SERIAL PRIMARY KEY,
            fournisseur VARCHAR(50) NOT NULL,
            categorie_source VARCHAR(100) NOT NULL,
            categorie_dwh_code VARCHAR(30) NOT NULL,
            famille VARCHAR(50),
            sous_famille VARCHAR(50),
            UNIQUE(fournisseur, categorie_source)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS staging.mapping_fournisseur (
            id SERIAL PRIMARY KEY,
            nom_source VARCHAR(200) NOT NULL UNIQUE,
            nom_normalise VARCHAR(100) NOT NULL,
            siret VARCHAR(20),
            tva_intra VARCHAR(20),
            code_interne VARCHAR(20)
        )
    """)

    # Insert default mappings
    op.execute("""
        INSERT INTO staging.mapping_categorie (fournisseur, categorie_source, categorie_dwh_code, famille, sous_famille) VALUES
        ('METRO', 'SPIRITUEUX', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
        ('METRO', 'BRASSERIE', 'ALC_BIERE', 'Boissons', 'Biere'),
        ('METRO', 'CAVE', 'ALC_VIN', 'Boissons', 'Vin'),
        ('METRO', 'CHAMPAGNES', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne'),
        ('METRO', 'CHAMPAGNE', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne'),
        ('METRO', 'EPICERIE SECHE', 'ALI_EPICERIE', 'Alimentation', 'Epicerie'),
        ('METRO', 'EPICERIE', 'ALI_EPICERIE', 'Alimentation', 'Epicerie'),
        ('METRO', 'SURGELES', 'ALI_SURGELES', 'Alimentation', 'Surgeles'),
        ('METRO', 'DROGUERIE', 'NON_ALI_DROGUERIE', 'Non alimentaire', 'Droguerie'),
        ('METRO', 'FOURNITURES', 'NON_ALI_FOURNITURES', 'Non alimentaire', 'Fournitures'),
        ('EUROCIEL', 'Alcools forts', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
        ('EUROCIEL', 'Spiritueux', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
        ('EUROCIEL', 'Bieres', 'ALC_BIERE', 'Boissons', 'Biere'),
        ('EUROCIEL', 'Vins', 'ALC_VIN', 'Boissons', 'Vin'),
        ('EUROCIEL', 'Champagnes', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne'),
        ('TAIYAT', 'SPIRITS', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
        ('TAIYAT', 'BEER', 'ALC_BIERE', 'Boissons', 'Biere'),
        ('TAIYAT', 'WINE', 'ALC_VIN', 'Boissons', 'Vin'),
        ('TAIYAT', 'CHAMPAGNE', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne')
    """)

    op.execute("""
        INSERT INTO staging.mapping_fournisseur (nom_source, nom_normalise, siret, tva_intra, code_interne) VALUES
        ('METRO', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
        ('METRO FRANCE', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
        ('METRO France', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
        ('METRO France SA', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
        ('EUROCIEL', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
        ('Eurociel', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
        ('EUROCIEL SAS', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
        ('TAIYAT', 'TAIYAT', NULL, NULL, 'TAIYAT'),
        ('Taiyat', 'TAIYAT', NULL, NULL, 'TAIYAT')
    """)

    # Create normalization functions

    # N1: clean_text - Basic text cleaning
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.clean_text(p_text TEXT)
        RETURNS TEXT AS $$
        BEGIN
            IF p_text IS NULL THEN
                RETURN NULL;
            END IF;

            RETURN TRIM(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REPLACE(
                                REPLACE(
                                    REPLACE(p_text, E'\\t', ' '),
                                    E'\\n', ''
                                ),
                                E'\\r', ''
                            ),
                            E'[\\u00AB\\u00BB]', '', 'g'
                        ),
                        E'\\u00A0', ' ', 'g'
                    ),
                    '\\s+', ' ', 'g'
                )
            );
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N1: normalize_designation - Product name normalization
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_designation(p_designation TEXT)
        RETURNS TEXT AS $$
        DECLARE
            v_result TEXT;
        BEGIN
            IF p_designation IS NULL OR p_designation = '' THEN
                RETURN NULL;
            END IF;

            -- Step 1: Clean characters
            v_result := staging.clean_text(p_designation);

            -- Step 2: Title Case
            v_result := INITCAP(v_result);

            -- Keep units lowercase
            v_result := REGEXP_REPLACE(v_result, '\\b(\\d+)(Cl|Ml|L|Kg|G)\\b', '\\1\\L\\2', 'gi');

            -- Step 3: Expand abbreviations
            v_result := REGEXP_REPLACE(v_result, '\\bWh\\b', 'Whiskey', 'gi');
            v_result := REGEXP_REPLACE(v_result, '\\bVdk\\b', 'Vodka', 'gi');
            v_result := REGEXP_REPLACE(v_result, '\\bChamp\\b', 'Champagne', 'gi');
            v_result := REGEXP_REPLACE(v_result, '\\bBle\\b', 'Blonde', 'gi');
            v_result := REGEXP_REPLACE(v_result, '(\\d+)D\\b', '\\1\\u00B0', 'g');

            -- Step 4: Normalize apostrophes
            v_result := REPLACE(v_result, '''', E'\\u2019');
            v_result := REPLACE(v_result, '`', E'\\u2019');

            -- Step 5: Normalize volumes
            v_result := REGEXP_REPLACE(v_result, '(\\d+)CL\\b', '\\1cl', 'gi');
            v_result := REGEXP_REPLACE(v_result, '(\\d+)ML\\b', '\\1ml', 'gi');
            v_result := REGEXP_REPLACE(v_result, '0[,.]7\\s*L\\b', '70cl', 'gi');
            v_result := REGEXP_REPLACE(v_result, '0[,.]5\\s*L\\b', '50cl', 'gi');
            v_result := REGEXP_REPLACE(v_result, '0[,.]33\\s*L\\b', '33cl', 'gi');

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N2: normalize_ean - EAN code normalization with checksum validation
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_ean(p_ean TEXT)
        RETURNS TEXT AS $$
        DECLARE
            v_ean TEXT;
            v_checksum INT;
            v_sum INT := 0;
            i INT;
        BEGIN
            IF p_ean IS NULL OR TRIM(p_ean) = '' THEN
                RETURN NULL;
            END IF;

            -- Clean: remove non-digits
            v_ean := TRIM(REGEXP_REPLACE(p_ean, '\\D', '', 'g'));

            -- Remove leading zero if 14 digits
            IF LENGTH(v_ean) = 14 AND v_ean ~ '^0' THEN
                v_ean := SUBSTRING(v_ean FROM 2);
            END IF;

            -- Validate length
            IF LENGTH(v_ean) NOT IN (8, 13) THEN
                RETURN NULL;
            END IF;

            -- Pad EAN-8 to EAN-13
            IF LENGTH(v_ean) = 8 THEN
                v_ean := '00000' || v_ean;
            END IF;

            -- Calculate EAN-13 checksum
            FOR i IN 1..12 LOOP
                v_sum := v_sum + (SUBSTRING(v_ean, i, 1)::INT * CASE WHEN i % 2 = 0 THEN 3 ELSE 1 END);
            END LOOP;
            v_checksum := (10 - (v_sum % 10)) % 10;

            -- Validate checksum (warn but still return)
            IF v_checksum != SUBSTRING(v_ean, 13, 1)::INT THEN
                RAISE WARNING 'EAN checksum invalid: % (expected: %)', v_ean, v_checksum;
            END IF;

            RETURN v_ean;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N3: normalize_categorie - Category normalization using mapping table
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_categorie(
            p_fournisseur TEXT,
            p_categorie_source TEXT
        ) RETURNS TEXT AS $$
            SELECT COALESCE(
                (SELECT categorie_dwh_code
                 FROM staging.mapping_categorie
                 WHERE fournisseur = UPPER(p_fournisseur)
                   AND UPPER(categorie_source) = UPPER(TRIM(p_categorie_source))),
                'INCONNU'
            );
        $$ LANGUAGE sql STABLE
    """)

    # N4: normalize_prix - Price normalization (handles French format)
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_prix(p_prix TEXT)
        RETURNS NUMERIC(14,4) AS $$
        DECLARE
            v_clean TEXT;
            v_result NUMERIC(14,4);
        BEGIN
            IF p_prix IS NULL OR p_prix = '' THEN
                RETURN NULL;
            END IF;

            -- Clean
            v_clean := TRIM(p_prix);
            v_clean := REGEXP_REPLACE(v_clean, E'[\\u20AC EUR]', '', 'gi');
            v_clean := REGEXP_REPLACE(v_clean, '\\s+', '', 'g');

            -- Handle French format (1 234,56 -> 1234.56)
            IF v_clean ~ '\\d+\\.\\d{3},' THEN
                v_clean := REPLACE(v_clean, '.', '');
            END IF;
            v_clean := REPLACE(v_clean, ',', '.');

            -- Convert
            BEGIN
                v_result := v_clean::NUMERIC(14,4);
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;

            -- Validate
            IF v_result < 0 OR v_result > 100000 THEN
                RAISE WARNING 'Price out of range: %', v_result;
                RETURN NULL;
            END IF;

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N5: normalize_quantite - Quantity normalization
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_quantite(p_quantite TEXT)
        RETURNS INTEGER AS $$
        DECLARE
            v_clean TEXT;
            v_result INTEGER;
        BEGIN
            IF p_quantite IS NULL OR p_quantite = '' THEN
                RETURN NULL;
            END IF;

            v_clean := TRIM(p_quantite);
            v_clean := REGEXP_REPLACE(v_clean, '[,.]0+$', '', 'g');
            v_clean := REPLACE(v_clean, ',', '.');

            BEGIN
                v_result := ROUND(v_clean::NUMERIC)::INTEGER;
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;

            IF v_result <= 0 OR v_result > 10000 THEN
                RAISE WARNING 'Quantity out of range: %', v_result;
                RETURN NULL;
            END IF;

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N6: normalize_fournisseur - Supplier normalization
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_fournisseur(p_nom TEXT)
        RETURNS TABLE(nom_normalise TEXT, siret TEXT, tva_intra TEXT, code_interne TEXT) AS $$
            SELECT
                COALESCE(m.nom_normalise, UPPER(TRIM(p_nom))),
                m.siret,
                m.tva_intra,
                COALESCE(m.code_interne, 'INCONNU')
            FROM staging.mapping_fournisseur m
            WHERE UPPER(TRIM(m.nom_source)) = UPPER(TRIM(p_nom))
            LIMIT 1;
        $$ LANGUAGE sql STABLE
    """)

    # N7: normalize_date - Date normalization (handles French and ISO formats)
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.normalize_date(p_date TEXT)
        RETURNS DATE AS $$
        DECLARE
            v_result DATE;
        BEGIN
            IF p_date IS NULL OR TRIM(p_date) = '' THEN
                RETURN NULL;
            END IF;

            BEGIN
                -- Format DD-MM-YYYY or DD/MM/YYYY (French)
                IF p_date ~ '^\\d{2}[-/]\\d{2}[-/]\\d{4}$' THEN
                    v_result := TO_DATE(p_date, 'DD-MM-YYYY');
                -- Format YYYY-MM-DD (ISO)
                ELSIF p_date ~ '^\\d{4}[-/]\\d{2}[-/]\\d{2}$' THEN
                    v_result := TO_DATE(p_date, 'YYYY-MM-DD');
                ELSE
                    -- Generic attempt
                    v_result := p_date::DATE;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                RETURN NULL;
            END;

            -- Validate range
            IF v_result < '2000-01-01'::DATE OR v_result > CURRENT_DATE + INTERVAL '30 days' THEN
                RAISE WARNING 'Date out of range: %', v_result;
                RETURN NULL;
            END IF;

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # N8: calculate_montants - Calculate amounts (HT, TVA, TTC)
    op.execute("""
        CREATE OR REPLACE FUNCTION staging.calculate_montants(
            p_prix_unitaire NUMERIC,
            p_quantite INTEGER,
            p_taux_tva NUMERIC
        ) RETURNS TABLE(
            montant_ht NUMERIC(14,2),
            montant_tva NUMERIC(14,2),
            montant_ttc NUMERIC(14,2)
        ) AS $$
        DECLARE
            v_ht NUMERIC(14,2);
            v_tva NUMERIC(14,2);
            v_ttc NUMERIC(14,2);
        BEGIN
            v_ht := ROUND(p_prix_unitaire * p_quantite, 2);
            v_tva := ROUND(v_ht * COALESCE(p_taux_tva, 20.0) / 100, 2);
            v_ttc := v_ht + v_tva;

            RETURN QUERY SELECT v_ht, v_tva, v_ttc;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE
    """)

    # Quality monitoring view
    op.execute("""
        CREATE OR REPLACE VIEW staging.v_qualite_normalisation AS
        SELECT
            batch_id,
            COUNT(*) AS total_lignes,
            COUNT(*) FILTER (WHERE extraction_status = 'NORMALISE') AS normalise,
            COUNT(*) FILTER (WHERE extraction_status = 'ERREUR_NORM') AS erreurs,
            COUNT(*) FILTER (WHERE designation IS NOT NULL AND designation != '') AS designation_ok,
            COUNT(*) FILTER (WHERE designation ~ '[A-Z]{3,}') AS designation_maj_excessif,
            COUNT(*) FILTER (WHERE ean ~ '^\\d{13}$') AS ean_ok,
            COUNT(*) FILTER (WHERE ean IS NULL) AS ean_manquant,
            COUNT(*) FILTER (WHERE categorie_source != 'INCONNU') AS categorie_ok,
            ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'NORMALISE') / NULLIF(COUNT(*), 0), 1) AS taux_normalisation
        FROM staging.stg_facture_ligne
        GROUP BY batch_id
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_stg_facture_ligne_batch ON staging.stg_facture_ligne(batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stg_facture_ligne_status ON staging.stg_facture_ligne(extraction_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stg_facture_ligne_ean ON staging.stg_facture_ligne(ean)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mapping_categorie_lookup ON staging.mapping_categorie(fournisseur, UPPER(categorie_source))")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS staging.v_qualite_normalisation")
    op.execute("DROP FUNCTION IF EXISTS staging.calculate_montants")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_date")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_fournisseur")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_quantite")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_prix")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_categorie")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_ean")
    op.execute("DROP FUNCTION IF EXISTS staging.normalize_designation")
    op.execute("DROP FUNCTION IF EXISTS staging.clean_text")
    op.execute("DROP TABLE IF EXISTS staging.mapping_fournisseur")
    op.execute("DROP TABLE IF EXISTS staging.mapping_categorie")
    op.execute("DROP TABLE IF EXISTS staging.stg_facture_ligne")
    op.execute("DROP TYPE IF EXISTS staging.extraction_status")
    op.execute("DROP SCHEMA IF EXISTS staging CASCADE")
