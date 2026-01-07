# Workflow de Normalisation des Colonnes ETL

## MassaCorp - NOUTAM SAS & L'Incontournable

---

## 1. Vue d'ensemble

Ce document définit les règles de normalisation des données extraites de tous les fournisseurs (METRO, EUROCIEL, TAIYAT) pour garantir la cohérence et la qualité des données dans le DWH.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     PIPELINE DE NORMALISATION DES COLONNES                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DONNÉES BRUTES          NORMALISATION              DONNÉES NORMALISÉES         │
│  (Multi-sources)         (Mini-workflows)           (Format unifié)             │
│  ┌─────────────┐        ┌─────────────────┐        ┌─────────────────┐         │
│  │ METRO       │        │ N1: Nom produit │        │                 │         │
│  │ "WH JACK    │───────►│ N2: EAN         │───────►│ "Jack Daniel's  │         │
│  │  DANIEL'S"  │        │ N3: Catégorie   │        │  Tennessee      │         │
│  ├─────────────┤        │ N4: Prix        │        │  Whiskey 35cl"  │         │
│  │ EUROCIEL    │        │ N5: Quantité    │        │                 │         │
│  │ "jack       │───────►│ N6: Fournisseur │───────►│ Format unifié   │         │
│  │  daniels"   │        │ N7: Dates       │        │ pour tous       │         │
│  ├─────────────┤        │ N8: Montants    │        │ fournisseurs    │         │
│  │ TAIYAT      │        │ ...             │        │                 │         │
│  │ "JACK       │───────►│                 │───────►│                 │         │
│  │  DANIEL S"  │        │                 │        │                 │         │
│  └─────────────┘        └─────────────────┘        └─────────────────┘         │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mini-Workflows par Colonne

### 2.1 N1: Normalisation du Nom Produit (designation)

**Problématique**: Les noms de produits varient entre fournisseurs et peuvent contenir des abréviations, casses différentes, caractères parasites.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    N1: WORKFLOW NOM PRODUIT (designation)                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE                                                                   │
│  "WH JACK DANIEL'S 40D 35CL"  (METRO)                                          │
│  "jack daniels 35"            (EUROCIEL)                                        │
│  "JACK DANIEL S  35CL"        (TAIYAT)                                          │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────┐                                   │
│  │ ÉTAPE 1: Nettoyage caractères           │                                   │
│  │ - TRIM espaces début/fin                │                                   │
│  │ - Supprimer double espaces              │                                   │
│  │ - Remplacer tabulations par espace      │                                   │
│  └───────────────┬─────────────────────────┘                                   │
│                  ▼                                                              │
│  ┌─────────────────────────────────────────┐                                   │
│  │ ÉTAPE 2: Uniformisation casse           │                                   │
│  │ - Convertir en Title Case               │                                   │
│  │ - Exceptions: cl, ml, L, kg (minuscule) │                                   │
│  │ - Exceptions: TVA, HT, TTC (majuscule)  │                                   │
│  └───────────────┬─────────────────────────┘                                   │
│                  ▼                                                              │
│  ┌─────────────────────────────────────────┐                                   │
│  │ ÉTAPE 3: Expansion abréviations         │                                   │
│  │ - WH → Whiskey                          │                                   │
│  │ - VDK → Vodka                           │                                   │
│  │ - CHAMP → Champagne                     │                                   │
│  │ - BLE → Blonde                          │                                   │
│  │ - 40D → 40°                             │                                   │
│  └───────────────┬─────────────────────────┘                                   │
│                  ▼                                                              │
│  ┌─────────────────────────────────────────┐                                   │
│  │ ÉTAPE 4: Normalisation apostrophes      │                                   │
│  │ - ' → ' (apostrophe typographique)      │                                   │
│  │ - ` → '                                 │                                   │
│  │ - Supprimer apostrophe orpheline        │                                   │
│  └───────────────┬─────────────────────────┘                                   │
│                  ▼                                                              │
│  ┌─────────────────────────────────────────┐                                   │
│  │ ÉTAPE 5: Formatage volume/poids         │                                   │
│  │ - 35CL → 35cl                           │                                   │
│  │ - 0,7L → 70cl                           │                                   │
│  │ - 500ML → 50cl                          │                                   │
│  │ - 1KG → 1kg                             │                                   │
│  └───────────────┬─────────────────────────┘                                   │
│                  ▼                                                              │
│  SORTIE NORMALISÉE                                                              │
│  "Jack Daniel's Tennessee Whiskey 35cl"                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Implémentation SQL**:

```sql
-- Fonction de normalisation du nom produit
CREATE OR REPLACE FUNCTION staging.normalize_designation(p_designation TEXT)
RETURNS TEXT AS $$
DECLARE
    v_result TEXT;
