# “””

# ADDITIONAL BUG VERIFICATION TESTS

These tests verify the bugs identified by Claude Code review in VSCode.
Bugs are categorized as:

- F1-F5: Functional Bugs
- B1-B9: Business Logic Bugs

================================================================================
“””

import unittest
import pandas as pd
import numpy as np
from enum import IntEnum

# =============================================================================

# CONSTANTS

# =============================================================================

class AnomalyType(IntEnum):
ERROR = -1
NORMAL = 0
OUTLIER = 1
NEW = 2
VANISH = 3
NEGLIGIBLE = 4

class ModelType:
BASIC = “basic”
SEASONAL = “seasonal”

DEVIATION_NEW = 0.0
DEVIATION_OUTLIER = 1.0
DEVIATION_NEGLIGIBLE = 1.0
DEVIATION_ERROR = -1.0
ERR_DEFAULT_VAL = np.nan

# =============================================================================

# DETECT_CORE FUNCTION (current version)

# =============================================================================

def detect_core(
ts: pd.Series,
threshold_anomaly: float,
threshold_negligible: float,
nb_periods: int = -1,
season_length: int = 1,
nb_hist_points: int = 2
) -> tuple:
ts = ts.reset_index(drop=True)

```
if (nb_periods < 0) or (nb_periods > len(ts) - 1):
    nb_periods = len(ts) - 1

def _compute_at(i):
    if (i < len(ts) - nb_periods) or (i < season_length):
        return AnomalyType.NEW, DEVIATION_NEW, ts[i]

    try:
        stop = max(0, i - nb_hist_points * season_length)
        indices = list(range(i - season_length, stop - 1, -season_length))
        expected_val = ts[indices].median()

        if np.isnan(ts[i]):
            return AnomalyType.VANISH, DEVIATION_OUTLIER, expected_val
        elif abs(expected_val) < threshold_negligible:
            return AnomalyType.NEGLIGIBLE, DEVIATION_NEGLIGIBLE, expected_val
        else:
            deviation = np.absolute(1 - ts[i] / expected_val)
            if deviation >= threshold_anomaly:
                return AnomalyType.OUTLIER, deviation, expected_val
            else:
                return AnomalyType.NORMAL, deviation, expected_val

    except Exception as err:
        print(f"Exception at index {i}: {err}")
        return AnomalyType.ERROR, DEVIATION_ERROR, ERR_DEFAULT_VAL

if len(ts) < 1 + season_length:
    if season_length > 1:
        return [AnomalyType.NEW] * len(ts), [DEVIATION_NEW] * len(ts), list(ts), ModelType.SEASONAL
    else:
        return [AnomalyType.NEW] * len(ts), [DEVIATION_NEW] * len(ts), list(ts), ModelType.BASIC
else:
    res = [_compute_at(i) for i in range(len(ts))]
    if season_length > 1:
        return [e[0] for e in res], [e[1] for e in res], [e[2] for e in res], ModelType.SEASONAL
    else:
        return [e[0] for e in res], [e[1] for e in res], [e[2] for e in res], ModelType.BASIC
```

# =============================================================================

# FUNCTIONAL BUG TESTS (F1-F5)

# =============================================================================

class TestFunctionalBugs(unittest.TestCase):
“”“Tests for Functional Bugs F1-F5”””

