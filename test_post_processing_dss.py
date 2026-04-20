"""
================================================================================
TEST CASES FOR DSS NOTEBOOK: top_anomalies_line_par
================================================================================

Copy this code into a DSS Notebook (compute_SP_display_seg or new notebook)
to test the ORIGINAL vs UPDATED version of top_anomalies_line_par

Flow: POST_PROCESSING
Inputs: SP_anomalies (df_seg), SP_toplines_cumul (df_tlines)
Outputs: SP_top_seg, SP_display_seg, SP_display_toplines

================================================================================
"""

# =============================================================================
# CELL 1: IMPORTS AND SETUP
# =============================================================================

import json
import pandas as pd
import numpy as np
from dataiku import pandasutils as pdu
import dataiku

# Import the function to test
from core.post_processing import top_anomalies_line_par
from core.constants import AnomalyType, PERIOD_CLONE

# =============================================================================
# CELL 2: LOAD DATA FROM DATASETS
# =============================================================================

# Read recipe inputs
SP_anomalies = dataiku.Dataset("SP_anomalies")
df_seg = SP_anomalies.get_dataframe()

SP_toplines_cumul = dataiku.Dataset("SP_toplines_cumul")
df_tlines = SP_toplines_cumul.get_dataframe()

print("=" * 70)
print("DATA LOADED")
print("=" * 70)
print(f"df_seg (SP_anomalies): {df_seg.shape[0]} rows, {df_seg.shape[1]} columns")
print(f"df_tlines (SP_toplines_cumul): {df_tlines.shape[0]} rows, {df_tlines.shape[1]} columns")

# =============================================================================
# CELL 3: LOAD PARAMETERS FROM PROJECT VARIABLES
# =============================================================================

dss_client = dataiku.api_client()
project = dss_client.get_default_project()
variables = project.get_variables()

# Local variables
period_run = variables['local']['period_run']
scope_run = variables['local']['scope_run']
id_set_parameters = variables['local']['id_set_params']

# Standard variables
line_fac_col = variables['standard']['line_fac_col']
flow_type = variables['standard']['flow_type']
line_materiality_col = variables['standard']['line_materiality_col']
line_id_cols = variables['standard']['line_id_cols']

thresholds_segment_materiality = variables['standard']['thresholds_segment_materiality']
if isinstance(thresholds_segment_materiality, str):
    thresholds_segment_materiality = json.loads(thresholds_segment_materiality)

target_detection_mapping = variables['standard']['target_detection_mapping']

# Text mapping
text_mapping = {
    "mt_cal_ead_tot_b": "ead", "residual_maturity": "maturity",
    "lgd_pit_ifrs9": "lgd_pit", "lgd_before_flex": "lgd_bf", "eir": "eir", "el_ratio": "el_ratio",
    "ltv": "ltv", "entity": "entity", "migration_matrix": "mmatrix",
    "basel_approach_type_arc": "approach", "stage": "stage",
    "accounting_site_code_post_acc": "accounting", "asset_class": "asset",
    "rating_code": "rating", "provision12": "provision12", "provision3": "provision3",
    "lgd_diff": "lgd_diff", "provision_uni": "provision_uni",
    "ead_ifrs9": "ead_ifrs9", "provision_ifrs9": "provision_ifrs9", "rating_code_num": "rating_code_num",
    "cd_secteur_nace2": "cd_secteur_nace2", "pd_model": "pd_model", "z_model_name": "z_model_name", 
    "product_code": "product_code", "cd_secteur_activite": "cd_secteur_activite", 
    "stage3": "stage3", "business_country": "business_country"
}

segment_filters = variables['standard']['segment_filters']
segment_conditions = variables['standard']['segment_conditions']
thresholds_line_anomaly = variables['standard']['thresholds_line_anomaly']

t_agg_mean_mapping = {"agg4": False, "agg5": True}

print("=" * 70)
print("PARAMETERS LOADED")
print("=" * 70)
print(f"period_run: {period_run}")
print(f"scope_run: {scope_run}")
print(f"flow_type: {flow_type}")
print(f"line_materiality_col: {line_materiality_col}")

