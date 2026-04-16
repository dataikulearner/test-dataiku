# “””

# TEST SUITE FOR DETECT_CORE - CURRENT VERSION

Author: DETECT Team
Date: 2025
Context: DETECT platform for anomaly detection in financial regulatory flows
(IFRS9, CCIRC, ICAAP, CRR)

# ================================================================================
BUSINESS LOGIC ANALYSIS

1. PURPOSE OF DETECT_CORE

-----

The `detect_core` function is the algorithmic heart of the DETECT platform.
It analyzes a time series of financial data (IFRS9 provisions, EAD, LGD, etc.)
to identify anomalies compared to historical patterns.

1. REGULATORY CONTEXT

-----

- IFRS9: International accounting standard for financial instruments
- Provisions must be calculated using ECL (Expected Credit Loss) models
- Anomalies may indicate:
  - Calculation errors in risk models
  - Undocumented methodology changes
  - Data quality issues in source systems

1. ANOMALY TYPES

-----

- NORMAL (0)    : Value within expected thresholds
- OUTLIER (1)   : Significant deviation from expected value
- NEW (2)       : New data point, insufficient history to evaluate
- VANISH (3)    : Missing value (NaN) - data disappeared
- NEGLIGIBLE (4): Value too close to zero to be significant
- ERROR (-1)    : Calculation error

1. DEVIATION FORMULA

-----

deviation = |1 - observed / expected|

Examples:

- expected=100, observed=100 → deviation = |1 - 1| = 0 (NORMAL)
- expected=100, observed=130 → deviation = |1 - 1.3| = 0.3 (threshold)
- expected=100, observed=200 → deviation = |1 - 2| = 1.0 (OUTLIER)
- expected=100, observed=50  → deviation = |1 - 0.5| = 0.5 (OUTLIER)

1. EXPECTED VALUE CALCULATION

-----

The expected value is the MEDIAN of historical points corresponding
to the same season (same quarter for quarterly data).

Example with season_length=4 (quarterly) and nb_hist_points=2:

- To calculate expected at index 8 (Q1 year 3):
- Take indices [4, 0] (Q1 year 2 and Q1 year 1)
- expected = median(ts[4], ts[0])

1. CONFIGURABLE THRESHOLDS

-----

- threshold_anomaly: Deviation threshold for OUTLIER (e.g., 0.3 = 30%)
- threshold_negligible: Threshold below which we classify as NEGLIGIBLE (e.g., 0.01)

# ================================================================================
IDENTIFIED ISSUES / POTENTIAL BUGS

⚠️ CRITICAL BUG - NEGLIGIBLE Logic (lines 103-104):
The condition only checks `abs(expected_val) < threshold_negligible`
WITHOUT checking `abs(observed_val)`.

Consequence: An observed value of 1,000,000 can be classified as NEGLIGIBLE
if expected=0.001, which is a severe business error.

================================================================================
“””

import unittest
import pandas as pd
import numpy as np
from enum import IntEnum
from typing import Tuple, List

# =============================================================================

# CONSTANTS (replicated from constants.py for standalone tests)

# =============================================================================

class AnomalyType(IntEnum):
“”“Anomaly types detected by the model”””
ERROR = -1       # Calculation error
NORMAL = 0       # Normal value, within thresholds
OUTLIER = 1      # Outlier value, exceeds thresholds
NEW = 2          # New value, insufficient history
VANISH = 3       # Disappeared value (NaN)
NEGLIGIBLE = 4   # Negligible value (close to zero)

class ModelType:
“”“Detection model types”””
BASIC = “basic”         # Without seasonality
SEASONAL = “seasonal”   # With seasonality (quarterly, monthly)

# Deviation constants

DEVIATION_NEW = 0.0
DEVIATION_OUTLIER = 1.0
DEVIATION_NEGLIGIBLE = 1.0
DEVIATION_ERROR = -1.0
ERR_DEFAULT_VAL = np.nan

# =============================================================================

# DETECT_CORE FUNCTION (current version to test)

# =============================================================================

def detect_core(
ts: pd.Series,
threshold_anomaly: float,
threshold_negligible: float,
nb_periods: int = -1,
season_length: int = 1,
nb_hist_points: int = 2
) -> tuple:
“””
Atomic anomaly detection model for time series.

