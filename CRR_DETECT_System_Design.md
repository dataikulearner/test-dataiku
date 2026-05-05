# CRR × DETECT System Design
## Anomaly Detection for Credit Risk Reporting

**Version**: 1.0  
**Date**: 05/05/2026  
**Author**: DETECT Team  
**Status**: Draft - En attente validation données historiques

---

## 1. Executive Summary

Ce document décrit l'architecture technique pour intégrer les données CRR (Credit Risk Reporting) dans la plateforme DETECT, en réutilisant l'algorithme original de détection d'anomalies basé sur les séries temporelles.

### Hypothèse clé
> **Les données historiques (minimum 4-6 quarters) sont disponibles** via tables archives ou extraction périodique.

---

## 2. Data Model

### 2.1 Source Tables

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TERADATA                                        │
│                     Connection: TD_PRD_RP_CRR                               │
│                     Schema: DB_FTG_SRS_PROD_VEXP_RP_CRR                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐         One-to-Many         ┌──────────────────────┐
│  │    CLIENT_AR        │ ─────────────────────────── │    FACILITE_AR       │
│  │    (V_EXPO_CLIENT)  │          SK_CLI             │  (V_EXPO_FACILITE)   │
│  ├─────────────────────┤              ↓              ├──────────────────────┤
│  │ SK_CLI          [PK]│ ═══════════════════════════ │ SK_CLI_CTRP      [FK]│
│  │ ID_CLI_FCT          │                             │ SK_FAC / ID_FAC_FCT  │
│  │ TX_TRG_SENR_UNSECUR │                             │ ID_RUN           [PK]│
│  │ CD_MOD_NOT          │                             │                      │
│  │ CD_TYP_CLIL         │                             │ ── Segmentation ──   │
│  │ CD_CLASS_TIE_MUT    │                             │ CD_POLE_PMAS_AP_ACCRED
│  │ CD_NOTE_ECH_GRP     │                             │ CD_PMAS_AP_ACCRED    │
│  │ CD_LIGN_CLIL        │                             │ CD_TYP_APPRO_BALE_2  │
│  │ CD_SECT_ACTIV       │                             │ CD_CLASS_EXPO_COREP  │
│  │ ID_GRP_AFF          │                             │ CD_SIT_RISQ_AP_ACCRED│
│  │ CD_SECT_ACTIV_GA    │                             │ ID_ENTITE_JURI_AP    │
│  │ MT_CHIFF_AFF_RECLC  │                             │                      │
│  └─────────────────────┘                             │ ── LGD/EAD Models ── │
│                                                      │ CD_MOD_LGD           │
│                                                      │ CD_MOD_LGD_SURCH_IRBA│
│                                                      │ CD_MOD_EAD           │
│                                                      │ CD_MOD_EAD_SURCH_IRBA│
│                                                      │                      │
│                                                      │ ── Rates ──          │
│                                                      │ TX_LGD               │
│                                                      │ TX_LGD_UTI_IRBA      │
│                                                      │ TX_PD_1              │
│                                                      │ TX_PD_1_UTI_IRBA     │
│                                                      │                      │
│                                                      │ ── Amounts ──        │
│                                                      │ MT_EXPO_BRUTE_TOT    │
│                                                      │ MT_EXPO_RISQ_TOT     │
│                                                      │ MT_RISQ_POND_TOT     │
│                                                      │ MT_PERT_ATT_EXPO_TOT │
│                                                      │ MT_PROV_GAL_AFF_TOT  │
│                                                      │ MT_PROV_SPE_AFF_TOT  │
│                                                      │                      │
│                                                      │ ── Rating ──         │
│                                                      │ CD_NOTE_CTRP_CORRES  │
│                                                      │ CD_ENG               │
│                                                      │ IND_FAC_AGR          │
│                                                      └──────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Join Strategy

```sql
-- Base query for DETECT input
SELECT 
    -- Period
    f.ID_RUN,
    
    -- Identifiers
    f.SK_FAC AS facility_id,
    c.ID_CLI_FCT AS client_id,
    
    -- Axes (Segmentation) - Level 1 to 5
    f.CD_POLE_PMAS_AP_ACCRED AS pole_pmas,           -- Level 1
    f.CD_PMAS_AP_ACCRED AS pma,                       -- Level 2
    f.CD_CLASS_EXPO_COREP_IRBA AS corep_class,        -- Level 3
    f.CD_TYP_APPRO_BALE_2 AS basel_approach,          -- Level 4
    f.CD_SIT_RISQ_AP_ACCRED AS risk_site,             -- Level 5
    c.CD_LIGN_CLIL AS client_coverage,                -- Optional
    c.CD_SECT_ACTIV AS industry_code,                 -- Optional
    
    -- Target Variables (Numeric - for anomaly detection)
    f.MT_EXPO_RISQ_TOT AS ead_amount,
    f.MT_RISQ_POND_TOT AS rwa_amount,
    f.MT_PERT_ATT_EXPO_TOT AS expected_loss,
    f.TX_LGD AS lgd_rate,
    f.TX_LGD_UTI_IRBA AS lgd_rate_irba,
    f.TX_PD_1 AS pd_rate,
    f.TX_PD_1_UTI_IRBA AS pd_rate_irba,
    
    -- Context (for investigation, not detection)
    f.CD_MOD_LGD AS lgd_model,
    f.CD_MOD_LGD_SURCH_IRBA AS lgd_model_irba,
    f.CD_MOD_EAD AS ead_model,
    c.CD_MOD_NOT AS rating_model,
    f.CD_NOTE_CTRP_CORRES_PD_RECAL_IRBA AS rating_after_penalty
    
FROM V_EXPO_FACILITE_AR f
LEFT JOIN V_EXPO_CLIENT_AR c ON f.SK_CLI_CTRP = c.SK_CLI
WHERE f.ID_RUN IN (${periods_list})  -- Historical periods
```

