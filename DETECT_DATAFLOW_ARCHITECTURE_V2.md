# DETECT Test Dataflow Architecture

---

## 📋 Document Information

| Field | Value |
|-------|-------|
| **Project** | DETECT - Anomaly Detection Platform |
| **Version** | 2.0 |
| **Author** | Data Engineering Team |
| **Last Updated** | April 2025 |
| **Status** | 🟢 Draft |

---

## 1. Executive Summary

This document defines the complete test dataflow architecture for the DETECT anomaly detection platform. The architecture covers **IFRS9**, **CCIRC**, and **ICAAP** regulatory flows across **Design** and **Automation** nodes in Dataiku DSS 14.

### 🎯 Objectives

- Ensure code quality through automated unit testing
- Prevent regression of known bugs
- Validate data pipeline outputs against reference datasets
- Enable safe production deployments with automatic rollback

---

## 2. Architecture Overview

### 2.1 Two-Node Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                        DETECT TEST ARCHITECTURE                                 │
│                                                                                 │
│  ┌───────────────────────────────┐       ┌───────────────────────────────┐     │
│  │                               │       │                               │     │
│  │      🔧 DESIGN NODE           │       │    🚀 AUTOMATION NODE         │     │
│  │         (SIT_JH)              │       │         (PROD)                │     │
│  │                               │       │                               │     │
│  │  ┌─────────────────────────┐  │       │  ┌─────────────────────────┐  │     │
│  │  │ ○ Execute Python test   │  │       │  │ ○ Compute metrics       │  │     │
│  │  │ ○ Integration test      │  │       │  │ ○ Run checks            │  │     │
│  │  │ ○ Regression test       │  │       │  │ ○ Post-deploy scenario  │  │     │
│  │  └─────────────────────────┘  │       │  └─────────────────────────┘  │     │
│  │              │                │       │              │                │     │
│  │              ▼                │       │              ▼                │     │
│  │  ┌─────────────────────────┐  │       │  ┌─────────────────────────┐  │     │
│  │  │                         │  │       │  │                         │  │     │
│  │  │   ☑ Create Bundle       │──────────▶  │   📊 Test Dashboard     │  │     │
│  │  │                         │  │ BUNDLE │  │      (JUnit XML)        │  │     │
│  │  └─────────────────────────┘  │       │  └─────────────────────────┘  │     │
│  │                               │       │                               │     │
│  └───────────────────────────────┘       └───────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Test Distribution Matrix

| Test Type | Design Node | Automation Node | Trigger |
|-----------|:-----------:|:---------------:|---------|
| Execute Python test | ✅ | ❌ | Pre-bundle |
| Integration test | ✅ | ❌ | Pre-bundle |
| Compute metrics + Run checks | ❌ | ✅ | Post-deploy (Hook) |
| Rollback scenario | ❌ | ✅ | On test failure |

---

## 3. Test Pyramid

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                              TEST PYRAMID                                       │
│                                                                                 │
│                                                                                 │
│                                   /\                                            │
│                                  /  \                                           │
│                                 /    \                                          │
│                                /      \                                         │
│                               / POST-  \                                        │
│                              / DEPLOY   \        ◁── Compute metrics            │
│                             /  < 2 min   \           Run checks                 │
│                            +--------------+          (Deployer Hook)            │
│                           /                \                                    │
│                          /   INTEGRATION    \    ◁── Compare datasets           │
│                         /     10-30 min      \       Reference vs Output        │
│                        +----------------------+                                 │
│                       /                        \                                │
│                      /       REGRESSION         \  ◁── 8 Known bugs             │
│                     /          < 1 min           \     Must never reappear      │
│                    +------------------------------+                             │
│                   /                                \                            │
│                  /         EXECUTE PYTHON TEST      \  ◁── pytest framework    │
│                 /             (Unit tests)           \     Individual functions │
│                +--------------------------------------+                         │
│                                                                                 │
│                                                                                 │
│   FEW ◁──────────────────── QUANTITY ──────────────────────▷ MANY              │
│   FAST ◁─────────────────── SPEED ─────────────────────────▷ SLOW              │
│   BROAD ◁────────────────── SCOPE ─────────────────────────▷ NARROW            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Deployment Workflow