# =============================================================================
# CELL 4: DATA EXPLORATION - CHECK ANOMALY DISTRIBUTION
# =============================================================================

print("=" * 70)
print("ANOMALY DISTRIBUTION IN df_seg (SP_anomalies)")
print("=" * 70)

# Overall distribution
print("\n--- Overall Anomaly Distribution ---")
print(df_seg['anomaly'].value_counts().sort_index())

# Distribution by period
print(f"\n--- Anomaly Distribution for period_run ({period_run}) ---")
df_period_run = df_seg[df_seg['period_clone'] == period_run]
print(f"Total rows: {len(df_period_run)}")
print(f"NORMAL (0): {(df_period_run['anomaly'] == 0).sum()}")
print(f"OUTLIER (1): {(df_period_run['anomaly'] == 1).sum()}")
print(f"NEW (2): {(df_period_run['anomaly'] == 2).sum()}")
print(f"VANISH (3): {(df_period_run['anomaly'] == 3).sum()}")

print(f"\n--- Anomaly Distribution for historical periods ---")
df_historical = df_seg[df_seg['period_clone'] != period_run]
print(f"Total rows: {len(df_historical)}")
print(f"NORMAL (0): {(df_historical['anomaly'] == 0).sum()}")
print(f"ANOMALY (!=0): {(df_historical['anomaly'] != 0).sum()}")

# =============================================================================
# CELL 5: DEFINE ORIGINAL VERSION (WITH BUG)
# =============================================================================

def top_anomalies_line_par_ORIGINAL(df_seg, df_line, period_run, scope_run,
                                     line_materiality_col, line_fac_col, thresholds_line_anomaly,
                                     thresholds_segment_materiality, flow_type, id_set_parameters,
                                     line_id_cols, target_detection_mapping, 
                                     segment_filters, segment_conditions, text_mapping,
                                     model_type="basic", line_topn_final=10, 
                                     line_topn_run=50, line_topn_ref=100):
    """
    ORIGINAL VERSION - Calls the original function WITHOUT anomaly filter
    Returns df_seg_topn_cumul for analysis
    """
    from core.post_processing import top_segment_par
    from core.constants import (TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE, 
                                 SEGMENT_ID, RANK, RANK_AXES, SEG_FILTER_PREFIX, 
                                 SEG_CONDITION_PREFIX, MODEL_TYPE, PERIOD_CLONE)
    
    # Filter by model_type
    df_seg_filtered = df_seg[df_seg['model_type'] == model_type].copy()
    
    if df_seg_filtered.empty:
        print(f"[ORIGINAL] No data for model_type={model_type}")
        return None
    
    # Get target_variable
    target_variable = df_seg_filtered['t_variable_clone'].values[0]
    
    # Get t_agg_name_mapping from target_detection_mapping
    t_agg_name_mapping = {}
    for key, value in target_detection_mapping.items():
        if isinstance(value, dict) and 't_agg_name' in value:
            t_agg_name_mapping[key] = value['t_agg_name']
    
    # Call top_segment_par to get top segments
    df_seg_topn = top_segment_par(df_seg_filtered, period_run, scope_run, 
                                   thresholds_segment_materiality, id_set_parameters,
                                   target_variable, t_agg_name_mapping, 
                                   segment_filters, segment_conditions, text_mapping)
    
    if df_seg_topn is None or df_seg_topn.empty:
        print(f"[ORIGINAL] top_segment_par returned empty")
        return None
    
    # Build select_cols
    select_cols = ([TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE, SEGMENT_ID, RANK, RANK_AXES] +
                   [col for col in df_seg_topn.columns if col.startswith(SEG_FILTER_PREFIX)
                    or col.startswith(SEG_CONDITION_PREFIX)])
    
    available_cols = [c for c in select_cols if c in df_seg_topn.columns]
    
    # Merge to get cumulative data - NO ANOMALY FILTER (BUG!)
    df_seg_topn_cumul = pd.merge(df_seg_filtered, df_seg_topn[available_cols],
                                  on=[TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE])
    
    return df_seg_topn_cumul


# =============================================================================
# CELL 6: DEFINE UPDATED VERSION (WITH FIX)
# =============================================================================