---

## 3. Justification des Choix de Configuration

### 3.1 Sélection des Axes (Colonnes de Segmentation)

Les axes définissent comment les données sont segmentées pour la détection d'anomalies. Le choix est basé sur **3 critères** :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CRITÈRES DE SÉLECTION DES AXES                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. BUSINESS RELEVANCE                                                      │
│     → L'axe doit avoir un sens métier pour CRR                             │
│     → Les analystes doivent pouvoir investiguer par cet axe                │
│                                                                             │
│  2. CARDINALITÉ APPROPRIÉE                                                  │
│     → Pas trop de valeurs distinctes (< 1000 idéalement)                   │
│     → Assez de valeurs pour segmenter utilement (> 3)                      │
│                                                                             │
│  3. STABILITÉ TEMPORELLE                                                    │
│     → Les valeurs ne changent pas fréquemment                              │
│     → Permet de comparer les mêmes segments dans le temps                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Analyse Détaillée des Axes Choisis

| # | Colonne Source | Axe DETECT | Pourquoi CHOISI | Cardinalité | Niveau |
|---|----------------|------------|-----------------|-------------|--------|
| 1 | **CD_POLE_PMAS_AP_ACCRED** | `pole_pmas` | Niveau le plus haut d'organisation métier. Tous les reportings CRR sont structurés par Pôle. Cardinalité faible (~10-20 pôles). | ~15 | Label 1 |
| 2 | **CD_PMAS_AP_ACCRED** | `pma` | Métier PMAS - niveau de détail opérationnel. C'est le niveau où les corrections LGD sont typiquement appliquées (cf. patterns de Sofia). | ~100 | Label 2 |
| 3 | **CD_CLASS_EXPO_COREP_IRBA** | `corep_class` | Classification réglementaire COREP. Obligatoire pour le reporting CRR/Basel. Chaque classe a des règles de calcul RWA différentes. | ~15 | Label 3 |
| 4 | **CD_TYP_APPRO_BALE_2** | `basel_approach` | Type d'approche Bâle (Standard=2, IRB=3). Impacte directement le calcul RWA et les modèles applicables. | 2-3 | Label 4 |
| 5 | **CD_SIT_RISQ_AP_ACCRED** | `risk_site` | Site de risque post-accréditation. Permet d'identifier les anomalies par localisation géographique. | ~50 | Label 5 |

#### Axes EXCLUS et Justification

| Colonne | Pourquoi EXCLUE |
|---------|-----------------|
| `SK_CLI_CTRP` | Identifiant technique, pas un axe de segmentation |
| `SK_FAC / ID_FAC_FCT` | Niveau trop granulaire (millions de facilities) |
| `CD_MOD_LGD` | C'est une TARGET de l'investigation, pas un axe. On veut détecter des anomalies qui RÉVÈLENT des problèmes de modèle |
| `CD_MOD_LGD_SURCH_IRBA` | Idem - c'est ce qu'on veut investiguer |
| `CD_ENG` | Code engagement - trop technique, peu de valeur métier |
| `IND_FAC_AGR` | Indicateur binaire - pas assez de granularité |
| `ID_ENTITE_JURI_AP_ACCRED` | Entité juridique - souvent redondant avec Pôle |
| `CD_NOTE_CTRP_CORRES_PD_RECAL_IRBA` | Rating - pourrait être un axe mais cardinalité trop élevée (~20+ ratings × transitions) |

#### Axes OPTIONNELS (À discuter avec CRR)

| Colonne (CLIENT_AR) | Axe Potentiel | Cas d'usage |
|---------------------|---------------|-------------|
| `CD_LIGN_CLIL` | `client_coverage` | Si CRR veut segmenter par ligne de couverture client |
| `CD_SECT_ACTIV` | `industry_code` | Pour analyse sectorielle (ex: impact COVID sur secteur tourisme) |
| `CD_MOD_NOT` | `rating_model` | Si CRR veut investiguer par modèle de notation |

---