```
def test_F1_all_nan_history_valid_observed(self):
    """
    F1: All-NaN history + valid observed → false NORMAL with NaN deviation
    
    Root Cause: abs(NaN) < threshold is False, falls through to NORMAL
    """
    # History is all NaN, but current value is valid
    ts = pd.Series([np.nan, np.nan, np.nan, 100.0])
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01
    )
    
    print(f"\n[F1] All-NaN history + valid observed:")
    print(f"     ts = {list(ts)}")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Deviation: {deviations[3]}")
    print(f"     Expected: {expected_values[3]}")
    
    # BUG: Returns NORMAL with NaN deviation instead of handling gracefully
    if anomalies[3] == AnomalyType.NORMAL and np.isnan(deviations[3]):
        print("     ❌ BUG CONFIRMED: NORMAL with NaN deviation")
        self.skipTest("F1 Bug confirmed: All-NaN history produces false NORMAL")
    
def test_F2_zero_division_when_threshold_zero(self):
    """
    F2: 0/0 division → false NORMAL with NaN deviation
    
    Root Cause: threshold_negligible=0 bypasses protection, 0/0 = NaN
    """
    ts = pd.Series([0.0, 0.0, 0.0, 0.0])
    threshold_negligible = 0.0  # Disables NEGLIGIBLE protection
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, threshold_negligible
    )
    
    print(f"\n[F2] Zero division (threshold_negligible=0):")
    print(f"     ts = {list(ts)}")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Deviation: {deviations[3]}")
    
    # BUG: 0/0 = NaN, NaN >= threshold is False → NORMAL
    if np.isnan(deviations[3]):
        print("     ❌ BUG CONFIRMED: 0/0 produces NaN deviation")
        self.skipTest("F2 Bug confirmed: 0/0 division not handled")

def test_F3_nb_hist_points_zero(self):
    """
    F3: nb_hist_points=0 → empty historical window → NaN expected
    
    Root Cause: range produces empty list, .median() = NaN
    """
    ts = pd.Series([100.0, 100.0, 100.0, 200.0])
    nb_hist_points = 0
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01, nb_hist_points=nb_hist_points
    )
    
    print(f"\n[F3] nb_hist_points=0:")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Expected: {expected_values[3]}")
    
    # BUG: Empty indices list → NaN expected
    if np.isnan(expected_values[3]):
        print("     ❌ BUG CONFIRMED: Empty window produces NaN expected")
        self.skipTest("F3 Bug confirmed: nb_hist_points=0 not validated")

def test_F4_season_length_zero(self):
    """
    F4: season_length=0 → range(step=0) → ValueError → ERROR
    
    Root Cause: No input validation, range(..., -0) raises exception
    """
    ts = pd.Series([100.0, 100.0, 100.0, 200.0])
    season_length = 0
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01, season_length=season_length
    )
    
    print(f"\n[F4] season_length=0:")
    print(f"     Results: {[AnomalyType(a).name for a in anomalies]}")
    
    # BUG: All become ERROR due to ValueError in range()
    if any(a == AnomalyType.ERROR for a in anomalies):
        print("     ❌ BUG CONFIRMED: season_length=0 causes errors")
        self.skipTest("F4 Bug confirmed: season_length=0 not validated")

def test_F5_inconsistent_return_type(self):
    """
    F5: Inconsistent return type - short series returns Series, normal returns list
    
    Root Cause: L119 returns ts (Series) vs L125 returns list
    """
    # Short series (len < 1 + season_length)
    ts_short = pd.Series([100.0])
    _, _, expected_short, _ = detect_core(ts_short, 0.3, 0.01)
    
    # Normal series
    ts_normal = pd.Series([100.0, 100.0, 100.0])
    _, _, expected_normal, _ = detect_core(ts_normal, 0.3, 0.01)
    
    print(f"\n[F5] Inconsistent return type:")
    print(f"     Short series expected type: {type(expected_short)}")
    print(f"     Normal series expected type: {type(expected_normal)}")
    
    # Check if types differ
    short_is_series = isinstance(expected_short, pd.Series)
    normal_is_list = isinstance(expected_normal, list)
    
    if short_is_series and normal_is_list:
        print("     ❌ BUG CONFIRMED: Inconsistent return types")
        self.skipTest("F5 Bug confirmed: Inconsistent return types")
    elif short_is_series or not normal_is_list:
        print(f"     Note: Types are {type(expected_short)} and {type(expected_normal)}")
```

# =============================================================================

# BUSINESS LOGIC BUG TESTS (B1-B9)

# =============================================================================

class TestBusinessLogicBugs(unittest.TestCase):
“”“Tests for Business Logic Bugs B1-B9”””

