# “””
DETECT CCIRC - Scope Layer Recipe

DSS Recipe: compute_scope_columns

Input:  SP_display_seg (with source columns from pre-processing)
Output: SP_display_seg_scoped (with scope_* boolean columns)

This recipe computes scope boolean columns based on scope definitions
in ccirc_params.json. It runs AFTER the main CCIRC pipeline and is
designed for fast iteration when scope definitions change.

Performance: 30 seconds - 2 minutes (vs 2-4 hours for full pipeline)

Usage:
1. Create Python recipe in DSS
2. Input: SP_display_seg
3. Output: SP_display_seg_scoped
4. Paste this code
5. Run
“””

import dataiku
import pandas as pd
import json
from typing import Dict, Any, List

# ==============================================================================

# Configuration

# ==============================================================================

# Input/Output dataset names

INPUT_DATASET = “SP_display_seg”
OUTPUT_DATASET = “SP_display_seg_scoped”

# Config file location (Managed Folder)

CONFIG_FOLDER = “ccirc_config”
CONFIG_FILE = “ccirc_params.json”

# Scope source columns (must exist in input dataset)

SCOPE_SOURCE_COLUMNS = [
“accounting_site_code_post_acc”,
“pmas_code_post_acc”,
“lb_site_risque_apres_accr”,
“cd_uds_pmas_metier_ap_acc”,
“business_country”,
]

# ==============================================================================

# Scope Computation Functions

# ==============================================================================

def compute_scope(df: pd.DataFrame, scope_id: str, filters: Dict[str, Any]) -> pd.Series:
“””
Compute a single scope boolean column.

```
Args:
    df: Input DataFrame
    scope_id: Scope identifier (for logging)
    filters: Dict of {column_name: filter_config}

Returns:
    Boolean Series (True where all filter conditions match)
"""
if not filters:
    return pd.Series([True] * len(df), index=df.index)

# Start with all True, then AND each condition
mask = pd.Series([True] * len(df), index=df.index)

for col_name, config in filters.items():
    # Skip metadata keys
    if col_name.startswith("_"):
        continue
    
    # Check column exists
    if col_name not in df.columns:
        print(f"  ⚠️ Column '{col_name}' not found, skipping filter")
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
    DataFrame with scope_* columns added
"""
df = df.copy()

for scope_id, config in scope_definitions.items():
    # Skip metadata keys
    if scope_id.startswith("_"):
        continue
    
    filters = config.get("filters", {})
    col_name = f"scope_{scope_id}"
    
    print(f"  Computing {col_name}...")
    df[col_name] = compute_scope(df, scope_id, filters)
    
    # Log stats
    count = df[col_name].sum()
    pct = 100 * count / len(df) if len(df) > 0 else 0
    print(f"    → {count:,} rows ({pct:.1f}%)")

return df
```

def get_scope_stats(df: pd.DataFrame, scope_ids: List[str]) -> Dict[str, Any]:
“””
Get statistics about scope membership.
“””
stats = {“total”: len(df)}

```
for scope_id in scope_ids:
    col = f"scope_{scope_id}"
    if col in df.columns:
        stats[scope_id] = int(df[col].sum())

# Count multi-scope rows
scope_cols = [f"scope_{s}" for s in scope_ids if f"scope_{s}" in df.columns]
if scope_cols:
    stats["multi_scope"] = int((df[scope_cols].sum(axis=1) > 1).sum())

return stats
```

# ==============================================================================

# Config Loading

# ==============================================================================

def load_scope_definitions() -> Dict[str, Any]:
“””
Load scope definitions from ccirc_params.json in Managed Folder.
“””
print(f”Loading config from {CONFIG_FOLDER}/{CONFIG_FILE}…”)

```
try:
    # Get managed folder
    folder = dataiku.Folder(CONFIG_FOLDER)
    
    # Read config file
    with folder.get_download_stream(CONFIG_FILE) as f:
        config = json.load(f)
    
    scopes = config.get("scopes", {})
    print(f"  Found {len(scopes)} scope definitions: {list(scopes.keys())}")
    
    return scopes

except Exception as e:
    print(f"  ⚠️ Error loading config: {e}")
    print(f"  Using fallback: loading from Project Variables")
    
    # Fallback: load from project variables
    client = dataiku.api_client()
    project = client.get_default_project()
    variables = project.get_variables()
    
    scopes = variables.get("standard", {}).get("scope_definitions", {})
    if isinstance(scopes, str):
        scopes = json.loads(scopes)
    
    return scopes
```

# ==============================================================================

# Validation

# ==============================================================================

def validate_input(df: pd.DataFrame) -> bool:
“””
Validate that input DataFrame has required source columns.
“””
print(“Validating input DataFrame…”)

```
missing_cols = []
for col in SCOPE_SOURCE_COLUMNS:
    if col not in df.columns:
        missing_cols.append(col)

if missing_cols:
    print(f"  ⚠️ Missing source columns: {missing_cols}")
    print(f"  Available columns: {list(df.columns)}")
    print(f"  ")
    print(f"  ACTION REQUIRED:")
    print(f"  1. Update pre_processing_ccirc to include these columns")
    print(f"  2. Re-run CCIRC pipeline once")
    print(f"  3. Then re-run this scope layer")
    return False

print(f"  ✓ All source columns present")
return True
```

# ==============================================================================

# Main Recipe

# ==============================================================================

def main():
“””
Main recipe execution.
“””
print(”=” * 70)
print(“DETECT CCIRC - Scope Layer”)
print(”=” * 70)

```
# Step 1: Load input dataset
print(f"\n[1/4] Loading input dataset: {INPUT_DATASET}")
input_ds = dataiku.Dataset(INPUT_DATASET)
df = input_ds.get_dataframe()
print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

# Step 2: Validate input
print(f"\n[2/4] Validating input")
if not validate_input(df):
    raise ValueError("Input validation failed. See messages above.")

# Step 3: Load scope definitions
print(f"\n[3/4] Loading scope definitions")
scope_definitions = load_scope_definitions()

if not scope_definitions:
    raise ValueError("No scope definitions found in config")

# Step 4: Compute scope columns
print(f"\n[4/4] Computing scope columns")
df_out = compute_all_scopes(df, scope_definitions)

# Get stats
scope_ids = [s for s in scope_definitions.keys() if not s.startswith("_")]
stats = get_scope_stats(df_out, scope_ids)

print(f"\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Total rows: {stats['total']:,}")
for scope_id in scope_ids:
    count = stats.get(scope_id, 0)
    pct = 100 * count / stats['total'] if stats['total'] > 0 else 0
    print(f"  scope_{scope_id}: {count:,} ({pct:.1f}%)")
print(f"  Multi-scope: {stats.get('multi_scope', 0):,}")

# Step 5: Write output
print(f"\nWriting output dataset: {OUTPUT_DATASET}")
output_ds = dataiku.Dataset(OUTPUT_DATASET)
output_ds.write_with_schema(df_out)

print(f"\n✅ Done! Output: {len(df_out):,} rows, {len(df_out.columns)} columns")
print("=" * 70)
```

# ==============================================================================

# Entry Point

# ==============================================================================

if **name** == “**main**”:
main()