### 3.2 Sélection des Target Variables (Variables Cibles)

Les target variables sont les **métriques numériques** sur lesquelles DETECT calcule les déviations. Le choix est basé sur **4 critères** :

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CRITÈRES DE SÉLECTION DES TARGET VARIABLES                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. TYPE NUMÉRIQUE                                                          │
│     → DETECT calcule: Deviation = (Current - Expected) / Expected          │
│     → Impossible sur des variables catégorielles                           │
│                                                                             │
│  2. AGRÉGABILITÉ                                                            │
│     → La variable peut être agrégée (SUM, AVG, WAVG) au niveau segment     │
│     → Le résultat agrégé a un sens métier                                  │
│                                                                             │
│  3. SENSIBILITÉ AUX ANOMALIES                                               │
│     → Une erreur de données (ex: mauvais modèle LGD) impacte la variable   │
│     → La variable "réagit" aux problèmes qu'on veut détecter               │
│                                                                             │
│  4. PERTINENCE RÉGLEMENTAIRE                                                │
│     → La variable est utilisée dans les reportings CRR                     │
│     → Une anomalie a des conséquences réglementaires                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Analyse Détaillée des Target Variables Choisies

| # | Colonne Source | Target Variable | Type | Agrégation | Justification Détaillée |
|---|----------------|-----------------|------|------------|-------------------------|
| 1 | **MT_EXPO_RISQ_TOT** | `ead_amount` | Montant (€) | SUM | **EAD (Exposure at Default)** - Métrique centrale du risque de crédit. Une anomalie d'EAD peut indiquer: erreurs de périmètre, problèmes de modèle EAD, ou changements de portefeuille non expliqués. Équivalent à `ead_ifrs9` dans DETECT IFRS9. |
| 2 | **MT_RISQ_POND_TOT** | `rwa_amount` | Montant (€) | SUM | **RWA (Risk-Weighted Assets)** - Directement utilisé pour le calcul des ratios de capital (CET1, Tier1). Une anomalie RWA a un impact réglementaire immédiat. Le RWA dépend de LGD, PD, EAD → une erreur de modèle LGD impacte le RWA. |
| 3 | **MT_PERT_ATT_EXPO_TOT** | `expected_loss` | Montant (€) | SUM | **Expected Loss** - Perte attendue = EAD × PD × LGD. Très sensible aux erreurs de modèle. Une anomalie d'EL peut signaler un problème de LGD ou PD. Équivalent à `provision_ifrs9`. |
| 4 | **TX_LGD** | `lgd_rate` | Ratio (%) | WAVG | **Taux de LGD** - Le taux moyen pondéré par EAD. Permet de détecter si le mix de modèles LGD a changé anormalement. Si beaucoup de facilities ont un LGD manquant, la moyenne peut dévier. |
| 5 | **TX_PD_1** | `pd_rate` | Ratio (%) | WAVG | **Probabilité de Défaut** - Idem que LGD. La PD moyenne pondérée révèle des changements de profil de risque. Utile pour cross-check avec les anomalies LGD. |

#### Relation entre Target Variables et Problème "Missing LGD"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  COMMENT LES TARGET VARIABLES RÉVÈLENT LES PROBLÈMES DE MODÈLE LGD         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Scénario: Un segment a soudainement beaucoup de "Missing LGD Models"      │
│                                                                             │
│  Impact sur les Target Variables:                                           │
│                                                                             │
│  ┌─────────────────┐                                                        │
│  │  TX_LGD         │ → Moyenne biaisée (exclut les nulls ou valeur 0)      │
│  │  (lgd_rate)     │ → Déviation détectée si proportion nulls augmente    │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │  MT_RISQ_POND   │ → RWA potentiellement sous-estimé                     │
│  │  (rwa_amount)   │ → Si LGD=0 utilisé par défaut → RWA trop bas         │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │  MT_PERT_ATT    │ → Expected Loss impacté (EL = EAD × PD × LGD)        │
│  │  (expected_loss)│ → Déviation visible si LGD moyen change              │
│  └─────────────────┘                                                        │
│                                                                             │
│  ⚠️  DETECT ne détecte pas directement "CD_MOD_LGD = NULL"                 │
│      MAIS une anomalie sur lgd_rate ou rwa_amount peut SIGNALER            │
│      qu'il y a un problème sous-jacent à investiguer.                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Variables EXCLUES et Justification

| Colonne | Type | Pourquoi EXCLUE |
|---------|------|-----------------|
| `CD_MOD_LGD` | Catégoriel | Impossible de calculer une déviation numérique |
| `CD_MOD_LGD_SURCH_IRBA` | Catégoriel | Idem |
| `CD_MOD_EAD` | Catégoriel | Idem |
| `MT_EXPO_BRUTE_TOT` | Montant | Redondant avec EAD. L'EAD (risque) est plus pertinent que l'exposure brute |
| `TX_LGD_UTI_IRBA` | Ratio | Redondant avec TX_LGD. On peut ajouter si besoin de distinguer LGD standard vs IRBA |
| `TX_PD_1_UTI_IRBA` | Ratio | Idem - redondant avec TX_PD_1 |
| `MT_PROV_GAL_AFF_TOT` | Montant | Provisions S1/S2 - pertinent mais secondaire pour CRR (plus IFRS9) |
| `MT_PROV_SPE_AFF_TOT` | Montant | Provisions S3 - idem |