### 4.1 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                           DEPLOYMENT WORKFLOW                                   │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  DESIGN NODE                                                                    │
│  ───────────                                                                    │
│                                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │          │    │ Execute  │    │          │    │Integraton│                  │
│  │   Code   │───▷│ Python   │───▷│Regression│───▷│   Test   │                  │
│  │  Commit  │    │  Test    │    │   Test   │    │(optional)│                  │
│  │          │    │          │    │          │    │          │                  │
│  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘                  │
│                                                       │                        │
│                                                       ▽                        │
│                                                 /────────\                     │
│                                                / All Pass? \                   │
│                                                \    ?      /                   │
│                                                 \────────/                     │
│                                                   │    │                       │
│                                              YES  │    │  NO                   │
│                                                   │    │                       │
│                                                   ▽    ▽                       │
│                                            ┌────────┐ ┌────────┐               │
│                                            │ Create │ │  Fix   │               │
│                                            │ Bundle │ │  Code  │               │
│                                            └───┬────┘ └────────┘               │
│                                                │                               │
│ ═══════════════════════════════════════════════╪═══════════════════════════════│
│                                                │                               │
│  AUTOMATION NODE                               │                               │
│  ───────────────                               ▽                               │
│                                          ┌───────────┐                         │
│                                          │  Deploy   │                         │
│                                          │  Bundle   │                         │
│                                          └─────┬─────┘                         │
│                                                │                               │
│                                                ▽                               │
│                                          ┌───────────┐                         │
│                                          │  Deployer │                         │
│                                          │   Hook    │                         │
│                                          │(post-dep.)│                         │
│                                          └─────┬─────┘                         │
│                                                │                               │
│                                                ▽                               │
│                                          ┌───────────┐                         │
│                                          │  Run Test │                         │
│                                          │  Scenario │                         │
│                                          └─────┬─────┘                         │
│                                                │                               │
│                                                ▽                               │
│                                          /────────\                            │
│                                         /  Tests   \                           │
│                                         \  Pass?   /                           │
│                                          \────────/                            │
│                                            │    │                              │
│                                       YES  │    │  NO                          │
│                                            │    │                              │
│                                            ▽    ▽                              │
│                                      ┌────────┐ ┌────────┐                     │
│                                      │SUCCESS │ │ROLLBACK│                     │
│                                      │  Done  │ │Previous│                     │
│                                      └────────┘ └───┬────┘                     │
│                                                     │                          │
│                                                     ▽                          │
│                                               ┌────────┐                       │
│                                               │ Alert  │                       │
│                                               │ & Fix  │                       │
│                                               └────────┘                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘


LEGEND:
───────
┌────────┐
│        │  =  Process / Action
└────────┘

/────────\
\        /  =  Decision
 \──────/

