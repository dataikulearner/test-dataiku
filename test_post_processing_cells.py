"""
================================================================================
DSS NOTEBOOK TEST CELLS - Copy từng cell vào notebook
================================================================================

Recipe: compute_SP_display_seg
Inputs: SP_anomalies, SP_toplines_cumul
Purpose: Test ORIGINAL vs UPDATED top_anomalies_line_par

================================================================================
"""

# ===========================================================================
# CELL 1: IMPORTS
# ===========================================================================
# Copy this cell first

import json
import pandas as pd
import numpy as np
import dataiku
from core.post_processing import top_segment_par
from core.constants import (
    TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE, SEGMENT_ID,
    RANK, RANK_AXES, SEG_FILTER_PREFIX, SEG_CONDITION_PREFIX,
    MODEL_TYPE, PERIOD_CLONE, AnomalyType
)

print("✓ Imports successful")


# ===========================================================================
# CELL 2: LOAD DATA
# ===========================================================================

df_seg = dataiku.Dataset("SP_anomalies").get_dataframe()
df_tlines = dataiku.Dataset("SP_toplines_cumul").get_dataframe()

print(f"df_seg: {df_seg.shape}")
print(f"df_tlines: {df_tlines.shape}")


# ===========================================================================
# CELL 3: LOAD VARIABLES
# ===========================================================================

project = dataiku.api_client().get_default_project()
variables = project.get_variables()

period_run = variables['local']['period_run']
scope_run = variables['local']['scope_run']
id_set_params = variables['local']['id_set_params']

thresholds_seg_materiality = variables['standard']['thresholds_segment_materiality']
if isinstance(thresholds_seg_materiality, str):
    thresholds_seg_materiality = json.loads(thresholds_seg_materiality)

target_detection_mapping = variables['standard']['target_detection_mapping']
segment_filters = variables['standard']['segment_filters']
segment_conditions = variables['standard']['segment_conditions']

text_mapping = {
    "mt_cal_ead_tot_b": "ead", "eir": "eir", "entity": "entity",
    "migration_matrix": "mmatrix", "basel_approach_type_arc": "approach",
    "stage": "stage", "accounting_site_code_post_acc": "accounting",
    "rating_code_num": "rating_code_num", "business_country": "business_country"
}

# Build t_agg_name_mapping
t_agg_name_mapping = {}
for key, value in target_detection_mapping.items():
    if isinstance(value, dict) and 't_agg_name' in value:
        t_agg_name_mapping[key] = value['t_agg_name']

print(f"period_run: {period_run}")
print(f"scope_run: {scope_run}")


# ===========================================================================
# CELL 4: CHECK ANOMALY DISTRIBUTION IN INPUT DATA
# ===========================================================================

print("=" * 60)
print(f"ANOMALY DISTRIBUTION - period_run = {period_run}")
print("=" * 60)

df_pr = df_seg[df_seg['period_clone'] == period_run]
print(f"\nperiod_run ({period_run}):")
print(f"  Total: {len(df_pr)}")
print(f"  NORMAL (0): {(df_pr['anomaly'] == 0).sum()}")
print(f"  OUTLIER (1): {(df_pr['anomaly'] == 1).sum()}")
print(f"  NEW (2): {(df_pr['anomaly'] == 2).sum()}")
print(f"  VANISH (3): {(df_pr['anomaly'] == 3).sum()}")

df_hist = df_seg[df_seg['period_clone'] != period_run]
print(f"\nHistorical:")
print(f"  Total: {len(df_hist)}")
print(f"  NORMAL (0): {(df_hist['anomaly'] == 0).sum()}")
print(f"  ANOMALY (!=0): {(df_hist['anomaly'] != 0).sum()}")


# ===========================================================================
# CELL 5: DEFINE TEST FUNCTION - SIMULATES MERGE STEP
# ===========================================================================

def test_merge_with_filter(df_seg, period_run, scope_run, model_type="basic", apply_filter=False):
    """
    Simulates the merge step in top_anomalies_line_par
    apply_filter=False -> ORIGINAL (BUG)
    apply_filter=True -> UPDATED (FIX)
    """
    # Filter by model_type
    df = df_seg[df_seg['model_type'] == model_type].copy()
    
    if df.empty:
        return None
        
    target_variable = df['t_variable_clone'].values[0]
    
    # Get top segments (simplified - just get period_run data)
    df_topn = top_segment_par(df, period_run, scope_run, 
                               thresholds_seg_materiality, id_set_params,
                               target_variable, t_agg_name_mapping,
                               segment_filters, segment_conditions, text_mapping)
    
    if df_topn is None or df_topn.empty:
        return None
    
    # Build select cols
    select_cols = [TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE, SEGMENT_ID, RANK, RANK_AXES]
    select_cols += [c for c in df_topn.columns if c.startswith(SEG_FILTER_PREFIX) or c.startswith(SEG_CONDITION_PREFIX)]
    available_cols = [c for c in select_cols if c in df_topn.columns]
    
    # Merge
    df_cumul = pd.merge(df, df_topn[available_cols], 
                        on=[TARGET_VARIABLE_CLONE, SEG_AXES, SEG_AXES_VALUE])
    
    # APPLY FILTER IF REQUESTED
    if apply_filter:
        mask_hist = df_cumul[PERIOD_CLONE] != period_run
        mask_pr_anom = (df_cumul[PERIOD_CLONE] == period_run) & (df_cumul['anomaly'] != AnomalyType.NORMAL)
        df_cumul = df_cumul[mask_hist | mask_pr_anom]
    
    return df_cumul