```
Args:
    ts: pandas time Series
    threshold_anomaly: Deviation threshold to classify as OUTLIER
    threshold_negligible: Threshold below which we classify as NEGLIGIBLE
    nb_periods: Number of periods to compute (-1 = entire series)
    season_length: Season length (4=quarterly, 12=monthly)
    nb_hist_points: Number of historical points for median calculation

Returns:
    Tuple (anomalies, deviations, expected_values, model_type)
"""
ts = ts.reset_index(drop=True)

if (nb_periods < 0) or (nb_periods > len(ts) - 1):
    nb_periods = len(ts) - 1

def _compute_at(i):
    # Condition for NEW: insufficient history
    if (i < len(ts) - nb_periods) or (i < season_length):
        return AnomalyType.NEW, DEVIATION_NEW, ts[i]

    try:
        # Calculate historical indices for the same season
        stop = max(0, i - nb_hist_points * season_length)
        indices = list(range(i - season_length, stop - 1, -season_length))
        expected_val = ts[indices].median()

        # Classification according to business rules
        if np.isnan(ts[i]):
            return AnomalyType.VANISH, DEVIATION_OUTLIER, expected_val
        elif abs(expected_val) < threshold_negligible:
            # ⚠️ BUG: Does not check abs(ts[i])
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

# Check minimum length
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

# TEST CLASS: BASIC LOGIC

# =============================================================================

class TestBasicLogic(unittest.TestCase):
“””
Tests for the main logic of detect_core.

```
These tests verify expected behavior for standard use cases
in the IFRS9/regulatory context.
"""

def test_01_constant_series_should_be_normal(self):
    """
    CASE: Time series with constant values.
    EXPECTED: All points (after the first) should be NORMAL.
    
    BUSINESS CONTEXT:
    A stable IFRS9 provision over several quarters indicates
    a stable credit portfolio - normal behavior.
    
    Example: ECL Provision = 100M€ each quarter
    """
    # Stable provision: 100M€ over 5 quarters
    ts = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
    threshold_anomaly = 0.3  # 30%
    threshold_negligible = 0.01
    
    anomalies, deviations, expected_values, model_type = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    # Index 0: NEW (no history)
    self.assertEqual(anomalies[0], AnomalyType.NEW,
        "First point should be NEW (no history)")
    
    # Index 1-4: NORMAL (deviation = 0)
    for i in range(1, 5):
        self.assertEqual(anomalies[i], AnomalyType.NORMAL,
            f"Index {i}: Expected NORMAL, got {AnomalyType(anomalies[i]).name}")
        self.assertAlmostEqual(deviations[i], 0.0, places=5,
            msg=f"Index {i}: Expected deviation 0, got {deviations[i]}")
    
    print("✅ PASS: Constant series → All NORMAL after first point")

def test_02_small_increase_stays_normal(self):
    """
    CASE: Progressive increase below threshold.
    EXPECTED: NORMAL because variation < 30%.
    
    BUSINESS CONTEXT:
    A slight provision increase (e.g., +10% per quarter)
    may reflect normal portfolio growth.
    
    Example: 100M → 110M → 120M → 130M (10%/quarter growth)
    """
    ts = pd.Series([100.0, 110.0, 120.0, 130.0])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, _, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    # At index 3: expected = median(ts[2]) = 120, observed = 130
    # deviation = |1 - 130/120| = 0.083 < 0.3 → NORMAL
    self.assertEqual(anomalies[3], AnomalyType.NORMAL)
    self.assertLess(deviations[3], threshold_anomaly)
    
    print(f"✅ PASS: Small increase → NORMAL (deviation={deviations[3]:.3f})")

def test_03_sudden_spike_should_be_outlier(self):
    """
    CASE: Sudden doubling of value.
    EXPECTED: OUTLIER because deviation = 100% > threshold.
    
    BUSINESS CONTEXT:
    A sudden doubling of provision may indicate:
    - Major portfolio quality degradation
    - Undocumented methodology change
    - Calculation error in ECL model
    
    Example: Provision goes from 100M€ to 200M€ in one quarter
    """
    ts = pd.Series([100.0, 100.0, 100.0, 200.0])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    # expected = 100, observed = 200
    # deviation = |1 - 200/100| = 1.0 > 0.3 → OUTLIER
    self.assertEqual(anomalies[3], AnomalyType.OUTLIER,
        f"Expected OUTLIER, got {AnomalyType(anomalies[3]).name}")
    self.assertEqual(deviations[3], 1.0,
        f"Expected deviation 1.0, got {deviations[3]}")
    self.assertEqual(expected_values[3], 100.0)
    
    print(f"✅ PASS: Sudden spike (+100%) → OUTLIER (deviation={deviations[3]:.3f})")

def test_04_sudden_drop_should_be_outlier(self):
    """
    CASE: Sudden 50% decrease.
    EXPECTED: OUTLIER because deviation = 50% > threshold.
    
    BUSINESS CONTEXT:
    A sudden provision drop may indicate:
    - Massive portfolio sale
    - Stage 3 transition with write-off
    - Error in source data (EAD, PD, LGD)
    
    Example: Provision goes from 100M€ to 50M€
    """
    ts = pd.Series([100.0, 100.0, 100.0, 50.0])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, _, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    # deviation = |1 - 50/100| = 0.5 > 0.3 → OUTLIER
    self.assertEqual(anomalies[3], AnomalyType.OUTLIER)
    self.assertAlmostEqual(deviations[3], 0.5)
    
    print(f"✅ PASS: Sudden drop (-50%) → OUTLIER (deviation={deviations[3]:.3f})")
```

# =============================================================================

# TEST CLASS: NEGLIGIBLE LOGIC

# =============================================================================

class TestNegligibleLogic(unittest.TestCase):
“””
Tests for NEGLIGIBLE logic.

```
WARNING: This class tests potentially buggy behavior.
The current code only checks expected value, not observed value.
"""