#### Variables OPTIONNELLES (À ajouter selon besoins CRR)

| Colonne | Target Potentiel | Cas d'usage |
|---------|------------------|-------------|
| `TX_LGD_UTI_IRBA` | `lgd_rate_irba` | Si CRR veut distinguer LGD standard vs LGD post-penalty |
| `MT_EXPO_BRUTE_TOT` | `gross_exposure` | Pour analyse des garanties (EAD vs Brute) |
| `MT_PROV_GAL_AFF_TOT + MT_PROV_SPE_AFF_TOT` | `total_provisions` | Pour cohérence avec reportings comptables |
| Ratio calculé: `MT_RISQ_POND_TOT / MT_EXPO_RISQ_TOT` | `rwa_density` | Densité RWA - très sensible aux erreurs de modèle |

---

### 3.3 Résumé Visuel des Choix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CRR × DETECT - CONFIGURATION SUMMARY                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  📊 AXES (Segmentation)                 📈 TARGET VARIABLES (Detection)    │
│  ─────────────────────                  ────────────────────────────────    │
│                                                                             │
│  ┌─────────────────────┐                ┌─────────────────────────────┐    │
│  │ CD_POLE_PMAS        │──┐             │ MT_EXPO_RISQ_TOT → SUM      │    │
│  │ (pole_pmas)         │  │             │ = ead_amount                │    │
│  └─────────────────────┘  │             └─────────────────────────────┘    │
│           ↓               │                                                 │
│  ┌─────────────────────┐  │             ┌─────────────────────────────┐    │
│  │ CD_PMAS_AP_ACCRED   │  │             │ MT_RISQ_POND_TOT → SUM      │    │
│  │ (pma)               │  │             │ = rwa_amount                │    │
│  └─────────────────────┘  │             └─────────────────────────────┘    │
│           ↓               │                                                 │
│  ┌─────────────────────┐  │  GroupBy    ┌─────────────────────────────┐    │
│  │ CD_CLASS_EXPO_COREP │──┼──────────── │ MT_PERT_ATT_EXPO → SUM      │    │
│  │ (corep_class)       │  │             │ = expected_loss             │    │
│  └─────────────────────┘  │             └─────────────────────────────┘    │
│           ↓               │                                                 │
│  ┌─────────────────────┐  │             ┌─────────────────────────────┐    │
│  │ CD_TYP_APPRO_BALE_2 │  │             │ TX_LGD → WAVG (by EAD)      │    │
│  │ (basel_approach)    │  │             │ = lgd_rate                  │    │
│  └─────────────────────┘  │             └─────────────────────────────┘    │
│           ↓               │                                                 │
│  ┌─────────────────────┐  │             ┌─────────────────────────────┐    │
│  │ CD_SIT_RISQ_AP_ACCR │──┘             │ TX_PD_1 → WAVG (by EAD)     │    │
│  │ (risk_site)         │                │ = pd_rate                   │    │
│  └─────────────────────┘                └─────────────────────────────┘    │
│                                                                             │
│  🔗 CONTEXT COLUMNS (Pour investigation, pas pour détection)               │
│  ─────────────────────────────────────────────────────────────              │
│  CD_MOD_LGD, CD_MOD_LGD_SURCH_IRBA, CD_MOD_EAD, CD_NOTE_CTRP_CORRES        │
│  → Affichés dans le drill-down pour aider l'analyste                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. DETECT Configuration

### 3.1 crr_params.json