BEGIN
    -- Étape 1: Nettoyage caractères
    v_result := TRIM(p_designation);
    v_result := REGEXP_REPLACE(v_result, '\s+', ' ', 'g');
    v_result := REPLACE(v_result, E'\t', ' ');

    -- Étape 2: Title Case avec exceptions
    v_result := INITCAP(v_result);

    -- Garder unités en minuscule
    v_result := REGEXP_REPLACE(v_result, '\b(\d+)(Cl|Ml|L|Kg|G)\b', '\1\L\2', 'gi');

    -- Étape 3: Expansion abréviations
    v_result := REGEXP_REPLACE(v_result, '\bWh\b', 'Whiskey', 'gi');
    v_result := REGEXP_REPLACE(v_result, '\bVdk\b', 'Vodka', 'gi');
    v_result := REGEXP_REPLACE(v_result, '\bChamp\b', 'Champagne', 'gi');
    v_result := REGEXP_REPLACE(v_result, '\bBle\b', 'Blonde', 'gi');
    v_result := REGEXP_REPLACE(v_result, '(\d+)D\b', '\1°', 'g');

    -- Étape 4: Normalisation apostrophes
    v_result := REPLACE(v_result, '''', ''');
    v_result := REPLACE(v_result, '`', ''');
    v_result := REGEXP_REPLACE(v_result, '\s+''\s+', '''', 'g');

    -- Étape 5: Normalisation volume
    v_result := REGEXP_REPLACE(v_result, '(\d+)CL\b', '\1cl', 'gi');
    v_result := REGEXP_REPLACE(v_result, '(\d+)ML\b', E'\\1ml', 'gi');
    -- Conversion 0,7L → 70cl
    v_result := REGEXP_REPLACE(v_result, '0[,.]7\s*L\b', '70cl', 'gi');
    v_result := REGEXP_REPLACE(v_result, '0[,.]5\s*L\b', '50cl', 'gi');
    v_result := REGEXP_REPLACE(v_result, '0[,.]33\s*L\b', '33cl', 'gi');

    RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**Implémentation Python**:

```python
def normalize_designation(designation: str) -> str:
    """Normalise le nom d'un produit."""
    if not designation:
        return ""

    import re

    # Étape 1: Nettoyage
    result = designation.strip()
    result = re.sub(r'\s+', ' ', result)
    result = result.replace('\t', ' ')

    # Étape 2: Title Case avec exceptions
    def title_case_with_exceptions(text):
        words = text.split()
        result = []
        units = {'cl', 'ml', 'l', 'kg', 'g'}
        for word in words:
            lower = word.lower()
            if lower in units or re.match(r'^\d+[a-z]+$', lower):
                result.append(lower)
            else:
                result.append(word.capitalize())
        return ' '.join(result)

    result = title_case_with_exceptions(result)

    # Étape 3: Expansion abréviations
    abbreviations = {
        r'\bWh\b': 'Whiskey',
        r'\bVdk\b': 'Vodka',
        r'\bChamp\b': 'Champagne',
        r'\bBle\b': 'Blonde',
        r'(\d+)D\b': r'\1°',
    }
    for pattern, replacement in abbreviations.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Étape 4: Apostrophes
    result = result.replace("'", "'").replace("`", "'")
    result = re.sub(r"\s+'\s+", "'", result)

    # Étape 5: Volumes
    result = re.sub(r'(\d+)CL\b', r'\1cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]7\s*L\b', '70cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]5\s*L\b', '50cl', result, flags=re.IGNORECASE)
    result = re.sub(r'0[,.]33\s*L\b', '33cl', result, flags=re.IGNORECASE)

    return result
```

---

### 2.2 N2: Normalisation EAN

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         N2: WORKFLOW EAN                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE              VALIDATION                 SORTIE                    │
│  "05010327325125"          ┌─────────────┐           "5010327325125"            │
│  " 5010327325125 "    ────►│ Trim        │────►      (EAN-13 valide)            │
│  "501032732512"            │ Pad zeros   │                                      │
│                            │ Checksum    │           NULL si invalide           │
│                            └─────────────┘                                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Règles**:
1. Supprimer espaces et zéros en tête superflus
2. Valider longueur (8 ou 13 chiffres)
3. Calculer et vérifier checksum EAN
4. Padder à 13 chiffres si EAN-8

```sql
CREATE OR REPLACE FUNCTION staging.normalize_ean(p_ean TEXT)
RETURNS TEXT AS $$
DECLARE
    v_ean TEXT;
    v_checksum INT;
    v_sum INT := 0;
    i INT;
BEGIN
    -- Nettoyage
    v_ean := TRIM(REGEXP_REPLACE(p_ean, '\D', '', 'g'));

    -- Supprimer zéro en tête si 14 chiffres
    IF LENGTH(v_ean) = 14 AND v_ean ~ '^0' THEN
        v_ean := SUBSTRING(v_ean FROM 2);
    END IF;

    -- Validation longueur
    IF LENGTH(v_ean) NOT IN (8, 13) THEN
        RETURN NULL;
    END IF;

    -- Padding EAN-8 → EAN-13
    IF LENGTH(v_ean) = 8 THEN
        v_ean := '00000' || v_ean;
    END IF;

    -- Calcul checksum EAN-13
    FOR i IN 1..12 LOOP
        v_sum := v_sum + (SUBSTRING(v_ean, i, 1)::INT * CASE WHEN i % 2 = 0 THEN 3 ELSE 1 END);
    END LOOP;
    v_checksum := (10 - (v_sum % 10)) % 10;

    -- Vérification checksum
    IF v_checksum != SUBSTRING(v_ean, 13, 1)::INT THEN
        -- Log warning mais retourner quand même (données sources parfois incorrectes)
        RAISE WARNING 'EAN checksum invalide: % (attendu: %)', v_ean, v_checksum;
    END IF;

    RETURN v_ean;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

### 2.3 N3: Normalisation Catégorie

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      N3: WORKFLOW CATÉGORIE                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE (source)           MAPPING                    SORTIE (DWH)              │
│                                                                                 │
│  METRO:                    ┌────────────────────┐                               │
│  "SPIRITUEUX"         ────►│                    │────► "ALC_SPIRITUEUX"         │
│  "BRASSERIE"          ────►│ Table de mapping   │────► "ALC_BIERE"              │
│  "CAVE"               ────►│ staging.mapping_   │────► "ALC_VIN"                │
│  "CHAMPAGNES"         ────►│ categorie          │────► "ALC_CHAMPAGNE"          │
│                            │                    │                               │
│  EUROCIEL:                 │ Clé: fournisseur + │                               │
│  "Alcools forts"      ────►│      categorie_src │────► "ALC_SPIRITUEUX"         │
│  "Bières"             ────►│                    │────► "ALC_BIERE"              │
│                            │                    │                               │
│  TAIYAT:                   │                    │                               │
│  "SPIRITS"            ────►│                    │────► "ALC_SPIRITUEUX"         │
│  "BEER"               ────►│                    │────► "ALC_BIERE"              │
│                            └────────────────────┘                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Table de mapping**:

```sql
CREATE TABLE staging.mapping_categorie (
    id SERIAL PRIMARY KEY,
    fournisseur VARCHAR(50) NOT NULL,
    categorie_source VARCHAR(100) NOT NULL,
    categorie_dwh_code VARCHAR(30) NOT NULL,
    famille VARCHAR(50),
    sous_famille VARCHAR(50),

    UNIQUE(fournisseur, categorie_source)
);

-- Mapping METRO
INSERT INTO staging.mapping_categorie (fournisseur, categorie_source, categorie_dwh_code, famille, sous_famille) VALUES
('METRO', 'SPIRITUEUX', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
('METRO', 'BRASSERIE', 'ALC_BIERE', 'Boissons', 'Bière'),
('METRO', 'CAVE', 'ALC_VIN', 'Boissons', 'Vin'),
('METRO', 'CHAMPAGNES', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne'),
('METRO', 'CHAMPAGNE', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne'),
('METRO', 'EPICERIE SECHE', 'ALI_EPICERIE', 'Alimentation', 'Épicerie'),
('METRO', 'EPICERIE', 'ALI_EPICERIE', 'Alimentation', 'Épicerie'),
('METRO', 'SURGELES', 'ALI_SURGELES', 'Alimentation', 'Surgelés'),
('METRO', 'DROGUERIE', 'NON_ALI_DROGUERIE', 'Non alimentaire', 'Droguerie'),
('METRO', 'FOURNITURES', 'NON_ALI_FOURNITURES', 'Non alimentaire', 'Fournitures');

-- Mapping EUROCIEL
INSERT INTO staging.mapping_categorie (fournisseur, categorie_source, categorie_dwh_code, famille, sous_famille) VALUES
('EUROCIEL', 'Alcools forts', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
('EUROCIEL', 'Spiritueux', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
('EUROCIEL', 'Bières', 'ALC_BIERE', 'Boissons', 'Bière'),
('EUROCIEL', 'Vins', 'ALC_VIN', 'Boissons', 'Vin'),
('EUROCIEL', 'Champagnes', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne');

-- Mapping TAIYAT
INSERT INTO staging.mapping_categorie (fournisseur, categorie_source, categorie_dwh_code, famille, sous_famille) VALUES
('TAIYAT', 'SPIRITS', 'ALC_SPIRITUEUX', 'Boissons', 'Alcool fort'),
('TAIYAT', 'BEER', 'ALC_BIERE', 'Boissons', 'Bière'),
('TAIYAT', 'WINE', 'ALC_VIN', 'Boissons', 'Vin'),
('TAIYAT', 'CHAMPAGNE', 'ALC_CHAMPAGNE', 'Boissons', 'Champagne');

-- Fonction de normalisation
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
$$ LANGUAGE sql STABLE;
```

---

### 2.4 N4: Normalisation Prix

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         N4: WORKFLOW PRIX                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE              TRANSFORMATION              SORTIE                   │
│                                                                                 │
│  "12,50"              ────►┌─────────────────┐────►   12.50                     │
│  "1 234,56"           ────►│ 1. Trim         │────►   1234.56                   │
│  "12.50€"             ────►│ 2. Remove €     │────►   12.50                     │
│  "12.50 EUR"          ────►│ 3. Replace , → .│────►   12.50                     │
│  " 12 50 "            ────►│ 4. Remove spaces│────►   12.50                     │
│                            │ 5. NUMERIC(14,4)│                                  │
│                            └─────────────────┘                                  │
│                                                                                 │
│  VALIDATION:                                                                    │
│  - Prix positif (>= 0)                                                         │
│  - Prix raisonnable (< 100000)                                                 │
│  - Précision 4 décimales max                                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

```sql
CREATE OR REPLACE FUNCTION staging.normalize_prix(p_prix TEXT)
RETURNS NUMERIC(14,4) AS $$
DECLARE
    v_clean TEXT;
    v_result NUMERIC(14,4);
BEGIN
    IF p_prix IS NULL OR p_prix = '' THEN
        RETURN NULL;
    END IF;

    -- Nettoyage
    v_clean := TRIM(p_prix);
    v_clean := REGEXP_REPLACE(v_clean, '[€EUR]', '', 'gi');
    v_clean := REGEXP_REPLACE(v_clean, '\s+', '', 'g');

    -- Gestion format français (1 234,56 → 1234.56)
    -- Si contient virgule ET point, le point est séparateur milliers
    IF v_clean ~ '\d+\.\d{3},' THEN
        v_clean := REPLACE(v_clean, '.', '');
    END IF;
    v_clean := REPLACE(v_clean, ',', '.');

    -- Conversion
    BEGIN
        v_result := v_clean::NUMERIC(14,4);
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;

    -- Validation
    IF v_result < 0 OR v_result > 100000 THEN
        RAISE WARNING 'Prix hors limites: %', v_result;
        RETURN NULL;
    END IF;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

### 2.5 N5: Normalisation Quantité

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       N5: WORKFLOW QUANTITÉ                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE              TRANSFORMATION              SORTIE                   │
│                                                                                 │
│  "12"                 ────►┌─────────────────┐────►   12                        │
│  "12.0"               ────►│ 1. Trim         │────►   12                        │
│  " 12 "               ────►│ 2. Remove .0    │────►   12                        │
│  "12,00"              ────►│ 3. To INTEGER   │────►   12                        │
│                            │ 4. Validate > 0 │                                  │
│                            └─────────────────┘                                  │
│                                                                                 │
│  VALIDATION:                                                                    │
│  - Quantité entière positive                                                   │
│  - Maximum raisonnable (< 10000)                                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

```sql
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
        RAISE WARNING 'Quantité hors limites: %', v_result;
        RETURN NULL;
    END IF;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

### 2.6 N6: Normalisation Fournisseur

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      N6: WORKFLOW FOURNISSEUR                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE              NORMALISATION               SORTIE                   │
│                                                                                 │
│  "metro"              ────►┌─────────────────┐────►   "METRO France"            │
│  "METRO FRANCE"       ────►│ Lookup table    │────►   "METRO France"            │
│  "Metro France SA"    ────►│ + SIRET         │────►   "METRO France"            │
│                            │ + TVA intra     │        SIRET: 399315613          │
│  "Eurociel"           ────►│                 │────►   "EUROCIEL"                │
│  "EUROCIEL SAS"       ────►│                 │────►   "EUROCIEL"                │
│                            │                 │        SIRET: xxx                │
│  "TAIYAT"             ────►│                 │────►   "TAIYAT"                  │
│                            └─────────────────┘                                  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

```sql
CREATE TABLE staging.mapping_fournisseur (
    id SERIAL PRIMARY KEY,
    nom_source VARCHAR(200) NOT NULL,
    nom_normalise VARCHAR(100) NOT NULL,
    siret VARCHAR(20),
    tva_intra VARCHAR(20),
    code_interne VARCHAR(20),

    UNIQUE(nom_source)
);

INSERT INTO staging.mapping_fournisseur (nom_source, nom_normalise, siret, tva_intra, code_interne) VALUES
('METRO', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
('METRO FRANCE', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
('METRO France', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
('METRO France SA', 'METRO France', '399315613', 'FR12399315613', 'METRO'),
('EUROCIEL', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
('Eurociel', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
('EUROCIEL SAS', 'EUROCIEL', NULL, NULL, 'EUROCIEL'),
('TAIYAT', 'TAIYAT', NULL, NULL, 'TAIYAT'),
('Taiyat', 'TAIYAT', NULL, NULL, 'TAIYAT');

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
$$ LANGUAGE sql STABLE;
```

---

### 2.7 N7: Normalisation Dates

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         N7: WORKFLOW DATE                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ENTRÉE BRUTE              TRANSFORMATION              SORTIE                   │
│                                                                                 │
│  "07-06-2024"         ────►┌─────────────────┐────►   2024-06-07                │
│  "07/06/2024"         ────►│ Détection format│────►   2024-06-07                │
│  "2024-06-07"         ────►│ Conversion ISO  │────►   2024-06-07                │
│  "07 juin 2024"       ────►│ Validation      │────►   2024-06-07                │
│  "June 7, 2024"       ────►│ Range check     │────►   2024-06-07                │
│                            └─────────────────┘                                  │
│                                                                                 │
│  VALIDATION:                                                                    │
│  - Date valide (existe dans calendrier)                                        │
│  - Date raisonnable (2000 < année < 2100)                                      │
│  - Pas dans le futur (pour factures)                                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

```sql
CREATE OR REPLACE FUNCTION staging.normalize_date(p_date TEXT)
RETURNS DATE AS $$
DECLARE
    v_result DATE;
BEGIN
    IF p_date IS NULL OR TRIM(p_date) = '' THEN
        RETURN NULL;
    END IF;

    -- Essayer différents formats
    BEGIN
        -- Format DD-MM-YYYY ou DD/MM/YYYY (français)
        IF p_date ~ '^\d{2}[-/]\d{2}[-/]\d{4}$' THEN
            v_result := TO_DATE(p_date, 'DD-MM-YYYY');
        -- Format YYYY-MM-DD (ISO)
        ELSIF p_date ~ '^\d{4}[-/]\d{2}[-/]\d{2}$' THEN
            v_result := TO_DATE(p_date, 'YYYY-MM-DD');
        -- Format DD mois YYYY
        ELSIF p_date ~* '^\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}$' THEN
            v_result := TO_DATE(p_date, 'DD TMMonth YYYY');
        ELSE
            -- Tentative générique
            v_result := p_date::DATE;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;

    -- Validation range
    IF v_result < '2000-01-01'::DATE OR v_result > CURRENT_DATE + INTERVAL '30 days' THEN
        RAISE WARNING 'Date hors limites: %', v_result;
        RETURN NULL;
    END IF;

    RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

### 2.8 N8: Normalisation Montants (TVA, TTC)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       N8: WORKFLOW MONTANTS                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  CALCULS DÉRIVÉS:                                                               │
│                                                                                 │
│  montant_ht (source)        ┌─────────────────┐                                │
│  taux_tva (source)     ────►│ CALCUL          │────► montant_tva               │
│                             │ ht × taux/100   │      (calculé)                 │
│                             └─────────────────┘                                │
│                                                                                 │
│  montant_ht (source)        ┌─────────────────┐                                │
│  montant_tva (calc)    ────►│ CALCUL          │────► montant_ttc               │
│                             │ ht + tva        │      (calculé)                 │
│                             └─────────────────┘                                │
│                                                                                 │
│  VALIDATION COHÉRENCE:                                                          │
│  - |ht × qté - montant_ligne| < 0.05€                                          │
│  - |ht + tva - ttc| < 0.01€                                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

```sql
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
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## 3. Table de Caractères Parasites

Liste des caractères à nettoyer/remplacer dans toutes les colonnes texte:

| Caractère | Code | Action | Remplacement |
|-----------|------|--------|--------------|
| `\t` | Tab | Remplacer | Espace |
| `\n` | Newline | Supprimer | - |
| `\r` | Carriage return | Supprimer | - |
| Double espace | | Réduire | Espace simple |
| ` (accent grave) | | Remplacer | ' |
| ' (smart quote) | | Garder | ' |
| « » | Guillemets FR | Supprimer | - |
| ° | Degré | Garder | ° |
| € | Euro | Supprimer (prix) | - |
| \u00A0 | Non-breaking space | Remplacer | Espace |

```sql
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
                            REPLACE(p_text, E'\t', ' '),
                            E'\n', ''
                        ),
                        E'\r', ''
                    ),
                    '[\u00AB\u00BB]', '', 'g'  -- Guillemets
                ),
                '\u00A0', ' ', 'g'  -- NBSP
            ),
            '\s+', ' ', 'g'  -- Multiple espaces
        )
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