def top_anomalies_line_par_UPDATED(df_seg, df_line, period_run, scope_run,
                                    line_materiality_col, line_fac_col, thresholds_line_anomaly,
                                    thresholds_segment_materiality, flow_type, id_set_parameters,
                                    line_id_cols, target_detection_mapping,
                                    segment_filters, segment_conditions, text_mapping,
                                    model_type="basic", line_topn_final=10,
                                    line_topn_run=50, line_topn_ref=100):
    """
    UPDATED VERSION - WITH anomaly filter for period_run
    Returns df_seg_topn_cumul for analysis
    """
    from core.post_processing import top_segment_par
    from core.constants import (TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE,
                                 SEGMENT_ID, RANK, RANK_AXES, SEG_FILTER_PREFIX,
                                 SEG_CONDITION_PREFIX, MODEL_TYPE, PERIOD_CLONE,
                                 AnomalyType)
    
    # Filter by model_type
    df_seg_filtered = df_seg[df_seg['model_type'] == model_type].copy()
    
    if df_seg_filtered.empty:
        print(f"[UPDATED] No data for model_type={model_type}")
        return None
    
    # Get target_variable
    target_variable = df_seg_filtered['t_variable_clone'].values[0]
    
    # Get t_agg_name_mapping from target_detection_mapping
    t_agg_name_mapping = {}
    for key, value in target_detection_mapping.items():
        if isinstance(value, dict) and 't_agg_name' in value:
            t_agg_name_mapping[key] = value['t_agg_name']
    
    # Call top_segment_par
    df_seg_topn = top_segment_par(df_seg_filtered, period_run, scope_run,
                                   thresholds_segment_materiality, id_set_parameters,
                                   target_variable, t_agg_name_mapping,
                                   segment_filters, segment_conditions, text_mapping)
    
    if df_seg_topn is None or df_seg_topn.empty:
        print(f"[UPDATED] top_segment_par returned empty")
        return None
    
    # Build select_cols
    select_cols = ([TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE, SEGMENT_ID, RANK, RANK_AXES] +
                   [col for col in df_seg_topn.columns if col.startswith(SEG_FILTER_PREFIX)
                    or col.startswith(SEG_CONDITION_PREFIX)])
    
    available_cols = [c for c in select_cols if c in df_seg_topn.columns]
    
    # Merge
    df_seg_topn_cumul = pd.merge(df_seg_filtered, df_seg_topn[available_cols],
                                  on=[TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE])
    
    # ====================================================================
    # FIX: ANOMALY FILTER
    # For period_run: keep ONLY anomalies (exclude NORMAL=0)
    # For historical periods: keep ALL data (normal + anomaly)
    # ====================================================================
    mask_historical = df_seg_topn_cumul[PERIOD_CLONE] != period_run
    mask_period_run_anomaly = (
        (df_seg_topn_cumul[PERIOD_CLONE] == period_run) & 
        (df_seg_topn_cumul['anomaly'] != AnomalyType.NORMAL)
    )
    
    rows_before = len(df_seg_topn_cumul)
    df_seg_topn_cumul = df_seg_topn_cumul[mask_historical | mask_period_run_anomaly]
    rows_after = len(df_seg_topn_cumul)
    
    print(f"[UPDATED] Anomaly filter: {rows_before} -> {rows_after} rows")
    print(f"[UPDATED] Removed {rows_before - rows_after} NORMAL rows from period_run")
    # ====================================================================
    
    return df_seg_topn_cumul


# =============================================================================
# CELL 7: TEST CASE 1 - ORIGINAL VERSION (BUG DEMONSTRATION)
# =============================================================================

print("=" * 70)
print("TEST CASE 1: ORIGINAL VERSION (BUG DEMONSTRATION)")
print("=" * 70)

df_cumul_original = top_anomalies_line_par_ORIGINAL(
    df_seg, df_tlines, period_run, scope_run,
    line_materiality_col, line_fac_col, thresholds_line_anomaly,
    thresholds_segment_materiality, flow_type, id_set_parameters,
    line_id_cols, target_detection_mapping,
    segment_filters, segment_conditions, text_mapping,
    model_type="basic"
)