```json
{
    "flow_type": "crr",
    "scope_run": "CRR_MAIN",
    
    "periods_str": "2965/2964/2963/2962/2961/2960",
    "period_col": "id_run",
    
    "target_variables": [
        "ead_amount",
        "rwa_amount",
        "expected_loss",
        "lgd_rate",
        "pd_rate"
    ],
    
    "target_agg_functions": {
        "ead_amount": ["sum", "avg", "count"],
        "rwa_amount": ["sum", "avg"],
        "expected_loss": ["sum", "avg"],
        "lgd_rate": ["avg", "wavg"],
        "pd_rate": ["avg", "wavg"]
    },
    
    "weight_vars": {
        "lgd_rate": "ead_amount",
        "pd_rate": "ead_amount"
    },
    
    "axes_str": "pole_pmas/pole_pmas|pma/pole_pmas|pma|corep_class/pole_pmas|pma|corep_class|basel_approach/pole_pmas|pma|corep_class|basel_approach|risk_site",
    
    "entity_mapping_col": "pole_pmas",
    "entity_title": "Pôle PMAS",
    
    "pma_col": "pma",
    "line_id_cols": ["facility_id", "client_id"],
    "line_fac_col": "facility_id",
    
    "segment_vars": [
        "ead_amount",
        "rwa_amount",
        "expected_loss"
    ],
    
    "segment_filters": [
        {"pole_pmas": "PMA_03"},
        {"pole_pmas": "PMA_05"},
        {"corep_class": "CEC500"}
    ],
    
    "segment_conditions": [
        {
            "condition_1": {"corep_class": "CEC500"},
            "condition_2": {"basel_approach": "2__OR__3"}
        }
    ],
    
    "thresholds_segment_anomaly": {
        "pole_pmas": 0.15,
        "pole_pmas|pma": 0.20,
        "pole_pmas|pma|corep_class": 0.25,
        "pole_pmas|pma|corep_class|basel_approach": 0.30,
        "pole_pmas|pma|corep_class|basel_approach|risk_site": 0.35
    },
    
    "thresholds_negligibility": {
        "ead_amount": 10000,
        "rwa_amount": 5000,
        "expected_loss": 1000
    },
    
    "thresholds_segment_materiality": {
        "reference": {
            "tab": "seg_axes == 'pole_pmas'",
            "measure": "materiality",
            "top": 10
        },
        "ead_amount": {
            "segment": "(seg_agg5 > 100000) | ((seg_agg5 > 10000) & (deviation > 3))",
            "rank": "(rank <= 30) & (rank_axes <= 10)"
        },
        "rwa_amount": {
            "segment": "(seg_agg5 > 50000) | ((seg_agg5 > 5000) & (deviation > 3))",
            "rank": "(rank <= 30) & (rank_axes <= 10)"
        }
    },
    
    "thresholds_line_anomaly": {
        "ead_amount": 0.5,
        "rwa_amount": 0.5,
        "lgd_rate": 0.3,
        "pd_rate": 0.3
    },
    
    "thresholds_topline": {
        "ead_amount": 1000000,
        "rwa_amount": 500000
    },
    
    "nb_last": 3,
    "nb_periods": -1,
    "nbs_last": 2,
    "s_window": 4,
    "materiality_metric": "metric1"
}
```

### 3.2 Axes Hierarchy (Dashboard Labels)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DETECT CRR Dashboard                                │
│                    Horizontal Hierarchical Unfolding                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Label 1        Label 2        Label 3         Label 4         Label 5     │
│  ────────       ────────       ────────        ────────        ────────    │
│  Pôle PMAS  →   PMA/Métier  →  Corep Class  →  Basel Appr  →  Risk Site   │
│                                                                             │
│  ┌─────────┐   ┌─────────┐    ┌──────────┐    ┌──────────┐   ┌──────────┐  │
│  │ PMA_03  │→  │ PMA_50  │→   │ CEC500   │→   │ NI_C (2) │→  │ SITE_001 │  │
│  │ PMA_05  │   │ PMA_51  │    │ CEC400   │    │ NI_F (3) │   │ SITE_002 │  │
│  │ PMA_08  │   │ PMA_325 │    │ CEC313   │    │          │   │ SITE_003 │  │
│  │ PMA_300 │   │ PMA_502 │    │ CEC410   │    │          │   │          │  │
│  │ PMA_512 │   │ PMA_558 │    │ CEC411   │    │          │   │          │  │
│  │ PMA_513 │   │ PMA_6700│    │ CEC412   │    │          │   │          │  │
│  │ PMA_527 │   │  ...    │    │ CEC441   │    │          │   │          │  │
│  └─────────┘   └─────────┘    │ CEC520   │    └──────────┘   └──────────┘  │
│                               └──────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Pipeline Architecture

### 4.1 High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DETECT CRR Pipeline                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ╔═══════════════╗                                                          │
│  ║   TERADATA    ║                                                          │
│  ║  TD_PRD_RP_CRR║                                                          │
│  ╚═══════╤═══════╝                                                          │
│          │                                                                  │
│          ▼                                                                  │
│  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐             │
│  │ SYNC Recipe   │────▶│  CRR_INPUT    │────▶│  AGGREGATE    │             │
│  │ (SQL Query)   │     │  (HDFS/ORC)   │     │  (PySpark)    │             │
│  └───────────────┘     └───────────────┘     └───────┬───────┘             │
│                                                       │                     │
│                                                       ▼                     │
│  ┌───────────────────────────────────────────────────────────────────┐     │
│  │                      DETECT_CORE                                   │     │
│  ├───────────────────────────────────────────────────────────────────┤     │
│  │                                                                    │     │
│  │   detect_axe()  ─────────▶  SP_anomalies_crr                      │     │
│  │                                                                    │     │
│  │   detect_core() ─────────▶  Deviation calculation                 │     │
│  │                            Expected = Median(T-4, T-3, T-2, T-1)  │     │
│  │                            Deviation = (Current - Expected) / Exp │     │
│  │                                                                    │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                  │                                          │
│                                  ▼                                          │
│  ┌───────────────┐     ┌───────────────┐     ┌───────────────┐             │
│  │ POST-PROCESS  │────▶│ SP_toplines   │────▶│ SP_display    │             │
│  │               │     │ SP_display_seg│     │ _toplines     │             │
│  └───────────────┘     └───────────────┘     └───────┬───────┘             │
│                                                       │                     │
│                                                       ▼                     │
│                                              ╔═══════════════╗              │
│                                              ║   TABLEAU     ║              │
│                                              ║   Dashboard   ║              │
│                                              ╚═══════════════╝              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 DSS Project Structure

