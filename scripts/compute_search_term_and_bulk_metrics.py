#!/usr/bin/env python3
"""
Compute requested metrics from:
- Search term report (Nov): own product-targeting CTR/CVR
- Search term report (Dec): competitor product-targeting sales/spend/ROAS
- Bulk file: count enabled competitor product targets

Inputs (expected paths):
  data/asin_master.xlsx
  data/search_terms_2025-11.xlsx
  data/search_terms_2025-12.xlsx
  data/bulk.xlsx
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ASIN_RE = re.compile(r"\b[A-Z0-9]{10}\b")


@dataclass(frozen=True)
class Metrics:
    nov_own_ctr: float
    nov_own_cvr: float
    dec_comp_spend: float
    dec_comp_sales: float
    dec_comp_roas: float
    bulk_enabled_comp_targets: int
    bulk_enabled_comp_targets_strict: int


def _extract_asin(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    m = ASIN_RE.search(str(value))
    return m.group(0) if m else None


def _read_own_asins(asin_master_path: Path) -> set[str]:
    df = pd.read_excel(asin_master_path, sheet_name=0, dtype=str)
    col = df.columns[0]
    return {a.strip() for a in df[col].dropna().astype(str) if a and a.strip()}


def _load_search_terms(path: Path, own_asins: set[str]) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)

    # Column names are Japanese (Amazon Ads export). We rely on these:
    # - ターゲティング: targeting criterion (contains ASIN for product targeting)
    # - インプレッション: impressions
    # - クリック: clicks
    # - 費用: cost/spend
    # - 広告がクリックされてから7日間の総売上高: 7-day sales
    # - 広告がクリックされてから7日間の合計注文数: 7-day orders
    numeric_cols = [
        "インプレッション",
        "クリック",
        "費用",
        "広告がクリックされてから7日間の総売上高",
        "広告がクリックされてから7日間の合計注文数",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["_target_asin"] = df["ターゲティング"].map(_extract_asin)
    df["_is_product_target"] = df["_target_asin"].notna()
    df["_is_own_target"] = df["_is_product_target"] & df["_target_asin"].isin(own_asins)
    df["_is_competitor_target"] = df["_is_product_target"] & (~df["_target_asin"].isin(own_asins))
    return df


def compute_metrics(
    asin_master_path: Path,
    nov_path: Path,
    dec_path: Path,
    bulk_path: Path,
) -> Metrics:
    own_asins = _read_own_asins(asin_master_path)

    nov = _load_search_terms(nov_path, own_asins)
    dec = _load_search_terms(dec_path, own_asins)

    # 1) Nov own product targeting CTR = sum(clicks) / sum(impressions)
    nov_own = nov[nov["_is_own_target"]]
    nov_imp = float(nov_own["インプレッション"].sum())
    nov_clk = float(nov_own["クリック"].sum())
    nov_own_ctr = (nov_clk / nov_imp) if nov_imp else 0.0

    # 2) Nov own product targeting CVR = sum(orders) / sum(clicks)
    nov_orders = float(nov_own["広告がクリックされてから7日間の合計注文数"].sum())
    nov_own_cvr = (nov_orders / nov_clk) if nov_clk else 0.0

    # 3) Dec competitor product targeting sales/spend/ROAS
    dec_comp = dec[dec["_is_competitor_target"]]
    dec_comp_spend = float(dec_comp["費用"].sum())
    dec_comp_sales = float(dec_comp["広告がクリックされてから7日間の総売上高"].sum())
    dec_comp_roas = (dec_comp_sales / dec_comp_spend) if dec_comp_spend else 0.0

    # 4) Bulk: count enabled competitor product targets
    # We treat "商品ターゲティング" entity as (positive) product targeting.
    # "除外商品ターゲティング" is excluded.
    bulk_sheet = "スポンサープロダクト広告キャンペーン"
    usecols = [
        "エンティティ",
        "ステータス",
        "商品ターゲティング式",
        "商品ターゲティングID",
        "キャンペーンの状態（情報提供のみ）",
        "広告グループの状態（情報提供のみ）",
    ]
    bulk = pd.read_excel(
        bulk_path,
        sheet_name=bulk_sheet,
        usecols=lambda c: c in usecols,
        dtype=str,
    )
    bulk["_asin"] = bulk["商品ターゲティング式"].map(_extract_asin)
    base = bulk[(bulk["_asin"].notna()) & (bulk["エンティティ"].fillna("") == "商品ターゲティング")].copy()
    base = base[~base["_asin"].isin(own_asins)]
    enabled = base[base["ステータス"].fillna("") == "有効"]

    # Strict variant: only count targets whose campaign AND ad group are both active.
    strict = enabled[
        (enabled["キャンペーンの状態（情報提供のみ）"].fillna("") == "有効")
        & (enabled["広告グループの状態（情報提供のみ）"].fillna("") == "有効")
    ]

    bulk_enabled_comp_targets = int(enabled["商品ターゲティングID"].nunique())
    bulk_enabled_comp_targets_strict = int(strict["商品ターゲティングID"].nunique())

    return Metrics(
        nov_own_ctr=nov_own_ctr,
        nov_own_cvr=nov_own_cvr,
        dec_comp_spend=dec_comp_spend,
        dec_comp_sales=dec_comp_sales,
        dec_comp_roas=dec_comp_roas,
        bulk_enabled_comp_targets=bulk_enabled_comp_targets,
        bulk_enabled_comp_targets_strict=bulk_enabled_comp_targets_strict,
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    asin_master_path = root / "data" / "asin_master.xlsx"
    nov_path = root / "data" / "search_terms_2025-11.xlsx"
    dec_path = root / "data" / "search_terms_2025-12.xlsx"
    bulk_path = root / "data" / "bulk.xlsx"

    m = compute_metrics(
        asin_master_path=asin_master_path,
        nov_path=nov_path,
        dec_path=dec_path,
        bulk_path=bulk_path,
    )

    def pct(x: float) -> str:
        return f"{x*100:.2f}%"

    def money(x: float) -> str:
        return f"{x:,.2f}"

    print("## Metrics")  # human-readable, copy/paste friendly
    print(f"1) Nov own product-targeting CTR: {pct(m.nov_own_ctr)}")
    print(f"2) Nov own product-targeting CVR (orders/clicks): {pct(m.nov_own_cvr)}")
    print(f"3) Dec competitor product-targeting spend: {money(m.dec_comp_spend)}")
    print(f"   Dec competitor product-targeting sales: {money(m.dec_comp_sales)}")
    print(f"   Dec competitor product-targeting ROAS: {m.dec_comp_roas:.2f}")
    print(f"4) Bulk enabled competitor product targets (entity=商品ターゲティング): {m.bulk_enabled_comp_targets:,}")
    print(f"   (strict: enabled + campaign+adgroup active): {m.bulk_enabled_comp_targets_strict:,}")


if __name__ == "__main__":
    main()