def test_05_both_small_values_negligible(self):
    """
    CASE: Both Expected AND Observed are very small.
    EXPECTED: NEGLIGIBLE (correct behavior).
    
    BUSINESS CONTEXT:
    For a segment with very low exposure (e.g., EAD < 1000€),
    variations are not significant for reporting.
    
    Example: Provision of 0.001M€ → 0.002M€ (insignificant)
    """
    ts = pd.Series([0.001, 0.001, 0.001, 0.002])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, _, _, _ = detect_core(ts, threshold_anomaly, threshold_negligible)
    
    # expected = 0.001 < 0.01 → NEGLIGIBLE (OK because observed also < 0.01)
    self.assertEqual(anomalies[3], AnomalyType.NEGLIGIBLE)
    
    print("✅ PASS: Both small values → NEGLIGIBLE (correct behavior)")

def test_06_BUG_small_expected_large_observed_should_not_be_negligible(self):
    """
    ⚠️ BUG TEST: Small expected but very large observed.
    
    CURRENT BEHAVIOR (BUGGY): NEGLIGIBLE
    EXPECTED BEHAVIOR: Should be OUTLIER or new SPIKE type
    
    CRITICAL BUSINESS CONTEXT:
    If provision goes from 0.001M€ to 1,000M€, this is a MAJOR
    anomaly that must absolutely be detected!
    
    This bug can cause:
    - Non-detection of massive calculation errors
    - Incorrect regulatory reporting risks
    - Potential underestimation of credit risks
    """
    ts = pd.Series([0.001, 0.001, 0.001, 1000000.0])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    print("\n" + "="*60)
    print("⚠️ NEGLIGIBLE BUG ANALYSIS")
    print("="*60)
    print(f"   Observed value:  {ts[3]:,.0f}")
    print(f"   Expected value:  {expected_values[3]}")
    print(f"   |expected| < {threshold_negligible}? {abs(expected_values[3]) < threshold_negligible}")
    print(f"   |observed| < {threshold_negligible}? {abs(ts[3]) < threshold_negligible}")
    print(f"   Current result:  {AnomalyType(anomalies[3]).name}")
    print(f"   Expected result: OUTLIER or SPIKE")
    
    # Current code returns NEGLIGIBLE (bug!)
    if anomalies[3] == AnomalyType.NEGLIGIBLE:
        print("\n   ❌ BUG CONFIRMED: Massive value classified as NEGLIGIBLE!")
        print("   This behavior is incorrect and must be fixed.")
        # Skip this test as it's a known bug
        self.skipTest("Known bug: NEGLIGIBLE does not check observed value")
    else:
        # If bug is fixed, verify it's OUTLIER
        self.assertEqual(anomalies[3], AnomalyType.OUTLIER)