```
def test_B1_nb_periods_zero_disables_detection(self):
    """
    B1: nb_periods=0 disables all detection (everything is NEW)
    
    Impact: Outliers completely invisible
    """
    ts = pd.Series([100.0, 100.0, 100.0, 1000000.0])  # Obvious outlier
    nb_periods = 0
    
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01, nb_periods=nb_periods)
    
    print(f"\n[B1] nb_periods=0:")
    print(f"     ts = {list(ts)}")
    print(f"     Results: {[AnomalyType(a).name for a in anomalies]}")
    
    # BUG: All points become NEW, outlier not detected
    if all(a == AnomalyType.NEW for a in anomalies):
        print("     ❌ BUG CONFIRMED: All points are NEW, outlier missed!")
        self.skipTest("B1 Bug confirmed: nb_periods=0 disables detection")

def test_B2_negligible_strict_less_than(self):
    """
    B2: Negligible uses strict < not <= — boundary value escapes
    
    Impact: expected == threshold → extreme deviation possible
    """
    threshold_negligible = 0.01
    # expected = 0.01 (exactly at threshold)
    ts = pd.Series([0.01, 0.01, 0.01, 1000.0])
    
    anomalies, deviations, _, _ = detect_core(
        ts, 0.3, threshold_negligible
    )
    
    print(f"\n[B2] Negligible strict < (expected=threshold):")
    print(f"     expected = 0.01, threshold_negligible = 0.01")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Deviation: {deviations[3]:.2f}")
    
    # BUG: abs(0.01) < 0.01 is False, so extreme deviation calculated
    if anomalies[3] != AnomalyType.NEGLIGIBLE and deviations[3] > 1000:
        print("     ❌ BUG CONFIRMED: Extreme deviation at boundary")

def test_B3_near_zero_expected_extreme_deviation(self):
    """
    B3: Near-zero expected just above threshold → extreme deviation
    
    Impact: Small denominator produces misleading numbers
    """
    # expected = 0.011 (just above threshold of 0.01)
    ts = pd.Series([0.011, 0.011, 0.011, 1000.0])
    
    anomalies, deviations, _, _ = detect_core(ts, 0.3, 0.01)
    
    print(f"\n[B3] Near-zero expected (0.011):")
    print(f"     expected = 0.011, observed = 1000")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Deviation: {deviations[3]:.2f}")
    
    # Note: deviation = |1 - 1000/0.011| ≈ 90908
    if deviations[3] > 1000:
        print(f"     ⚠️ Extreme deviation: {deviations[3]:.0f}")
        print("     This is technically correct but may be misleading")

def test_B4_vanish_with_nan_expected(self):
    """
    B4: VANISH with NaN expected when all history is NaN
    
    Impact: Corrupts downstream materiality calculations
    """
    ts = pd.Series([np.nan, np.nan, np.nan, np.nan])
    
    anomalies, deviations, expected_values, _ = detect_core(ts, 0.3, 0.01)
    
    print(f"\n[B4] VANISH with NaN expected:")
    print(f"     Results: {[AnomalyType(a).name for a in anomalies]}")
    print(f"     Expected values: {expected_values}")
    
    # Check if VANISH points have NaN expected
    for i in range(1, len(anomalies)):
        if anomalies[i] == AnomalyType.VANISH and np.isnan(expected_values[i]):
            print(f"     ⚠️ Index {i}: VANISH with NaN expected")

def test_B5_negligible_ignores_huge_observed(self):
    """
    B5: NEGLIGIBLE only checks expected, ignores huge observed
    
    Impact: expected=1e-6, observed=1M → NEGLIGIBLE, masking anomaly
    """
    ts = pd.Series([1e-6, 1e-6, 1e-6, 1000000.0])
    
    anomalies, _, expected_values, _ = detect_core(ts, 0.3, 0.01)
    
    print(f"\n[B5] NEGLIGIBLE ignores huge observed:")
    print(f"     expected = 1e-6, observed = 1,000,000")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    
    if anomalies[3] == AnomalyType.NEGLIGIBLE:
        print("     ❌ BUG CONFIRMED: 1M classified as NEGLIGIBLE!")
        self.skipTest("B5 Bug confirmed: NEGLIGIBLE ignores observed")

def test_B6_sign_flip_masked_by_negligible(self):
    """
    B6: Sign flip masked by negligible
    
    Impact: expected=-0.0005, observed=+1000 → NEGLIGIBLE
    """
    ts = pd.Series([-0.0005, -0.0005, -0.0005, 1000.0])
    
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01)
    
    print(f"\n[B6] Sign flip masked:")
    print(f"     expected = -0.0005, observed = +1000")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    
    if anomalies[3] == AnomalyType.NEGLIGIBLE:
        print("     ❌ BUG CONFIRMED: Sign flip + magnitude change masked!")
        self.skipTest("B6 Bug confirmed: Sign flip masked by NEGLIGIBLE")

def test_B7_negative_nb_hist_points(self):
    """
    B7: Negative nb_hist_points → empty indices problem
    
    Impact: No input validation, silent NaN propagation
    """
    ts = pd.Series([100.0, 100.0, 100.0, 200.0])
    nb_hist_points = -1
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01, nb_hist_points=nb_hist_points
    )
    
    print(f"\n[B7] Negative nb_hist_points:")
    print(f"     nb_hist_points = -1")
    print(f"     Result: {AnomalyType(anomalies[3]).name}")
    print(f"     Expected: {expected_values[3]}")
    
    if np.isnan(expected_values[3]) or anomalies[3] == AnomalyType.ERROR:
        print("     ❌ BUG CONFIRMED: Negative nb_hist_points not validated")
        self.skipTest("B7 Bug confirmed: Negative nb_hist_points not validated")

def test_B8_partial_nan_reduces_window(self):
    """
    B8: Partial NaN in history silently reduces comparison window
    
    Impact: pandas .median() drops NaN — 2-point window becomes 1-point
    """
    # Year 1: Q1=NaN, Year 2: Q1=100, Year 3: Q1=200 (current)
    ts = pd.Series([
        np.nan, 0, 0, 0,  # Year 1: Q1 is NaN
        100, 0, 0, 0,     # Year 2: Q1=100
        200, 0, 0, 0      # Year 3: Q1=200 (current)
    ])
    season_length = 4
    nb_hist_points = 2
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01,
        season_length=season_length,
        nb_hist_points=nb_hist_points
    )
    
    print(f"\n[B8] Partial NaN reduces window:")
    print(f"     History: Q1Y1=NaN, Q1Y2=100, Q1Y3=200")
    print(f"     nb_hist_points=2, but only 1 valid point")
    print(f"     Expected at index 8: {expected_values[8]}")
    
    # median([NaN, 100]) = 100 (NaN dropped, window reduced to 1)
    if expected_values[8] == 100.0:
        print("     ⚠️ Window silently reduced: median([NaN, 100]) = 100")

def test_B9_zero_observed_loses_materiality(self):
    """
    B9: Zero observed always gives deviation = 1.0 regardless of expected
    
    Impact: Drop from 10→0 same deviation as 1M→0
    """
    # Small drop: 10 → 0
    ts_small = pd.Series([10.0, 10.0, 10.0, 0.0])
    _, dev_small, _, _ = detect_core(ts_small, 0.3, 0.01)
    
    # Large drop: 1M → 0
    ts_large = pd.Series([1000000.0, 1000000.0, 1000000.0, 0.0])
    _, dev_large, _, _ = detect_core(ts_large, 0.3, 0.01)
    
    print(f"\n[B9] Zero observed loses materiality:")
    print(f"     10 → 0: deviation = {dev_small[3]:.2f}")
    print(f"     1M → 0: deviation = {dev_large[3]:.2f}")
    
    # Both give deviation = 1.0
    if dev_small[3] == dev_large[3] == 1.0:
        print("     ⚠️ Same deviation despite 100,000x difference in magnitude!")
        print("     Materiality information is lost")
```

# =============================================================================

# RUN TESTS

# =============================================================================

if **name** == “**main**”:
print(”\n” + “=”*80)
print(“VERIFYING BUGS FROM CLAUDE CODE REVIEW”)
print(”=”*80)

```
loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromTestCase(TestFunctionalBugs))
suite.addTests(loader.loadTestsFromTestCase(TestBusinessLogicBugs))

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Summary
print("\n" + "="*80)
print("VERIFICATION SUMMARY")
print("="*80)
print(f"Tests run:    {result.testsRun}")
print(f"Skipped:      {len(result.skipped)} (bugs confirmed)")
print(f"Failures:     {len(result.failures)}")
print(f"Errors:       {len(result.errors)}")

print("\n" + "="*80)
print("BUGS CONFIRMED")
print("="*80)
for test, reason in result.skipped:
    print(f"  ✓ {test}: {reason}")
```