---

## 4. Application aux Sources

### 4.1 METRO

```sql
-- Normalisation complète ligne METRO
CREATE OR REPLACE FUNCTION staging.normalize_metro_ligne(
    p_ligne staging.stg_facture_ligne
) RETURNS staging.stg_facture_ligne AS $$
DECLARE
    v_ligne staging.stg_facture_ligne := p_ligne;
    v_fournisseur RECORD;
    v_montants RECORD;
BEGIN
    -- Nettoyer tous les champs texte
    v_ligne.designation := staging.clean_text(v_ligne.designation);
    v_ligne.categorie_source := staging.clean_text(v_ligne.categorie_source);

    -- Normaliser designation
    v_ligne.designation := staging.normalize_designation(v_ligne.designation);

    -- Normaliser EAN
    v_ligne.ean := staging.normalize_ean(v_ligne.ean);

    -- Normaliser catégorie
    v_ligne.categorie_source := staging.normalize_categorie('METRO', v_ligne.categorie_source);

    -- Normaliser fournisseur
    SELECT * INTO v_fournisseur FROM staging.normalize_fournisseur(v_ligne.fournisseur_nom);
    v_ligne.fournisseur_nom := v_fournisseur.nom_normalise;
    v_ligne.fournisseur_siret := v_fournisseur.siret;

    -- Normaliser prix et quantité
    v_ligne.prix_unitaire := staging.normalize_prix(v_ligne.prix_unitaire::TEXT);
    v_ligne.quantite := staging.normalize_quantite(v_ligne.quantite::TEXT);

    -- Calculer montants
    SELECT * INTO v_montants FROM staging.calculate_montants(
        v_ligne.prix_unitaire,
        v_ligne.quantite,
        v_ligne.taux_tva
    );

    -- Valider cohérence
    IF ABS(v_montants.montant_ht - v_ligne.montant_ligne) > 0.05 THEN
        RAISE WARNING 'Incohérence montant ligne %: calculé=%, source=%',
            v_ligne.id, v_montants.montant_ht, v_ligne.montant_ligne;
    END IF;

    RETURN v_ligne;
END;
$$ LANGUAGE plpgsql;
```