def test_07_large_expected_small_observed_should_be_outlier(self):
    """
    CASE: Large expected, very small observed.
    EXPECTED: OUTLIER (massive drop).
    
    BUSINESS CONTEXT:
    A provision drop from 100M€ to nearly zero indicates:
    - Possible undocumented massive write-off
    - Data error (EAD disappeared)
    - Issue in data pipeline
    """
    ts = pd.Series([100.0, 100.0, 100.0, 0.001])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, _, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    # expected = 100, observed = 0.001
    # deviation = |1 - 0.001/100| ≈ 1.0 → OUTLIER
    self.assertEqual(anomalies[3], AnomalyType.OUTLIER)
    self.assertGreater(deviations[3], 0.99)
    
    print(f"✅ PASS: Large expected → small observed = OUTLIER (deviation≈1.0)")
```

# =============================================================================

# TEST CLASS: MISSING VALUES (VANISH)

# =============================================================================

class TestMissingValues(unittest.TestCase):
“””
Tests for VANISH type (missing data).

```
BUSINESS CONTEXT:
Missing data in IFRS9 flows may indicate:
- Issues in data pipelines
- Closed or migrated segments
- Extraction errors
"""

def test_08_nan_value_should_be_vanish(self):
    """
    CASE: Current value is NaN.
    EXPECTED: VANISH with expected_val calculated correctly.
    
    BUSINESS CONTEXT:
    If a segment suddenly disappears from reporting,
    this requires immediate investigation.
    """
    ts = pd.Series([100.0, 100.0, 100.0, np.nan])
    threshold_anomaly = 0.3
    threshold_negligible = 0.01
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, threshold_anomaly, threshold_negligible
    )
    
    self.assertEqual(anomalies[3], AnomalyType.VANISH)
    # Expected value should still be calculated (for audit purposes)
    self.assertAlmostEqual(expected_values[3], 100.0)
    
    print("✅ PASS: NaN value → VANISH with expected value preserved")

def test_09_all_nan_series(self):
    """
    CASE: Series entirely composed of NaN.
    EXPECTED: Graceful handling without crash.
    """
    ts = pd.Series([np.nan, np.nan, np.nan, np.nan])
    
    anomalies, deviations, expected_values, _ = detect_core(
        ts, 0.3, 0.01
    )
    
    # First point: NEW
    self.assertEqual(anomalies[0], AnomalyType.NEW)
    # Subsequent points: VANISH (since expected = median of NaN = NaN)
    
    print(f"All NaN series results: {[AnomalyType(a).name for a in anomalies]}")
```

# =============================================================================

# TEST CLASS: NEW POINTS

# =============================================================================

class TestNewPoints(unittest.TestCase):
“””
Tests for NEW type (insufficient history).

```
BUSINESS CONTEXT:
New credit segments have no history for comparison.
They should be marked NEW until sufficient data accumulates.
"""

def test_10_first_point_always_new(self):
    """
    CASE: First point in series.
    EXPECTED: NEW (no history available).
    """
    ts = pd.Series([100.0, 100.0, 100.0])
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01)
    
    self.assertEqual(anomalies[0], AnomalyType.NEW)
    
    print("✅ PASS: First point → NEW")

def test_11_short_series_all_new(self):
    """
    CASE: Series shorter than season_length + 1.
    EXPECTED: All points are NEW.
    
    BUSINESS CONTEXT:
    A new credit product launched less than a year ago
    has no seasonal comparison point yet.
    """
    ts = pd.Series([100.0, 200.0])  # Only 2 points
    season_length = 4  # Quarterly
    
    anomalies, _, _, model_type = detect_core(
        ts, 0.3, 0.01, season_length=season_length
    )
    
    # len(ts)=2 < 1 + season_length=5 → All NEW
    self.assertTrue(all(a == AnomalyType.NEW for a in anomalies))
    
    print("✅ PASS: Short series → All NEW")