if df_cumul_original is not None:
    # Check period_run data
    df_period_run_orig = df_cumul_original[df_cumul_original['period_clone'] == period_run]
    
    print(f"\n--- ORIGINAL: period_run ({period_run}) Analysis ---")
    print(f"Total rows: {len(df_period_run_orig)}")
    print(f"NORMAL (anomaly=0): {(df_period_run_orig['anomaly'] == 0).sum()}")
    print(f"ANOMALY (anomaly!=0): {(df_period_run_orig['anomaly'] != 0).sum()}")
    print(f"Anomaly types: {sorted(df_period_run_orig['anomaly'].unique())}")
    
    # BUG CHECK
    has_normal_in_period_run = (df_period_run_orig['anomaly'] == 0).sum() > 0
    if has_normal_in_period_run:
        print("\n⚠️ BUG CONFIRMED: period_run contains NORMAL (anomaly=0) rows!")
    else:
        print("\n✓ No bug detected (but check if anomaly filter was applied elsewhere)")
else:
    print("ERROR: ORIGINAL version returned None")


# =============================================================================
# CELL 8: TEST CASE 2 - UPDATED VERSION (FIX DEMONSTRATION)
# =============================================================================

print("\n" + "=" * 70)
print("TEST CASE 2: UPDATED VERSION (FIX DEMONSTRATION)")
print("=" * 70)

df_cumul_updated = top_anomalies_line_par_UPDATED(
    df_seg, df_tlines, period_run, scope_run,
    line_materiality_col, line_fac_col, thresholds_line_anomaly,
    thresholds_segment_materiality, flow_type, id_set_parameters,
    line_id_cols, target_detection_mapping,
    segment_filters, segment_conditions, text_mapping,
    model_type="basic"
)

if df_cumul_updated is not None:
    # Check period_run data
    df_period_run_upd = df_cumul_updated[df_cumul_updated['period_clone'] == period_run]
    
    print(f"\n--- UPDATED: period_run ({period_run}) Analysis ---")
    print(f"Total rows: {len(df_period_run_upd)}")
    print(f"NORMAL (anomaly=0): {(df_period_run_upd['anomaly'] == 0).sum()}")
    print(f"ANOMALY (anomaly!=0): {(df_period_run_upd['anomaly'] != 0).sum()}")
    print(f"Anomaly types: {sorted(df_period_run_upd['anomaly'].unique())}")
    
    # FIX CHECK
    has_normal_in_period_run = (df_period_run_upd['anomaly'] == 0).sum() > 0
    if not has_normal_in_period_run:
        print("\n✅ FIX CONFIRMED: period_run contains NO NORMAL rows!")
    else:
        print("\n❌ FIX FAILED: period_run still contains NORMAL rows")
else:
    print("ERROR: UPDATED version returned None")


# =============================================================================
# CELL 9: TEST CASE 3 - COMPARISON TABLE
# =============================================================================

print("\n" + "=" * 70)
print("TEST CASE 3: SIDE-BY-SIDE COMPARISON")
print("=" * 70)

if df_cumul_original is not None and df_cumul_updated is not None:
    print(f"\n{'Period':<12} {'Version':<10} {'Total':<8} {'Normal':<8} {'Anomaly':<8} {'Status':<12}")
    print("-" * 60)
    
    # Get all periods
    all_periods = sorted(df_cumul_original['period_clone'].unique())
    
    for period in all_periods:
        # Original
        df_orig_p = df_cumul_original[df_cumul_original['period_clone'] == period]
        orig_normal = (df_orig_p['anomaly'] == 0).sum()
        orig_anomaly = (df_orig_p['anomaly'] != 0).sum()
        
        # Updated
        df_upd_p = df_cumul_updated[df_cumul_updated['period_clone'] == period]
        upd_normal = (df_upd_p['anomaly'] == 0).sum()
        upd_anomaly = (df_upd_p['anomaly'] != 0).sum()
        
        is_period_run = (period == period_run)
        
        if is_period_run:
            orig_status = "⚠️ BUG" if orig_normal > 0 else "✓"
            upd_status = "✅ FIXED" if upd_normal == 0 else "❌"
        else:
            orig_status = "✓"
            upd_status = "✓"
        
        print(f"{period:<12} {'ORIGINAL':<10} {len(df_orig_p):<8} {orig_normal:<8} {orig_anomaly:<8} {orig_status:<12}")
        print(f"{'':<12} {'UPDATED':<10} {len(df_upd_p):<8} {upd_normal:<8} {upd_anomaly:<8} {upd_status:<12}")
        print("-" * 60)


