# “””
test_scope_utils.py - Unit Tests for Scope Utils

Run: python test_scope_utils.py
“””

import unittest
import pandas as pd
import sys
import os

# Add lib to path

sys.path.insert(0, os.path.join(os.path.dirname(**file**), ‘..’, ‘lib’))

from scope_utils import compute_scope, compute_all_scopes, get_scope_stats

class TestComputeScope(unittest.TestCase):
“”“Tests for compute_scope function”””

```
def setUp(self):
    """Create test DataFrame"""
    self.df = pd.DataFrame({
        "segment_id": ["S1", "S2", "S3", "S4", "S5", "S6", "S7"],
        "accounting_site_code_post_acc": ["12309", "40043", "10054", "99999", "30448", "12309", "40043"],
        "pmas_code_post_acc": ["PMA_01", "PMA_03", "PMA_02", "PMA_03", "PMA_05", "PMA_01", "PMA_03"],
        "lb_site_risque_apres_accr": ["Other", "Other", "Other", "BNPP Factor France", None, "Other", None],
    })

def test_in_operator(self):
    """Test IN operator"""
    filters = {
        "accounting_site_code_post_acc": {
            "operator": "IN",
            "values": ["12309", "40043"]
        }
    }
    result = compute_scope(self.df, "us", filters)
    
    # S1=12309, S2=40043, S6=12309, S7=40043 → True
    expected = [True, True, False, False, False, True, True]
    self.assertEqual(result.tolist(), expected)

def test_equals_operator(self):
    """Test EQUALS operator"""
    filters = {
        "pmas_code_post_acc": {
            "operator": "EQUALS",
            "value": "PMA_03"
        }
    }
    result = compute_scope(self.df, "test", filters)
    
    # S2, S4, S7 have PMA_03
    expected = [False, True, False, True, False, False, True]
    self.assertEqual(result.tolist(), expected)

def test_not_in_operator_without_allow_null(self):
    """Test NOT_IN operator without allow_null"""
    filters = {
        "lb_site_risque_apres_accr": {
            "operator": "NOT_IN",
            "values": ["BNPP Factor France"],
            "allow_null": False
        }
    }
    result = compute_scope(self.df, "test", filters)
    
    # S1, S2, S3, S6 = Other (not in list) → True
    # S4 = BNPP Factor France → False
    # S5, S7 = None → False (allow_null=False)
    expected = [True, True, True, False, False, True, False]
    self.assertEqual(result.tolist(), expected)

def test_not_in_operator_with_allow_null(self):
    """Test NOT_IN operator with allow_null=True"""
    filters = {
        "lb_site_risque_apres_accr": {
            "operator": "NOT_IN",
            "values": ["BNPP Factor France"],
            "allow_null": True
        }
    }
    result = compute_scope(self.df, "test", filters)
    
    # S1, S2, S3, S6 = Other (not in list) → True
    # S4 = BNPP Factor France → False
    # S5, S7 = None → True (allow_null=True)
    expected = [True, True, True, False, True, True, True]
    self.assertEqual(result.tolist(), expected)

def test_combined_filters_and_logic(self):
    """Test multiple filters combined with AND"""
    filters = {
        "accounting_site_code_post_acc": {
            "operator": "IN",
            "values": ["30448", "48019"]
        },
        "pmas_code_post_acc": {
            "operator": "EQUALS",
            "value": "PMA_05"
        }
    }
    result = compute_scope(self.df, "japan", filters)
    
    # Only S5: site=30448 AND pmas=PMA_05
    expected = [False, False, False, False, True, False, False]
    self.assertEqual(result.tolist(), expected)

def test_bcef_scope(self):
    """Test BCeF scope: PMA_03 AND NOT 'BNPP Factor France' OR NULL"""
    filters = {
        "pmas_code_post_acc": {
            "operator": "EQUALS",
            "value": "PMA_03"
        },
        "lb_site_risque_apres_accr": {
            "operator": "NOT_IN",
            "values": ["BNPP Factor France"],
            "allow_null": True
        }
    }
    result = compute_scope(self.df, "bcef", filters)
    
    # S2: PMA_03 + Other → True
    # S4: PMA_03 + BNPP Factor France → False
    # S7: PMA_03 + NULL → True
    expected = [False, True, False, False, False, False, True]
    self.assertEqual(result.tolist(), expected)

def test_empty_filters(self):
    """Test empty filters returns all True"""
    result = compute_scope(self.df, "all", {})
    expected = [True] * len(self.df)
    self.assertEqual(result.tolist(), expected)

def test_missing_column_skipped(self):
    """Test that missing columns are skipped gracefully"""
    filters = {
        "non_existent_column": {
            "operator": "EQUALS",
            "value": "X"
        }
    }
    # Should not raise, should return all True (no valid filters)
    result = compute_scope(self.df, "test", filters)
    expected = [True] * len(self.df)
    self.assertEqual(result.tolist(), expected)
```

class TestComputeAllScopes(unittest.TestCase):
“”“Tests for compute_all_scopes function”””