### 4.2 EUROCIEL

```sql
-- À implémenter selon format spécifique EUROCIEL
CREATE OR REPLACE FUNCTION staging.normalize_eurociel_ligne(
    p_ligne staging.stg_facture_ligne
) RETURNS staging.stg_facture_ligne AS $$
-- Structure similaire à METRO avec adaptations
$$ LANGUAGE plpgsql;
```

### 4.3 TAIYAT

```sql
-- À implémenter selon format spécifique TAIYAT
CREATE OR REPLACE FUNCTION staging.normalize_taiyat_ligne(
    p_ligne staging.stg_facture_ligne
) RETURNS staging.stg_facture_ligne AS $$
-- Structure similaire à METRO avec adaptations
$$ LANGUAGE plpgsql;
```

---

## 5. Procédure de Normalisation Globale

```sql
-- Procédure principale de normalisation
CREATE OR REPLACE PROCEDURE staging.run_normalization(p_batch_id UUID)
LANGUAGE plpgsql AS $$
DECLARE
    v_count INT := 0;
    v_errors INT := 0;
    r RECORD;
BEGIN
    RAISE NOTICE '=== NORMALISATION BATCH % ===', p_batch_id;

    -- Parcourir les lignes du batch
    FOR r IN
        SELECT * FROM staging.stg_facture_ligne
        WHERE batch_id = p_batch_id
        AND extraction_status = 'BRUT'
    LOOP
        BEGIN
            -- Appliquer normalisation selon fournisseur
            CASE UPPER(r.fournisseur_nom)
                WHEN 'METRO FRANCE', 'METRO' THEN
                    UPDATE staging.stg_facture_ligne
                    SET (designation, ean, categorie_source, fournisseur_nom,
                         fournisseur_siret, prix_unitaire, quantite) =
                        (SELECT l.designation, l.ean, l.categorie_source,
                                l.fournisseur_nom, l.fournisseur_siret,
                                l.prix_unitaire, l.quantite
                         FROM staging.normalize_metro_ligne(r) l)
                    WHERE id = r.id;

                WHEN 'EUROCIEL' THEN
                    -- Appliquer normalisation EUROCIEL
                    UPDATE staging.stg_facture_ligne
                    SET designation = staging.normalize_designation(designation),
                        ean = staging.normalize_ean(ean)
                    WHERE id = r.id;

                WHEN 'TAIYAT' THEN
                    -- Appliquer normalisation TAIYAT
                    UPDATE staging.stg_facture_ligne
                    SET designation = staging.normalize_designation(designation),
                        ean = staging.normalize_ean(ean)
                    WHERE id = r.id;

                ELSE
                    RAISE WARNING 'Fournisseur inconnu: %', r.fournisseur_nom;
            END CASE;

            -- Marquer comme normalisé
            UPDATE staging.stg_facture_ligne
            SET extraction_status = 'NORMALISE'
            WHERE id = r.id;

            v_count := v_count + 1;

        EXCEPTION WHEN OTHERS THEN
            v_errors := v_errors + 1;
            UPDATE staging.stg_facture_ligne
            SET extraction_status = 'ERREUR_NORM',
                validation_errors = validation_errors ||
                    jsonb_build_array(format('Erreur normalisation: %s', SQLERRM))
            WHERE id = r.id;
        END;
    END LOOP;

    RAISE NOTICE 'Normalisation terminée: % lignes, % erreurs', v_count, v_errors;
END;
$$;
```