# =============================================================================
# CELL 10: TEST CASE 4 - HISTORICAL DATA UNCHANGED
# =============================================================================

print("\n" + "=" * 70)
print("TEST CASE 4: VERIFY HISTORICAL DATA UNCHANGED")
print("=" * 70)

if df_cumul_original is not None and df_cumul_updated is not None:
    # Historical data
    df_hist_orig = df_cumul_original[df_cumul_original['period_clone'] != period_run]
    df_hist_upd = df_cumul_updated[df_cumul_updated['period_clone'] != period_run]
    
    print(f"\nOriginal historical rows: {len(df_hist_orig)}")
    print(f"Updated historical rows: {len(df_hist_upd)}")
    
    if len(df_hist_orig) == len(df_hist_upd):
        print("✅ Historical row counts match!")
    else:
        print(f"❌ Historical row counts differ: {len(df_hist_orig)} vs {len(df_hist_upd)}")
    
    # Check NORMAL rows still exist in historical
    hist_normal_orig = (df_hist_orig['anomaly'] == 0).sum()
    hist_normal_upd = (df_hist_upd['anomaly'] == 0).sum()
    
    print(f"\nOriginal historical NORMAL rows: {hist_normal_orig}")
    print(f"Updated historical NORMAL rows: {hist_normal_upd}")
    
    if hist_normal_upd > 0:
        print("✅ Historical periods still contain NORMAL data (correct)")
    else:
        print("⚠️ No NORMAL data in historical periods")


# =============================================================================
# CELL 11: SUMMARY REPORT
# =============================================================================

print("\n" + "=" * 70)
print("SUMMARY REPORT")
print("=" * 70)

if df_cumul_original is not None and df_cumul_updated is not None:
    # Counts
    orig_period_run = df_cumul_original[df_cumul_original['period_clone'] == period_run]
    upd_period_run = df_cumul_updated[df_cumul_updated['period_clone'] == period_run]
    
    orig_normal_count = (orig_period_run['anomaly'] == 0).sum()
    upd_normal_count = (upd_period_run['anomaly'] == 0).sum()
    
    print(f"""
┌─────────────────────────────────────────────────────────────────────┐
│                        TEST RESULTS                                 │
├─────────────────────────────────────────────────────────────────────┤
│ period_run: {period_run:<56} │
│ scope_run: {scope_run:<57} │
├─────────────────────────────────────────────────────────────────────┤
│ ORIGINAL VERSION:                                                   │
│   - period_run rows: {len(orig_period_run):<47} │
│   - NORMAL rows in period_run: {orig_normal_count:<37} │
│   - Status: {'⚠️ BUG - Contains NORMAL data' if orig_normal_count > 0 else '✓ OK':<45} │
├─────────────────────────────────────────────────────────────────────┤
│ UPDATED VERSION:                                                    │
│   - period_run rows: {len(upd_period_run):<47} │
│   - NORMAL rows in period_run: {upd_normal_count:<37} │
│   - Status: {'✅ FIXED - No NORMAL data' if upd_normal_count == 0 else '❌ Still has NORMAL':<45} │
├─────────────────────────────────────────────────────────────────────┤
│ ROWS FILTERED: {len(orig_period_run) - len(upd_period_run):<53} │
└─────────────────────────────────────────────────────────────────────┘
    """)
    
    # Final verdict
    if orig_normal_count > 0 and upd_normal_count == 0:
        print("🎉 TEST PASSED: Bug demonstrated in ORIGINAL, Fix verified in UPDATED")
    elif orig_normal_count == 0:
        print("ℹ️ No NORMAL data in period_run - cannot demonstrate bug with this data")
    else:
        print("❌ TEST FAILED: UPDATED version still has NORMAL data in period_run")
