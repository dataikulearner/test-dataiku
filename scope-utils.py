# “””
scope_utils.py - Scope Computation Library for DETECT

Reusable functions for computing scope boolean columns.
Can be used in both DSS recipes and standalone Python.

Usage:
from lib.scope_utils import compute_all_scopes, get_scope_stats

```
df = compute_all_scopes(df, scope_definitions)
stats = get_scope_stats(df, ["us", "fortis", "bcef", "japan"])
```

“””

import pandas as pd
from typing import Dict, Any, List

def compute_scope(df: pd.DataFrame, scope_id: str, filters: Dict[str, Any]) -> pd.Series:
“””
Compute a single scope boolean column.

```
Args:
    df: Input DataFrame
    scope_id: Scope identifier (for logging)
    filters: Dict of {column_name: filter_config}

Filter config format:
    {
        "operator": "IN" | "EQUALS" | "NOT_IN" | "NOT_EQUALS",
        "values": [...],           # For IN/NOT_IN
        "value": "...",            # For EQUALS/NOT_EQUALS
        "allow_null": true/false   # For NOT_IN/NOT_EQUALS
    }

Returns:
    Boolean Series (True where all filter conditions match)

Example:
    >>> filters = {
    ...     "pmas_code": {"operator": "EQUALS", "value": "PMA_03"},
    ...     "lb_site": {"operator": "NOT_IN", "values": ["X"], "allow_null": True}
    ... }
    >>> mask = compute_scope(df, "bcef", filters)
"""
if not filters:
    return pd.Series([True] * len(df), index=df.index)

# Start with all True, then AND each condition
mask = pd.Series([True] * len(df), index=df.index)

for col_name, config in filters.items():
    # Skip metadata keys (e.g., "_comment")
    if col_name.startswith("_"):
        continue
    
    # Skip if column doesn't exist
    if col_name not in df.columns:
        continue
    
    operator = config.get("operator", "IN").upper()
    values = config.get("values", [])
    value = config.get("value")
    allow_null = config.get("allow_null", False)
    
    # Use single value if values list empty
    if not values and value is not None:
        values = [value]
    
    # Build condition based on operator
    if operator == "IN":
        condition = df[col_name].isin(values)
    
    elif operator == "EQUALS":
        condition = df[col_name] == (value if value else values[0])
    
    elif operator == "NOT_IN":
        # NOT_IN: value is not in the exclusion list
        # When allow_null=False: NULL values are excluded (return False)
        # When allow_null=True: NULL values are included (return True)
        condition = ~df[col_name].isin(values)
        if allow_null:
            condition = condition | df[col_name].isna()
        else:
            # Exclude NULL values when allow_null=False
            condition = condition & df[col_name].notna()
    
    elif operator == "NOT_EQUALS":
        condition = df[col_name] != (value if value else values[0])
        if allow_null:
            condition = condition | df[col_name].isna()
    
    else:
        raise ValueError(f"Unknown operator: {operator}")
    
    mask = mask & condition

return mask
```

def compute_all_scopes(df: pd.DataFrame, scope_definitions: Dict[str, Any]) -> pd.DataFrame:
“””
Compute all scope boolean columns.

```
Args:
    df: Input DataFrame
    scope_definitions: Dict from ccirc_params["scopes"]

Returns:
    DataFrame with scope_* columns added (copy, original unchanged)

Example:
    >>> scope_defs = {
    ...     "us": {"filters": {"site": {"operator": "IN", "values": ["A", "B"]}}},
    ...     "japan": {"filters": {"site": {"operator": "IN", "values": ["C"]}}}
    ... }
    >>> df_out = compute_all_scopes(df, scope_defs)
    >>> # df_out has columns: scope_us, scope_japan
"""
df = df.copy()

for scope_id, config in scope_definitions.items():
    # Skip metadata keys
    if scope_id.startswith("_"):
        continue
    
    filters = config.get("filters", {})
    df[f"scope_{scope_id}"] = compute_scope(df, scope_id, filters)

return df
```

def get_scope_stats(df: pd.DataFrame, scope_ids: List[str]) -> Dict[str, Any]:
“””
Get statistics about scope membership.

```
Args:
    df: DataFrame with scope_* columns
    scope_ids: List of scope IDs (without "scope_" prefix)

Returns:
    Dict with counts: total, per-scope, multi_scope

Example:
    >>> stats = get_scope_stats(df, ["us", "fortis", "bcef", "japan"])
    >>> print(stats)
    {"total": 10000, "us": 500, "fortis": 800, "bcef": 300, "japan": 100, "multi_scope": 50}
"""
stats = {"total": len(df)}

for scope_id in scope_ids:
    col = f"scope_{scope_id}"
    if col in df.columns:
        stats[scope_id] = int(df[col].sum())

# Count multi-scope rows (rows belonging to 2+ scopes)
scope_cols = [f"scope_{s}" for s in scope_ids if f"scope_{s}" in df.columns]
if scope_cols:
    stats["multi_scope"] = int((df[scope_cols].sum(axis=1) > 1).sum())

return stats
```

def validate_scope_columns(df: pd.DataFrame, required_columns: List[str]) -> Dict[str, bool]:
“””
Validate that DataFrame has required columns for scope computation.

```
Args:
    df: Input DataFrame
    required_columns: List of column names needed for scopes

Returns:
    Dict mapping column name to present (True/False)

Example:
    >>> result = validate_scope_columns(df, ["accounting_site_code", "pmas_code"])
    >>> if all(result.values()):
    ...     print("All columns present")
"""
return {col: col in df.columns for col in required_columns}
```