---

## 6. Tests de Normalisation

```sql
-- Tests unitaires pour les fonctions de normalisation
DO $$
DECLARE
    v_result TEXT;
BEGIN
    -- Test N1: Designation
    ASSERT staging.normalize_designation('WH JACK DANIEL''S 40D 35CL')
        ~* 'jack.*daniel.*whiskey.*35cl',
        'Test N1 failed: designation';

    -- Test N2: EAN
    ASSERT staging.normalize_ean('5010327325125') = '5010327325125',
        'Test N2 failed: EAN valide';
    ASSERT staging.normalize_ean('05010327325125') = '5010327325125',
        'Test N2 failed: EAN avec 0 en tête';

    -- Test N3: Catégorie
    ASSERT staging.normalize_categorie('METRO', 'SPIRITUEUX') = 'ALC_SPIRITUEUX',
        'Test N3 failed: catégorie METRO';

    -- Test N4: Prix
    ASSERT staging.normalize_prix('12,50') = 12.50,
        'Test N4 failed: prix virgule';
    ASSERT staging.normalize_prix('1 234,56') = 1234.56,
        'Test N4 failed: prix avec espace';

    -- Test N5: Quantité
    ASSERT staging.normalize_quantite('12') = 12,
        'Test N5 failed: quantité simple';
    ASSERT staging.normalize_quantite('12.0') = 12,
        'Test N5 failed: quantité décimale';

    -- Test N7: Date
    ASSERT staging.normalize_date('07-06-2024') = '2024-06-07'::DATE,
        'Test N7 failed: date FR';
    ASSERT staging.normalize_date('2024-06-07') = '2024-06-07'::DATE,
        'Test N7 failed: date ISO';

    RAISE NOTICE 'Tous les tests passés!';
END;
$$;
```