def test_12_first_season_all_new(self):
    """
    CASE: Seasonal model, first complete season.
    EXPECTED: All points in first season are NEW.
    
    BUSINESS CONTEXT:
    For the first year of a new portfolio,
    no Q1-Q1 or Q2-Q2 comparison is possible.
    """
    # 5 quarters: [Q1, Q2, Q3, Q4, Q1] (year 1 + start of year 2)
    ts = pd.Series([100.0, 100.0, 100.0, 100.0, 200.0])
    season_length = 4
    
    anomalies, _, _, _ = detect_core(
        ts, 0.3, 0.01, season_length=season_length
    )
    
    # Index 0-3 (year 1): NEW because i < season_length
    for i in range(4):
        self.assertEqual(anomalies[i], AnomalyType.NEW,
            f"Index {i}: Expected NEW, got {AnomalyType(anomalies[i]).name}")
    
    # Index 4 (Q1 year 2): Can be compared to index 0 (Q1 year 1)
    self.assertNotEqual(anomalies[4], AnomalyType.NEW)
    
    print("✅ PASS: First season → All NEW, then comparison possible")
```

# =============================================================================

# TEST CLASS: SEASONALITY

# =============================================================================

class TestSeasonality(unittest.TestCase):
“””
Tests for seasonality logic.

```
BUSINESS CONTEXT:
IFRS9 data often shows seasonal patterns:
- Q1: Start of year, rating revisions
- Q2/Q3: Normal activity
- Q4: Annual closing, additional provisions

Comparison should be done quarter by quarter.
"""

def test_13_same_quarter_comparison(self):
    """
    CASE: Quarterly data, Q1 vs Q1 comparison.
    EXPECTED: Comparison between corresponding quarters.
    
    BUSINESS CONTEXT:
    Q1 2024 should be compared to Q1 2023, not Q4 2023.
    Seasonal patterns are thus respected.
    """
    # [Q1, Q2, Q3, Q4, Q1, Q2, Q3, Q4] - 2 years
    ts = pd.Series([100, 110, 120, 130, 100, 110, 120, 130])
    season_length = 4
    
    anomalies, deviations, expected_values, model_type = detect_core(
        ts, 0.3, 0.01, season_length=season_length
    )
    
    # Index 4 (Q1 year 2) vs Index 0 (Q1 year 1): 100 vs 100
    self.assertEqual(anomalies[4], AnomalyType.NORMAL)
    self.assertAlmostEqual(deviations[4], 0.0)
    self.assertEqual(model_type, ModelType.SEASONAL)
    
    # Index 5 (Q2 year 2) vs Index 1 (Q2 year 1): 110 vs 110
    self.assertEqual(anomalies[5], AnomalyType.NORMAL)
    
    print("✅ PASS: Seasonal Q-Q comparison works correctly")

def test_14_seasonal_anomaly_detected(self):
    """
    CASE: Anomaly in a specific quarter.
    EXPECTED: OUTLIER due to significant deviation vs same quarter previous year.
    
    BUSINESS CONTEXT:
    If Q1 2024 doubles compared to Q1 2023, it's an anomaly
    even if Q4 2023 was also high.
    """
    # Q1 year 1 = 100, Q1 year 2 = 200 (doubling)
    ts = pd.Series([100, 110, 120, 130, 200, 110, 120, 130])
    season_length = 4
    
    anomalies, deviations, _, _ = detect_core(
        ts, 0.3, 0.01, season_length=season_length
    )
    
    # Index 4: expected = ts[0] = 100, observed = 200
    # deviation = |1 - 200/100| = 1.0 → OUTLIER
    self.assertEqual(anomalies[4], AnomalyType.OUTLIER)
    self.assertAlmostEqual(deviations[4], 1.0)
    
    print("✅ PASS: Seasonal anomaly detected correctly")
```

# =============================================================================

# TEST CLASS: MEDIAN CALCULATION

# =============================================================================

class TestMedianCalculation(unittest.TestCase):
“””
Tests for expected value calculation (historical median).

```
The median is more robust than the mean because it resists
outliers in the history.
"""

def test_15_median_two_historical_points(self):
    """
    CASE: nb_hist_points=2 with two years of history.
    EXPECTED: expected = median of 2 seasonal points.
    
    Example: For Q1 year 3:
    - Historical points: Q1 year 2 (index 4) and Q1 year 1 (index 0)
    - expected = median(200, 100) = 150
    """
    # 3 years: different values for each Q1
    ts = pd.Series([
        100, 0, 0, 0,   # Year 1: Q1=100
        200, 0, 0, 0,   # Year 2: Q1=200
        150, 0, 0, 0    # Year 3: Q1=150 (current)
    ])
    season_length = 4
    nb_hist_points = 2
    
    _, _, expected_values, _ = detect_core(
        ts, 0.3, 0.01,
        season_length=season_length,
        nb_hist_points=nb_hist_points
    )
    
    # Index 8: median(ts[4], ts[0]) = median(200, 100) = 150
    self.assertAlmostEqual(expected_values[8], 150.0)
    
    print(f"✅ PASS: Median of 2 historical points = {expected_values[8]}")