```
DETECT_CRR/
├── 📁 Data Sources
│   ├── 🔗 TD_PRD_RP_CRR (Teradata Connection)
│   │   ├── V_EXPO_CLIENT_AR
│   │   └── V_EXPO_FACILITE_AR
│   │
│   └── 📁 Managed Folders
│       └── crr_params_folder/
│           └── crr_params.json
│
├── 📁 Datasets
│   ├── 📊 CRR_input_raw          (Sync from Teradata)
│   ├── 📊 CRR_input_joined       (Client + Facility)
│   ├── 📊 CRR_input_aggregated   (GroupBy axes + period)
│   ├── 📊 SP_anomalies_crr       (DETECT output)
│   ├── 📊 SP_toplines_crr        
│   ├── 📊 SP_display_seg_crr     
│   └── 📊 SP_display_toplines_crr
│
├── 📁 Recipes
│   ├── 🔧 sync_crr_data          (SQL - Teradata extract)
│   ├── 🔧 join_client_facility   (PySpark)
│   ├── 🔧 aggregate_segments     (PySpark)
│   ├── 🔧 compute_detect_core    (Python - detect_core)
│   ├── 🔧 post_process_anomalies (Python)
│   └── 🔧 prepare_tableau_output (PySpark)
│
├── 📁 Scenarios
│   ├── ▶️ SCN_DETECT_CRR_MAIN    (Full pipeline)
│   └── ▶️ SCN_DETECT_CRR_REFRESH (Incremental)
│
├── 📁 Webapps
│   └── 🌐 CRR_Investigation_Tool (Dash)
│
├── 📁 Libraries
│   └── 📦 detect_core_lib/
│       ├── models.py
│       ├── detect_core.py
│       ├── detect_axe.py
│       └── post_processing.py
│
└── 📁 Wiki
    ├── 📄 CRR_DETECT_Guide.md
    └── 📄 Threshold_Calibration.md
```

---

## 5. Target Variables Mapping

### 5.1 IFRS9 vs CRR Comparison

| IFRS9 Variable | CRR Equivalent | Source Column | Aggregation |
|----------------|----------------|---------------|-------------|
| `ead_ifrs9` | `ead_amount` | MT_EXPO_RISQ_TOT | SUM |
| `provision_ifrs9` | `expected_loss` | MT_PERT_ATT_EXPO_TOT | SUM |
| `lgd_pit_ifrs9` | `lgd_rate` | TX_LGD | WAVG (by EAD) |
| `eir` | `pd_rate` | TX_PD_1 | WAVG (by EAD) |
| `ltv` | N/A | - | - |
| `residual_maturity` | N/A | - | - |
| N/A | `rwa_amount` | MT_RISQ_POND_TOT | SUM |

### 5.2 Detection Use Cases

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CRR Anomaly Detection Use Cases                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USE CASE 1: EAD Amount Anomaly                                            │
│  ─────────────────────────────────                                          │
│  Target: MT_EXPO_RISQ_TOT (sum by segment)                                 │
│  Question: "Est-ce que l'exposition totale de ce segment a bougé          │
│             anormalement par rapport à la tendance historique?"            │
│                                                                             │
│  USE CASE 2: RWA Amount Anomaly                                            │
│  ─────────────────────────────────                                          │
│  Target: MT_RISQ_POND_TOT (sum by segment)                                 │
│  Question: "Est-ce que les actifs pondérés de ce segment ont varié        │
│             de manière inattendue?"                                        │
│                                                                             │
│  USE CASE 3: LGD Rate Anomaly                                              │
│  ─────────────────────────────────                                          │
│  Target: TX_LGD (weighted avg by EAD)                                      │
│  Question: "Est-ce que le taux de LGD moyen du segment s'écarte           │
│             de la normale?"                                                 │
│                                                                             │
│  USE CASE 4: RWA Density Check                                             │
│  ─────────────────────────────────                                          │
│  Target: RWA / EAD ratio                                                   │
│  Question: "Est-ce que la densité RWA est cohérente avec l'historique?"   │
│                                                                             │
│  ⚠️  NOTE: Ces use cases détectent des ANOMALIES dans les métriques.       │
│      Ils NE détectent PAS directement les "Missing LGD Models".           │
│      Le lien est INDIRECT: une anomalie peut SIGNALER un problème         │
│      sous-jacent incluant potentiellement des erreurs de modèle.          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Algorithm Adaptation