# ===========================================================================
# CELL 6: TEST ORIGINAL VERSION (NO FILTER - BUG)
# ===========================================================================

print("=" * 60)
print("TEST: ORIGINAL VERSION (NO FILTER)")
print("=" * 60)

df_original = test_merge_with_filter(df_seg, period_run, scope_run, apply_filter=False)

if df_original is not None:
    df_pr_orig = df_original[df_original['period_clone'] == period_run]
    normal_count = (df_pr_orig['anomaly'] == 0).sum()
    
    print(f"period_run rows: {len(df_pr_orig)}")
    print(f"NORMAL (0) in period_run: {normal_count}")
    print(f"Anomaly types: {sorted(df_pr_orig['anomaly'].unique())}")
    
    if normal_count > 0:
        print("\n⚠️ BUG: period_run CONTAINS NORMAL rows!")
    else:
        print("\n✓ No NORMAL rows in period_run")
else:
    print("ERROR: Original test returned None")


# ===========================================================================
# CELL 7: TEST UPDATED VERSION (WITH FILTER - FIX)
# ===========================================================================

print("=" * 60)
print("TEST: UPDATED VERSION (WITH FILTER)")
print("=" * 60)

df_updated = test_merge_with_filter(df_seg, period_run, scope_run, apply_filter=True)

if df_updated is not None:
    df_pr_upd = df_updated[df_updated['period_clone'] == period_run]
    normal_count = (df_pr_upd['anomaly'] == 0).sum()
    
    print(f"period_run rows: {len(df_pr_upd)}")
    print(f"NORMAL (0) in period_run: {normal_count}")
    print(f"Anomaly types: {sorted(df_pr_upd['anomaly'].unique()) if len(df_pr_upd) > 0 else 'N/A'}")
    
    if normal_count == 0:
        print("\n✅ FIX: period_run has NO NORMAL rows!")
    else:
        print("\n❌ FIX FAILED: period_run still has NORMAL rows")
else:
    print("ERROR: Updated test returned None")


# ===========================================================================
# CELL 8: COMPARISON SUMMARY
# ===========================================================================

print("=" * 60)
print("COMPARISON SUMMARY")
print("=" * 60)

if df_original is not None and df_updated is not None:
    # Period run comparison
    orig_pr = df_original[df_original['period_clone'] == period_run]
    upd_pr = df_updated[df_updated['period_clone'] == period_run]
    
    orig_normal = (orig_pr['anomaly'] == 0).sum()
    upd_normal = (upd_pr['anomaly'] == 0).sum()
    
    print(f"""
┌────────────────────────────────────────────────────────┐
│ period_run = {period_run:<42} │
├────────────────────────────────────────────────────────┤
│ ORIGINAL:                                              │
│   Rows: {len(orig_pr):<48} │
│   NORMAL: {orig_normal:<46} │
│   Status: {'⚠️ BUG' if orig_normal > 0 else '✓ OK':<46} │
├────────────────────────────────────────────────────────┤
│ UPDATED:                                               │
│   Rows: {len(upd_pr):<48} │
│   NORMAL: {upd_normal:<46} │
│   Status: {'✅ FIXED' if upd_normal == 0 else '❌ FAILED':<46} │
├────────────────────────────────────────────────────────┤
│ Rows filtered: {len(orig_pr) - len(upd_pr):<41} │
└────────────────────────────────────────────────────────┘
    """)
    
    # Historical comparison
    orig_hist = df_original[df_original['period_clone'] != period_run]
    upd_hist = df_updated[df_updated['period_clone'] != period_run]
    
    print(f"Historical rows - Original: {len(orig_hist)}, Updated: {len(upd_hist)}")
    if len(orig_hist) == len(upd_hist):
        print("✅ Historical data unchanged!")
    else:
        print(f"❌ Historical data changed: diff = {len(orig_hist) - len(upd_hist)}")


# ===========================================================================
# CELL 9: DETAILED PERIOD BREAKDOWN
# ===========================================================================

print("=" * 60)
print("DETAILED PERIOD BREAKDOWN")
print("=" * 60)

if df_original is not None and df_updated is not None:
    print(f"{'Period':<10} {'Orig':<8} {'Upd':<8} {'Orig_N':<8} {'Upd_N':<8} {'Status':<10}")
    print("-" * 60)
    
    for period in sorted(df_original['period_clone'].unique()):
        orig_p = df_original[df_original['period_clone'] == period]
        upd_p = df_updated[df_updated['period_clone'] == period]
        
        orig_n = (orig_p['anomaly'] == 0).sum()
        upd_n = (upd_p['anomaly'] == 0).sum()
        
        if period == period_run:
            status = "⚠️→✅" if orig_n > 0 and upd_n == 0 else "CHECK"
        else:
            status = "✓" if len(orig_p) == len(upd_p) else "DIFF"
        
        print(f"{period:<10} {len(orig_p):<8} {len(upd_p):<8} {orig_n:<8} {upd_n:<8} {status:<10}")