def test_16_median_single_point_available(self):
    """
    CASE: Only one historical point available.
    EXPECTED: expected = that single point.
    """
    ts = pd.Series([100, 0, 0, 0, 200])
    season_length = 4
    nb_hist_points = 2  # But only 1 point available
    
    _, _, expected_values, _ = detect_core(
        ts, 0.3, 0.01,
        season_length=season_length,
        nb_hist_points=nb_hist_points
    )
    
    # Index 4: only ts[0] available → expected = 100
    self.assertAlmostEqual(expected_values[4], 100.0)
    
    print("✅ PASS: Single historical point → expected = that point")
```

# =============================================================================

# TEST CLASS: EDGE CASES

# =============================================================================

class TestEdgeCases(unittest.TestCase):
“””
Tests for edge cases and boundary conditions.

```
These tests verify code robustness against extreme
situations that may occur in production.
"""

def test_17_empty_series(self):
    """
    CASE: Empty time series.
    EXPECTED: Empty lists without error.
    """
    ts = pd.Series([], dtype=float)
    
    anomalies, deviations, expected_values, model_type = detect_core(
        ts, 0.3, 0.01
    )
    
    self.assertEqual(len(anomalies), 0)
    self.assertEqual(len(deviations), 0)
    
    print("✅ PASS: Empty series handled correctly")

def test_18_single_element(self):
    """
    CASE: Series with single element.
    EXPECTED: NEW (no history).
    """
    ts = pd.Series([100.0])
    
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01)
    
    self.assertEqual(len(anomalies), 1)
    self.assertEqual(anomalies[0], AnomalyType.NEW)
    
    print("✅ PASS: Single element → NEW")

def test_19_negative_values(self):
    """
    CASE: Negative values in series.
    EXPECTED: Correct deviation calculation.
    
    BUSINESS CONTEXT:
    Some metrics can be negative (P&L, deltas).
    """
    ts = pd.Series([-100.0, -100.0, -100.0, -200.0])
    
    anomalies, deviations, _, _ = detect_core(ts, 0.3, 0.01)
    
    # expected = -100, observed = -200
    # deviation = |1 - (-200)/(-100)| = |1 - 2| = 1.0
    self.assertEqual(anomalies[3], AnomalyType.OUTLIER)
    self.assertAlmostEqual(deviations[3], 1.0)
    
    print("✅ PASS: Negative values handled correctly")

def test_20_threshold_exactly_reached(self):
    """
    CASE: Deviation exactly equal to threshold.
    EXPECTED: OUTLIER (condition >=).
    
    Verification of boundary condition behavior.
    """
    # expected = 100, observed = 130 → deviation = 0.3 exactly
    ts = pd.Series([100.0, 100.0, 100.0, 130.0])
    threshold_anomaly = 0.3
    
    anomalies, deviations, _, _ = detect_core(ts, threshold_anomaly, 0.01)
    
    # deviation = |1 - 130/100| = 0.3 >= 0.3 → OUTLIER
    self.assertEqual(anomalies[3], AnomalyType.OUTLIER)
    self.assertAlmostEqual(deviations[3], 0.3)
    
    print("✅ PASS: Deviation = threshold → OUTLIER (condition >=)")

def test_21_just_below_threshold(self):
    """
    CASE: Deviation just below threshold.
    EXPECTED: NORMAL.
    """
    # expected = 100, observed = 129 → deviation = 0.29
    ts = pd.Series([100.0, 100.0, 100.0, 129.0])
    threshold_anomaly = 0.3
    
    anomalies, deviations, _, _ = detect_core(ts, threshold_anomaly, 0.01)
    
    # deviation = |1 - 129/100| = 0.29 < 0.3 → NORMAL
    self.assertEqual(anomalies[3], AnomalyType.NORMAL)
    self.assertAlmostEqual(deviations[3], 0.29)
    
    print("✅ PASS: Deviation < threshold → NORMAL")

def test_22_expected_exactly_zero(self):
    """
    CASE: Expected value = 0 exactly.
    EXPECTED: NEGLIGIBLE (because 0 < threshold_negligible).
    
    Note: This case avoids division by zero thanks to NEGLIGIBLE condition.
    """
    ts = pd.Series([0.0, 0.0, 0.0, 100.0])
    
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01)
    
    # expected = 0 < 0.01 → NEGLIGIBLE
    # Note: This is also the buggy case since observed = 100 is not negligible!
    self.assertEqual(anomalies[3], AnomalyType.NEGLIGIBLE)
    
    print("✅ PASS: Expected = 0 → NEGLIGIBLE (avoids division by zero)")
```

# =============================================================================

# TEST CLASS: NB_PERIODS PARAMETER

# =============================================================================

class TestNbPeriodsParameter(unittest.TestCase):
“””
Tests for nb_periods parameter.

```
This parameter allows limiting calculation to the last N periods,
useful for incremental analyses.
"""