### 6.1 DETECT Core Algorithm (Unchanged)

```python
# detect_core.py - No modification needed

def compute_expected_value(historical_values: List[float], method: str = "median") -> float:
    """
    Compute expected value from historical data.
    
    For CRR: Use median of last 4-6 quarters
    Same as IFRS9/CCIRC implementation.
    """
    if method == "median":
        return np.median(historical_values)
    elif method == "mad_median":
        # MAD-clipped median (V2)
        median = np.median(historical_values)
        mad = np.median(np.abs(historical_values - median))
        # Clip outliers before computing final median
        clipped = [v for v in historical_values if abs(v - median) <= 3 * mad]
        return np.median(clipped) if clipped else median
    else:
        return np.mean(historical_values)


def compute_deviation(current: float, expected: float) -> float:
    """
    Compute signed deviation.
    
    Deviation = (Current - Expected) / Expected
    
    Positive = Increase (blue in dashboard)
    Negative = Decrease (red in dashboard)
    """
    if expected == 0:
        return 0.0 if current == 0 else float('inf')
    return (current - expected) / expected


def classify_anomaly(deviation: float, threshold: float, 
                     is_new: bool = False, is_vanish: bool = False,
                     is_negligible: bool = False) -> str:
    """
    Classify anomaly type.
    
    Returns: NORMAL, OUTLIER, NEW, VANISH, NEGLIGIBLE
    """
    if is_negligible:
        return "NEGLIGIBLE"
    if is_new:
        return "NEW"
    if is_vanish:
        return "VANISH"
    if abs(deviation) > threshold:
        return "OUTLIER"
    return "NORMAL"
```

### 6.2 Aggregation Layer (CRR-Specific)

```python
# aggregate_crr.py

from pyspark.sql import functions as F
from pyspark.sql import Window

def aggregate_crr_segments(df_input, axes_list, target_vars, weight_vars, period_col="id_run"):
    """
    Aggregate facility-level data to segment level.
    
    Parameters:
    -----------
    df_input : DataFrame
        Joined CLIENT + FACILITY data
    axes_list : List[List[str]]
        Hierarchy of axes, e.g. [["pole_pmas"], ["pole_pmas", "pma"], ...]
    target_vars : Dict[str, List[str]]
        Variables and their aggregations
    weight_vars : Dict[str, str]
        Weight variable for weighted averages
    
    Returns:
    --------
    DataFrame with aggregated segments
    """
    
    result_dfs = []
    
    for axes in axes_list:
        axes_key = "|".join(axes)
        group_cols = [period_col] + axes
        
        # Build aggregation expressions
        agg_exprs = []
        
        for var, agg_funcs in target_vars.items():
            for agg_func in agg_funcs:
                if agg_func == "sum":
                    agg_exprs.append(F.sum(var).alias(f"{var}_sum"))
                elif agg_func == "avg":
                    agg_exprs.append(F.avg(var).alias(f"{var}_avg"))
                elif agg_func == "count":
                    agg_exprs.append(F.count(var).alias(f"{var}_count"))
                elif agg_func == "wavg" and var in weight_vars:
                    # Weighted average: sum(var * weight) / sum(weight)
                    weight_col = weight_vars[var]
                    agg_exprs.append(
                        (F.sum(F.col(var) * F.col(weight_col)) / F.sum(weight_col))
                        .alias(f"{var}_wavg")
                    )
        
        # Aggregate
        df_agg = (df_input
                  .groupBy(group_cols)
                  .agg(*agg_exprs)
                  .withColumn("seg_axes", F.lit(axes_key)))
        
        result_dfs.append(df_agg)
    
    # Union all segment levels
    return reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), result_dfs)
```

---

## 7. Dashboard Integration

### 7.1 Tableau Workbook Structure

```
CRR_DETECT_Dashboard.twbx
├── 📊 Toplines Overview
│   ├── Heatmap: Pôle × Quarter
│   ├── KPIs: Total EAD, RWA, Anomaly Count
│   └── Trend: EAD Evolution by Pôle
│
├── 📊 Segment Investigation
│   ├── Hierarchical Unfolding (Label 1-5)
│   ├── Deviation Coloring (Blue=↑, Red=↓)
│   └── Anomaly Classification Filter
│
├── 📊 Line Investigation
│   ├── Top Deviated Facilities
│   ├── Facility Details (Client, LGD Model, etc.)
│   └── Historical Trend per Facility
│
└── 📊 Model Analysis (CRR-Specific)
    ├── LGD Model Distribution by Segment
    ├── Missing LGD Model Count
    └── Model Anomaly Correlation
```

### 7.2 Color Coding (Same as IFRS9/CCIRC)