```
def setUp(self):
    """Create test DataFrame"""
    self.df = pd.DataFrame({
        "segment_id": ["S1", "S2", "S3"],
        "accounting_site_code_post_acc": ["12309", "10054", "30448"],
        "pmas_code_post_acc": ["PMA_01", "PMA_02", "PMA_05"],
    })
    
    self.scope_definitions = {
        "us": {
            "filters": {
                "accounting_site_code_post_acc": {
                    "operator": "IN",
                    "values": ["12309", "40043"]
                }
            }
        },
        "fortis": {
            "filters": {
                "accounting_site_code_post_acc": {
                    "operator": "IN",
                    "values": ["10054", "10056"]
                }
            }
        },
        "japan": {
            "filters": {
                "accounting_site_code_post_acc": {
                    "operator": "IN",
                    "values": ["30448"]
                },
                "pmas_code_post_acc": {
                    "operator": "EQUALS",
                    "value": "PMA_05"
                }
            }
        }
    }

def test_all_scope_columns_created(self):
    """Test that all scope columns are created"""
    result = compute_all_scopes(self.df, self.scope_definitions)
    
    self.assertIn("scope_us", result.columns)
    self.assertIn("scope_fortis", result.columns)
    self.assertIn("scope_japan", result.columns)

def test_original_dataframe_unchanged(self):
    """Test that original DataFrame is not modified"""
    original_cols = list(self.df.columns)
    compute_all_scopes(self.df, self.scope_definitions)
    
    self.assertEqual(list(self.df.columns), original_cols)

def test_scope_values_correct(self):
    """Test that scope values are computed correctly"""
    result = compute_all_scopes(self.df, self.scope_definitions)
    
    # S1: site=12309 → us=True, fortis=False, japan=False
    self.assertTrue(result.loc[0, "scope_us"])
    self.assertFalse(result.loc[0, "scope_fortis"])
    self.assertFalse(result.loc[0, "scope_japan"])
    
    # S2: site=10054 → us=False, fortis=True, japan=False
    self.assertFalse(result.loc[1, "scope_us"])
    self.assertTrue(result.loc[1, "scope_fortis"])
    self.assertFalse(result.loc[1, "scope_japan"])
    
    # S3: site=30448, pmas=PMA_05 → us=False, fortis=False, japan=True
    self.assertFalse(result.loc[2, "scope_us"])
    self.assertFalse(result.loc[2, "scope_fortis"])
    self.assertTrue(result.loc[2, "scope_japan"])

def test_metadata_keys_skipped(self):
    """Test that keys starting with _ are skipped"""
    scope_defs = {
        "_comment": "This should be skipped",
        "us": {"filters": {}}
    }
    result = compute_all_scopes(self.df, scope_defs)
    
    self.assertIn("scope_us", result.columns)
    self.assertNotIn("scope__comment", result.columns)
```

class TestGetScopeStats(unittest.TestCase):
“”“Tests for get_scope_stats function”””

```
def test_basic_stats(self):
    """Test basic statistics calculation"""
    df = pd.DataFrame({
        "scope_us": [True, True, False, False, False],
        "scope_fortis": [False, False, True, True, False],
        "scope_japan": [False, False, False, False, True],
    })
    
    stats = get_scope_stats(df, ["us", "fortis", "japan"])
    
    self.assertEqual(stats["total"], 5)
    self.assertEqual(stats["us"], 2)
    self.assertEqual(stats["fortis"], 2)
    self.assertEqual(stats["japan"], 1)
    self.assertEqual(stats["multi_scope"], 0)

def test_multi_scope_count(self):
    """Test multi-scope counting"""
    df = pd.DataFrame({
        "scope_us": [True, True, False],
        "scope_bcef": [True, False, True],  # Row 0 belongs to both us and bcef
    })
    
    stats = get_scope_stats(df, ["us", "bcef"])
    
    self.assertEqual(stats["multi_scope"], 1)  # Only row 0
```

class TestEdgeCases(unittest.TestCase):
“”“Tests for edge cases”””

```
def test_empty_dataframe(self):
    """Test with empty DataFrame"""
    df = pd.DataFrame(columns=["site", "pmas"])
    scope_defs = {
        "us": {"filters": {"site": {"operator": "IN", "values": ["A"]}}}
    }
    
    result = compute_all_scopes(df, scope_defs)
    
    self.assertIn("scope_us", result.columns)
    self.assertEqual(len(result), 0)

def test_all_null_column(self):
    """Test with column containing all NULL values"""
    df = pd.DataFrame({
        "site": [None, None, None]
    })
    
    filters = {
        "site": {
            "operator": "NOT_IN",
            "values": ["X"],
            "allow_null": True
        }
    }
    
    result = compute_scope(df, "test", filters)
    
    # All NULL with allow_null=True → all True
    self.assertEqual(result.tolist(), [True, True, True])
```

if **name** == “**main**”:
print(”=” * 70)
print(“Running Scope Utils Unit Tests”)
print(”=” * 70)

```
unittest.main(verbosity=2)
```