---

## 7. Monitoring Qualité

```sql
-- Vue de monitoring qualité après normalisation
CREATE OR REPLACE VIEW staging.v_qualite_normalisation AS
SELECT
    batch_id,
    COUNT(*) AS total_lignes,
    COUNT(*) FILTER (WHERE extraction_status = 'NORMALISE') AS normalise,
    COUNT(*) FILTER (WHERE extraction_status = 'ERREUR_NORM') AS erreurs,

    -- Qualité designation
    COUNT(*) FILTER (WHERE designation IS NOT NULL AND designation != '') AS designation_ok,
    COUNT(*) FILTER (WHERE designation ~ '[A-Z]{3,}') AS designation_maj_excessif,

    -- Qualité EAN
    COUNT(*) FILTER (WHERE ean ~ '^\d{13}$') AS ean_ok,
    COUNT(*) FILTER (WHERE ean IS NULL) AS ean_manquant,

    -- Qualité catégorie
    COUNT(*) FILTER (WHERE categorie_source != 'INCONNU') AS categorie_ok,

    -- Taux global
    ROUND(100.0 * COUNT(*) FILTER (WHERE extraction_status = 'NORMALISE') / NULLIF(COUNT(*), 0), 1) AS taux_normalisation

FROM staging.stg_facture_ligne
GROUP BY batch_id;
```

---

*Document créé le 2026-01-06*
*MassaCorp - NOUTAM SAS & L'Incontournable*