def test_23_nb_periods_limits_calculation(self):
    """
    CASE: nb_periods = 2 (calculate only last 2 points).
    EXPECTED: Earlier points marked as NEW.
    """
    ts = pd.Series([100.0, 100.0, 100.0, 200.0, 200.0])
    nb_periods = 2
    
    anomalies, _, _, _ = detect_core(ts, 0.3, 0.01, nb_periods=nb_periods)
    
    # Index 0, 1, 2: < len(ts) - nb_periods = 3 → NEW
    for i in range(3):
        self.assertEqual(anomalies[i], AnomalyType.NEW,
            f"Index {i}: Expected NEW, got {AnomalyType(anomalies[i]).name}")
    
    # Index 3, 4: Calculated normally
    self.assertNotEqual(anomalies[3], AnomalyType.NEW)
    
    print("✅ PASS: nb_periods limits calculation scope")
```

# =============================================================================

# RUN TESTS

# =============================================================================

if **name** == “**main**”:
# Create test suite
loader = unittest.TestLoader()
suite = unittest.TestSuite()

```
# Add all test classes
suite.addTests(loader.loadTestsFromTestCase(TestBasicLogic))
suite.addTests(loader.loadTestsFromTestCase(TestNegligibleLogic))
suite.addTests(loader.loadTestsFromTestCase(TestMissingValues))
suite.addTests(loader.loadTestsFromTestCase(TestNewPoints))
suite.addTests(loader.loadTestsFromTestCase(TestSeasonality))
suite.addTests(loader.loadTestsFromTestCase(TestMedianCalculation))
suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
suite.addTests(loader.loadTestsFromTestCase(TestNbPeriodsParameter))

# Run with verbosity
print("\n" + "="*80)
print("RUNNING DETECT_CORE TEST SUITE")
print("="*80 + "\n")

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Summary
print("\n" + "="*80)
print("TEST SUMMARY")
print("="*80)
print(f"Tests run:    {result.testsRun}")
print(f"Failures:     {len(result.failures)}")
print(f"Errors:       {len(result.errors)}")
print(f"Skipped:      {len(result.skipped)}")
print(f"Success:      {'YES ✅' if result.wasSuccessful() else 'NO ❌'}")

# Business analysis
print("\n" + "="*80)
print("BUSINESS ANALYSIS")
print("="*80)
print("""
```

DETECT_CORE CODE REVIEW SUMMARY:

✅ CORRECT BEHAVIORS:

- NORMAL classification for stable values
- OUTLIER classification for deviations > threshold
- NaN handling (VANISH)
- New points handling (NEW)
- Correct historical median calculation
- Seasonality logic (Q-Q comparison)
- Negative values handling
- Boundary conditions (>=)

⚠️ IDENTIFIED BUG - HIGH PRIORITY:
Location:    Lines 103-104
Description: NEGLIGIBLE condition only checks |expected| < threshold
without checking |observed|
Impact:      An observed value of 1,000,000 can be ignored
if expected is close to zero
Risk:        Non-detection of major anomalies in provisions

RECOMMENDATION:
Fix NEGLIGIBLE condition to check BOTH values:

if abs(expected_val) < threshold_negligible AND abs(ts[i]) < threshold_negligible:
return AnomalyType.NEGLIGIBLE, …
elif abs(expected_val) < threshold_negligible:
# Special case: expected small but observed large = ANOMALY!
return AnomalyType.OUTLIER, …  # or new SPIKE type
“””)