```
┌────────────────────────────────────────────────────────┐
│  Classification    │  Color       │  Meaning           │
├────────────────────┼──────────────┼────────────────────┤
│  NORMAL            │  ⬜ Gray      │  Within threshold  │
│  OUTLIER (↑)       │  🟦 Blue     │  Increase anomaly  │
│  OUTLIER (↓)       │  🟥 Red      │  Decrease anomaly  │
│  NEW               │  🟩 Green    │  First appearance  │
│  VANISH            │  🟧 Orange   │  Disappeared       │
│  NEGLIGIBLE        │  ⬜ Light    │  Below materiality │
└────────────────────┴──────────────┴────────────────────┘
```

---

## 8. Implementation Roadmap

### Phase 1: Data Validation (1 semaine)
- [ ] Confirmer accès aux données historiques
- [ ] Vérifier qualité des colonnes (nulls, distribution)
- [ ] Valider le join CLIENT ↔ FACILITY

### Phase 2: Pipeline Setup (2 semaines)
- [ ] Créer projet DSS DETECT_CRR
- [ ] Implémenter recipes de sync et aggregation
- [ ] Configurer crr_params.json
- [ ] Tester detect_core sur données CRR

### Phase 3: Calibration (1 semaine)
- [ ] Ajuster thresholds par axe
- [ ] Définir seuils de negligibility
- [ ] Valider avec équipe CRR

### Phase 4: Dashboard & UAT (2 semaines)
- [ ] Adapter Tableau workbook
- [ ] Tests utilisateurs avec CRR
- [ ] Documentation et formation

### Phase 5: Production (1 semaine)
- [ ] Deployment sur Automation node
- [ ] Scheduling des scenarios
- [ ] Monitoring et alerting

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pas de données historiques | **Critical** | Demander extraction historique ou switch vers Peer Comparison |
| Volume 3.2M records | Medium | Optimiser avec partitioning, cache Spark |
| Join CLIENT/FACILITY lent | Medium | Broadcast join si CLIENT < 10M rows |
| Seuils mal calibrés | Low | Période de calibration avec CRR |
| Changement de périmètre CRR | Low | Flexibilité via params.json |

---

## 10. Appendix

### A. Column Mapping Reference

| Source (Teradata) | DETECT Input | Description |
|-------------------|--------------|-------------|
| ID_RUN | period | Run identifier (quarter) |
| SK_FAC / ID_FAC_FCT | facility_id | Facility key |
| SK_CLI_CTRP → SK_CLI | client_id | Client key |
| CD_POLE_PMAS_AP_ACCRED | pole_pmas | Label 1 |
| CD_PMAS_AP_ACCRED | pma | Label 2 |
| CD_CLASS_EXPO_COREP_IRBA | corep_class | Label 3 |
| CD_TYP_APPRO_BALE_2 | basel_approach | Label 4 |
| CD_SIT_RISQ_AP_ACCRED | risk_site | Label 5 |
| MT_EXPO_RISQ_TOT | ead_amount | Target: EAD |
| MT_RISQ_POND_TOT | rwa_amount | Target: RWA |
| MT_PERT_ATT_EXPO_TOT | expected_loss | Target: EL |
| TX_LGD | lgd_rate | Target: LGD Rate |
| TX_PD_1 | pd_rate | Target: PD Rate |
| CD_MOD_LGD | lgd_model | Context: Model code |
| CD_MOD_LGD_SURCH_IRBA | lgd_model_irba | Context: Model IRBA |

### B. Sample SQL for Historical Extract

```sql
-- If historical data exists in archive table
SELECT 
    f.ID_RUN,
    f.SK_FAC,
    c.ID_CLI_FCT,
    f.CD_POLE_PMAS_AP_ACCRED,
    f.CD_PMAS_AP_ACCRED,
    f.CD_CLASS_EXPO_COREP_IRBA,
    f.CD_TYP_APPRO_BALE_2,
    f.CD_SIT_RISQ_AP_ACCRED,
    f.MT_EXPO_RISQ_TOT,
    f.MT_RISQ_POND_TOT,
    f.MT_PERT_ATT_EXPO_TOT,
    f.TX_LGD,
    f.TX_PD_1,
    f.CD_MOD_LGD,
    f.CD_MOD_LGD_SURCH_IRBA
FROM ${RP_SCHEMA_EXPOLAYER}."V_EXPO_FACILITE_AR_HIST" f
LEFT JOIN ${RP_SCHEMA_EXPOLAYER}."V_EXPO_CLIENT_AR_HIST" c 
    ON f.SK_CLI_CTRP = c.SK_CLI
    AND f.ID_RUN = c.ID_RUN
WHERE f.ID_RUN >= 2959  -- Last 6 quarters
ORDER BY f.ID_RUN, f.SK_FAC;
```

---

**Document Status**: Draft - Pending historical data confirmation

**Next Action**: 
1. CRR team to confirm availability of historical ID_RUN values
2. If confirmed → Proceed to Phase 1
3. If not available → Switch to Peer Comparison approach (separate design doc)