───▷       =  Flow direction
```

---

## 5. DSS Test Step Types

### 5.1 Official DSS Test Steps (DSS 14)

| Step Type | Description | Use Case |
|-----------|-------------|----------|
| **Execute Python test** | Run pytest from project libraries | Unit tests, regression tests |
| **Integration test** | Swap datasets, build, compare outputs | Pipeline validation |
| **Webapp test** | Verify webapp is running + request/response | UI validation |
| **Compute metrics** | Calculate dataset metrics | Post-deploy validation |
| **Run checks** | Validate data quality rules | Post-deploy validation |

### 5.2 DSS Recommended Test Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                    DSS RECOMMENDED TEST WORKFLOW                                │
│                    (from official documentation)                                │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                                                                                 │
│    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐             │
│    │             │         │             │         │             │             │
│    │   DESIGN    │ Bundle  │     QA      │ Bundle  │ PRODUCTION  │             │
│    │    NODE     │────────▷│ AUTOMATION  │────────▷│ AUTOMATION  │             │
│    │             │         │    NODE     │         │    NODE     │             │
│    │             │         │             │         │             │             │
│    └──────┬──────┘         └──────┬──────┘         └──────┬──────┘             │
│           │                       │                       │                    │
│           ▽                       ▽                       ▽                    │
│    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐             │
│    │ Create test │         │ Run tests   │         │ Run tests   │             │
│    │ scenarios   │         │ via Deployer│         │ via Deployer│             │
│    │             │         │ Hook        │         │ Hook        │             │
│    └─────────────┘         └─────────────┘         └─────────────┘             │
│                                   │                       │                    │
│                                   ▽                       ▽                    │
│                            ┌─────────────┐         ┌─────────────┐             │
│                            │ Test report │         │ Push report │             │
│                            │ for sign-off│         │ to Govern   │             │
│                            └─────────────┘         └─────────────┘             │
│                                                                                 │
│                                                                                 │
│    YOUR SETUP (2 nodes):                                                       │
│    ─────────────────────                                                       │
│                                                                                 │
│    ┌─────────────┐                              ┌─────────────┐                │
│    │             │                              │             │                │
│    │   DESIGN    │          Bundle              │ AUTOMATION  │                │
│    │    NODE     │─────────────────────────────▷│    NODE     │                │
│    │             │                              │   (PROD)    │                │
│    │             │                              │             │                │
│    └──────┬──────┘                              └──────┬──────┘                │
│           │                                            │                       │
│           ▽                                            ▽                       │
│    ┌─────────────┐                              ┌─────────────┐                │
│    │ Run ALL     │                              │ Run post-   │                │
│    │ tests here  │                              │ deploy test │                │
│    │ BEFORE      │                              │ via Hook    │                │
│    │ bundle      │                              │ (quick)     │                │
│    └─────────────┘                              └─────────────┘                │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Test Scenarios

### 6.1 Design Node Scenarios

#### 📋 Scenario List

| ID | Scenario Name | DSS Step Type | Duration |
|----|---------------|---------------|----------|
| 1 | TEST_UNIT_MODELS | Execute Python test | ~45s |
| 2 | TEST_UNIT_PREPROC | Execute Python test | ~30s |
| 3 | TEST_UNIT_POSTPROC | Execute Python test | ~25s |
| 4 | TEST_REGRESSION | Execute Python test | ~15s |
| 5 | TEST_INTEGRATION_IFRS9 | Integration test | ~12min |
| 6 | TEST_INTEGRATION_CCIRC | Integration test | ~10min |
| 7 | TEST_INTEGRATION_ICAAP | Integration test | ~10min |

#### 📝 TEST_UNIT_MODELS

| Property | Value |
|----------|-------|
| **DSS Step Type** | Execute Python test |
| **Location** | `lib/python/test/test_models.py` |
| **Code Environment** | py39_detect_test (with pytest) |
| **Mark as Test Scenario** | ✅ Yes |

**Test Cases:**

| Test | Description | Related Bug |
|------|-------------|-------------|
| `test_classify_normal` | Normal classification within threshold | - |
| `test_classify_outlier_positive` | Positive deviation outlier | - |
| `test_classify_outlier_negative` | Negative deviation outlier | - |
| `test_classify_new` | New data point (no history) | BUG-003 |
| `test_classify_vanish` | Vanished data point | - |
| `test_classify_negligible` | Both expected AND observed small | BUG-001 |
| `test_classify_spike` | Sudden spike detection | - |
| `test_mad_calculation` | MAD robust estimation | - |
| `test_deviation_no_division_by_zero` | Division by zero protection | BUG-002 |

#### 📝 TEST_REGRESSION

| Property | Value |
|----------|-------|
| **DSS Step Type** | Execute Python test |
| **Location** | `lib/python/test/test_known_bugs.py` |
| **Purpose** | Ensure 8 known bugs never reappear |

**Covered Bugs:**

| Bug ID | Module | Description |
|--------|--------|-------------|
| BUG-001 | models.py | NEGLIGIBLE only checked expected |
| BUG-002 | models.py | Deviation used loop index `i` |
| BUG-003 | models.py | NEW used `and` not `or` |
| BUG-004 | models.py | Undefined `stop` variable |
| BUG-005 | post_processing.py | Segment used `!=` not `==` |
| BUG-006 | post_processing.py | Empty DataFrame concat |
| BUG-007 | tests | `setupClass` casing |
| BUG-008 | pre_processing.py | Delimiter `__` vs `\|` |

### 6.2 Automation Node Scenarios

#### 🔥 TEST_POST_DEPLOY

| Property | Value |
|----------|-------|
| **DSS Step Types** | Compute metrics + Run checks |
| **Trigger** | Deployer Hook (post-deployment) |
| **Duration** | < 2 minutes |
| **On Failure** | Trigger SCN_ROLLBACK |

**Steps:**

| Step | DSS Step Type | Action |
|------|---------------|--------|
| 1 | Compute metrics | `SP_anomalies` row count |
| 2 | Run checks | `row_count > 0` |
| 3 | Compute metrics | `Toplines_dataviz` row count |
| 4 | Run checks | `row_count > 0` |
| 5 | Run checks | No NULL in key columns |

#### ⏪ SCN_ROLLBACK

| Property | Value |
|----------|-------|
| **DSS Step Type** | Execute Python code |
| **Trigger** | On TEST_POST_DEPLOY failure |
| **Duration** | < 1 minute |

**Steps:**

| Step | Action |
|------|--------|
| 1 | Get previous bundle ID from history |
| 2 | Activate previous bundle |
| 3 | Send alert email to team |

---

## 7. Integration Test Flow

### 7.1 Step-by-Step Pipeline Testing

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                    INTEGRATION TEST FLOW (PER STEP)                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STEP 1: PRE-PROCESSING                                                        │
│  ──────────────────────                                                         │
│                                                                                 │
│    ┌────────────┐       ┌────────────┐       ┌────────────┐                    │
│    │            │       │            │       │            │                    │
│    │ ref_fem    │──────▷│ Pre-Proc   │──────▷│ prep_data  │                    │
│    │ ref_tiers  │       │  Recipe    │       │  (output)  │                    │
│    │            │       │            │       │            │                    │
│    └────────────┘       └────────────┘       └─────┬──────┘                    │
│         INPUT               PROCESS                │                           │
│                                                    ▽                           │
│                                              /──────────\                      │
│                                             /  Compare   \                     │
│                                             \    vs      /                     │
│                                              \ref_prep  /                      │
│                                               \────────/                       │
│                                                                                 │
│  STEP 2: MODELING                                                              │
│  ────────────────                                                               │
│                                                                                 │
│    ┌────────────┐       ┌────────────┐       ┌────────────┐                    │
│    │            │       │            │       │            │                    │
│    │ prep_data  │──────▷│detect_core │──────▷│ anomalies  │                    │
│    │            │       │  Recipe    │       │  (output)  │                    │
│    │            │       │            │       │            │                    │
│    └────────────┘       └────────────┘       └─────┬──────┘                    │
│         INPUT               PROCESS                │                           │
│                                                    ▽                           │
│                                              /──────────\                      │
│                                             /  Compare   \                     │
│                                             \    vs      /                     │
│                                              \ref_anom  /                      │
│                                               \────────/                       │
│                                                                                 │
│  STEP 3: POST-PROCESSING                                                       │
│  ───────────────────────                                                        │
│                                                                                 │
│    ┌────────────┐       ┌────────────┐       ┌────────────┐                    │
│    │            │       │            │       │            │                    │
│    │ anomalies  │──────▷│ Segments & │──────▷│ toplines   │                    │
│    │            │       │   Ranks    │       │  (output)  │                    │
│    │            │       │            │       │            │                    │
│    └────────────┘       └────────────┘       └─────┬──────┘                    │
│         INPUT               PROCESS                │                           │
│                                                    ▽                           │
│                                              /──────────\                      │
│                                             /  Compare   \                     │
│                                             \    vs      /                     │
│                                              \ref_top   /                      │
│                                               \────────/                       │
│                                                                                 │
│                                                                                 │
│  LEGEND:                                                                       │
│  ───────                                                                        │
│  ┌────────────┐                                                                │
│  │            │  =  Dataset                                                    │
│  └────────────┘                                                                │
│                                                                                 │
│  /──────────\                                                                  │
│  \          /  =  Comparison / Decision                                        │
│   \────────/                                                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Test Data Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                         TEST DATA ARCHITECTURE                                  │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  📁 Managed Folder: test_reference_data/                                        │
│                                                                                 │
│  ├── 📁 inputs/                                                                 │
│  │   ├── 📄 ref_fem_sample.parquet ──────── 2000 rows + edge cases             │
│  │   ├── 📄 ref_tiers_sample.parquet ────── Matching counterparties            │
│  │   └── 📄 ref_ifrs9_params.json ───────── Config with pipe delimiter         │
│  │                                                                              │
│  ├── 📁 expected_outputs/                                                       │
│  │   ├── 📁 step1_pre_processing/                                              │
│  │   │   ├── 📄 ref_prep_ifrs9.parquet                                         │
│  │   │   ├── 📄 ref_prep_ccirc.parquet                                         │
│  │   │   └── 📄 ref_prep_icaap.parquet                                         │
│  │   ├── 📁 step2_modeling/                                                    │
│  │   │   ├── 📄 ref_anomalies_ifrs9.parquet                                    │
│  │   │   ├── 📄 ref_anomalies_ccirc.parquet                                    │
│  │   │   └── 📄 ref_anomalies_icaap.parquet                                    │
│  │   └── 📁 step3_post_processing/                                             │
│  │       ├── 📄 ref_toplines_ifrs9.parquet                                     │
│  │       ├── 📄 ref_toplines_ccirc.parquet                                     │
│  │       └── 📄 ref_toplines_icaap.parquet                                     │
│  │                                                                              │
│  └── 📁 edge_cases/                                                             │
│      ├── 📄 division_by_zero.parquet                                           │
│      ├── 📄 negligible_both_small.parquet                                      │
│      ├── 📄 all_null_history.parquet                                           │
│      └── 📄 empty_dataframe.parquet                                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Project Libraries Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                      PROJECT LIBRARIES STRUCTURE                                │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  📁 DETECT_IFRS9/lib/python/                                                    │
│                                                                                 │
│  ├── 📁 detect_core/                      ◁── PRODUCTION CODE                  │
│  │   ├── 📄 __init__.py                                                        │
│  │   ├── 📄 models.py ──────────────────── detect_core, detect_axes            │
│  │   ├── 📄 pre_processing.py ──────────── enrich_data_period_*                │
│  │   ├── 📄 post_processing.py ─────────── segments, ranks, toplines           │
│  │   └── 📄 config.py ──────────────────── load/validate ifrs9_params.json     │
│  │                                                                              │
│  ├── 📁 test/                             ◁── TEST CODE (pytest)               │
│  │   ├── 📄 __init__.py                                                        │
│  │   ├── 📄 conftest.py ────────────────── Shared fixtures                     │
│  │   ├── 📄 test_models.py ─────────────── Unit tests for models.py            │
│  │   ├── 📄 test_pre_processing.py ─────── Unit tests for pre_processing.py    │
│  │   ├── 📄 test_post_processing.py ────── Unit tests for post_processing.py   │
│  │   └── 📄 test_known_bugs.py ─────────── Regression tests (8 bugs)           │
│  │                                                                              │
│  └── 📄 pytest.ini                        ◁── pytest configuration             │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Rollback Mechanism

### 10.1 Bundle History

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                    AUTOMATION NODE - BUNDLE HISTORY                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┬────────────┬────────────────┬─────────────────────────┐   │
│  │  Bundle ID      │  Status    │  Deploy Date   │  Post-Deploy Test       │   │
│  ├─────────────────┼────────────┼────────────────┼─────────────────────────┤   │
│  │  v2024.12.3     │  🔴 ACTIVE │  2024-12-15    │  ❌ FAILED              │   │
│  │  v2024.12.2     │  🟢 AVAIL  │  2024-12-10    │  ✅ PASSED ◁── TARGET   │   │
│  │  v2024.12.1     │  ⚪ AVAIL  │  2024-12-05    │  ✅ PASSED              │   │
│  │  v2024.11.5     │  ⚪ AVAIL  │  2024-11-28    │  ✅ PASSED              │   │
│  └─────────────────┴────────────┴────────────────┴─────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Rollback Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                            ROLLBACK FLOW                                        │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│                                                                                 │
│                          ┌─────────────────┐                                    │
│                          │                 │                                    │
│                          │ Deploy Bundle   │                                    │
│                          │   v2024.12.3    │                                    │
│                          │                 │                                    │
│                          └────────┬────────┘                                    │
│                                   │                                             │
│                                   ▽                                             │
│                          ┌─────────────────┐                                    │
│                          │                 │                                    │
│                          │ Deployer Hook   │                                    │
│                          │ (post-deploy)   │                                    │
│                          │                 │                                    │
│                          └────────┬────────┘                                    │
│                                   │                                             │
│                                   ▽                                             │
│                          ┌─────────────────┐                                    │
│                          │                 │                                    │
│                          │ TEST_POST_DEPLOY│                                    │
│                          │   scenario      │                                    │
│                          │                 │                                    │
│                          └────────┬────────┘                                    │
│                                   │                                             │
│                                   ▽                                             │
│                            /─────────────\                                      │
│                           /               \                                     │
│                          /   Tests Pass?   \                                    │
│                          \                 /                                    │
│                           \               /                                     │
│                            \─────────────/                                      │
│                                │     │                                          │
│                           YES  │     │  NO                                      │
│                                │     │                                          │
│                                ▽     ▽                                          │
│                    ┌───────────────┐ ┌───────────────┐                          │
│                    │               │ │               │                          │
│                    │   SUCCESS     │ │  SCN_ROLLBACK │                          │
│                    │     Done      │ │  Activate     │                          │
│                    │               │ │  v2024.12.2   │                          │
│                    └───────────────┘ └───────┬───────┘                          │
│                                              │                                  │
│                                              ▽                                  │
│                                    ┌───────────────┐                            │
│                                    │               │                            │
│                                    │  Send Alert   │                            │
│                                    │  to Team      │                            │
│                                    │               │                            │
│                                    └───────────────┘                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 11. Test Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                            TEST DASHBOARD                                       │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  Project: DETECT_IFRS9_PROD     Bundle: v2024.12.3     Node: AUTOMATION        │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │  📊 TEST SCENARIOS                                                        │ │
│  │                                                                           │ │
│  │  ┌──────────────────────┬──────────┬──────────┬──────────┬─────────────┐ │ │
│  │  │ Scenario             │ Status   │ Duration │ Last Run │ Actions     │ │ │
│  │  ├──────────────────────┼──────────┼──────────┼──────────┼─────────────┤ │ │
│  │  │ TEST_UNIT_MODELS     │ ✅ PASS  │ 45s      │ 2h ago   │ [Log][Rpt]  │ │ │
│  │  │ TEST_UNIT_PREPROC    │ ✅ PASS  │ 32s      │ 2h ago   │ [Log][Rpt]  │ │ │
│  │  │ TEST_UNIT_POSTPROC   │ ✅ PASS  │ 28s      │ 2h ago   │ [Log][Rpt]  │ │ │
│  │  │ TEST_REGRESSION      │ ✅ PASS  │ 15s      │ 2h ago   │ [Log][Rpt]  │ │ │
│  │  │ TEST_INTEGRATION_*   │ ✅ PASS  │ 12m 30s  │ 1h ago   │ [Log][Rpt]  │ │ │
│  │  │ TEST_POST_DEPLOY     │ ✅ PASS  │ 1m 45s   │ 30m ago  │ [Log][Rpt]  │ │ │
│  │  └──────────────────────┴──────────┴──────────┴──────────┴─────────────┘ │ │
│  │                                                                           │ │
│  │  Summary: 6/6 PASSED                                                      │ │
│  │                                                                           │ │
│  │  [📥 Export JUnit XML]  [📄 Export HTML Report]                           │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Implementation Checklist

### 12.1 Design Node

| # | Task | Status |
|---|------|--------|
| 1 | Create `lib/python/test/` directory structure | ⬜ TODO |
| 2 | Write `test_models.py` (Execute Python test) | ⬜ TODO |
| 3 | Write `test_pre_processing.py` (Execute Python test) | ⬜ TODO |
| 4 | Write `test_post_processing.py` (Execute Python test) | ⬜ TODO |
| 5 | Write `test_known_bugs.py` (regression) | ⬜ TODO |
| 6 | Create `pytest.ini` with markers | ⬜ TODO |
| 7 | Create `conftest.py` with fixtures | ⬜ TODO |
| 8 | Create Managed Folder: `test_reference_data` | ⬜ TODO |
| 9 | Generate reference input samples | ⬜ TODO |
| 10 | Generate expected output datasets | ⬜ TODO |
| 11 | Create TEST_UNIT_* scenarios | ⬜ TODO |
| 12 | Create TEST_REGRESSION scenario | ⬜ TODO |
| 13 | Create TEST_INTEGRATION_* scenarios | ⬜ TODO |
| 14 | Mark all as "Test Scenario" for Dashboard | ⬜ TODO |

### 12.2 Automation Node

| # | Task | Status |
|---|------|--------|
| 1 | Create TEST_POST_DEPLOY scenario | ⬜ TODO |
| 2 | Create SCN_ROLLBACK scenario | ⬜ TODO |
| 3 | Configure Deployer Hook (post-deployment) | ⬜ TODO |
| 4 | Configure rollback trigger on failure | ⬜ TODO |
| 5 | Verify Test Dashboard displays results | ⬜ TODO |
| 6 | Test rollback mechanism manually | ⬜ TODO |

---

## 13. Timeline

| Phase | Tasks | Duration |
|-------|-------|----------|
| **Phase 1** | Project library structure + pytest.ini | 2 days |
| **Phase 2** | Execute Python test (unit tests) | 5 days |
| **Phase 3** | Regression tests (8 bugs) | 2 days |
| **Phase 4** | Reference data generation | 2 days |
| **Phase 5** | Design node scenarios | 3 days |
| **Phase 6** | Automation node scenarios | 2 days |
| **Phase 7** | Test Dashboard + validation | 1 day |
| **Total** | | **~3 weeks** |

---

## 14. Summary

| Component | DSS Term | Description |
|-----------|----------|-------------|
| **Unit tests** | Execute Python test | pytest for individual functions |
| **Regression tests** | Execute Python test | 8 known bugs |
| **Pipeline tests** | Integration test | Dataset comparison |
| **Post-deploy tests** | Compute metrics + Run checks | Quick validation via Deployer Hook |
| **Rollback** | Execute Python code | Revert to previous bundle |

---

## 15. References

| Document | URL |
|----------|-----|
| Testing a project | https://doc.dataiku.com/dss/latest/scenarios/test_scenarios.html |
| Scenario steps | https://doc.dataiku.com/dss/latest/scenarios/steps.html |
| Deployment infrastructures | https://doc.dataiku.com/dss/latest/deployment/project-deployment-infrastructures.html |
| Tutorial: Test scenarios | https://knowledge.dataiku.com/latest/automate-tasks/scenarios/tutorial-test-scenarios.html |
