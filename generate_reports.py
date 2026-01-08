#!/usr/bin/env python3
"""
Generate seller before/after summary Excel files from provided source reports.

Inputs (default):
  - Traffic / Business report (ASIN list + total sales):
    - /workspace/data/raw/file_1WSfWFB0Gkwc9WmlEwJ9aeUjBha6OSFNI.csv
    - /workspace/data/raw/file_13GTQvJU91pLXGKGOfxdIG6T6zzXk1m-N.csv
  - Sponsored Products (SP) Search Term report (Before/After are auto-detected via min 開始日):
    - /workspace/data/raw/sheet_1dcUxn-5Ih8vH1gVVtAXQ6c2wC0hexjMm.xlsx
    - /workspace/data/raw/sheet_1BBW9mBpGd7nHmvMBeRRSHV0uRV_QIQkA.xlsx

Outputs:
  - /workspace/first_data.xlsx
  - /workspace/second_data.xlsx
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path("/workspace")
RAW = ROOT / "data" / "raw"


def _to_number(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s or s.lower() in {"nan", "none"}:
        return 0.0
    # Handle currency and comma-separated numbers: "￥179,685" -> 179685
    s = s.replace(",", "")
    s = s.replace("¥", "").replace("￥", "")
    # Keep digits, minus sign, and dot only.
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in {"-", "."}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


def _read_csv_traffic(path: Path) -> pd.DataFrame:
    # Amazon reports often have BOM.
    return pd.read_csv(path, encoding="utf-8-sig")


@dataclass(frozen=True)
class TrafficAgg:
    total_sales: float
    total_units: float
    asin_set: set[str]


def agg_traffic(path: Path) -> TrafficAgg:
    df = _read_csv_traffic(path)
    # Use total columns (non-B2B) that typically already include B2B in "total".
    sales = df["注文商品の売上額"].map(_to_number).sum()
    units = df["注文された商品点数"].map(_to_number).sum()
    asins: set[str] = set()
    for col in ["（親）ASIN", "（子）ASIN"]:
        if col in df.columns:
            asins.update({str(x).strip() for x in df[col].dropna().astype(str).tolist() if str(x).strip()})
    return TrafficAgg(total_sales=float(sales), total_units=float(units), asin_set=asins)


@dataclass(frozen=True)
class AdsAgg:
    impressions: float
    clicks: float
    spend: float
    sales: float
    orders: float
    units: float
    portfolios: int
    campaigns: int
    ad_groups: int
    targetings: int
    avg_bid: float
    # For second dataset (SP-only breakdown)
    sp_auto_sales: float
    sp_own_pt_sales: float
    sp_comp_pt_sales: float
    sp_auto_spend: float
    sp_own_pt_spend: float
    sp_comp_pt_spend: float


def _sum_campaign_metrics(df: pd.DataFrame) -> dict[str, float]:
    for c in ["インプレッション数", "クリック数", "支出", "売上", "注文", "商品点数"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return {
        "impressions": float(df.get("インプレッション数", 0).sum()),
        "clicks": float(df.get("クリック数", 0).sum()),
        "spend": float(df.get("支出", 0).sum()),
        "sales": float(df.get("売上", 0).sum()),
        "orders": float(df.get("注文", 0).sum()),
        "units": float(df.get("商品点数", 0).sum()),
    }


_ASIN_RE = re.compile(r'asin(?:-expanded)?="([A-Z0-9]{10})"', re.IGNORECASE)


def _extract_asin(expr: Any) -> str | None:
    if expr is None or (isinstance(expr, float) and pd.isna(expr)):
        return None
    m = _ASIN_RE.search(str(expr))
    return m.group(1).upper() if m else None


def agg_ads(workbook_path: Path, own_asins: set[str]) -> AdsAgg:
    # This script version expects an SP Search Term report workbook with 1 sheet.
    # Sheet name can vary; use the first sheet.
    sheet0 = pd.ExcelFile(workbook_path).sheet_names[0]
    df = pd.read_excel(workbook_path, sheet_name=sheet0)

    # Normalize numeric columns we need.
    num_cols = {
        "インプレッション": "impressions",
        "クリック": "clicks",
        "費用": "spend",
        "広告がクリックされてから7日間の総売上高": "sales",
        "広告がクリックされてから7日間の合計注文数": "orders",
        "広告がクリックされてから7日間の合計販売数": "units",
    }
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0

    impressions = float(df["インプレッション"].sum())
    clicks = float(df["クリック"].sum())
    spend = float(df["費用"].sum())
    sales = float(df["広告がクリックされてから7日間の総売上高"].sum())
    orders = float(df["広告がクリックされてから7日間の合計注文数"].sum())
    units = float(df["広告がクリックされてから7日間の合計販売数"].sum())

    # Counts from the report itself (SP only)
    portfolios = int(df["ポートフォリオ名"].dropna().astype(str).nunique()) if "ポートフォリオ名" in df.columns else 0
    campaigns = int(df["キャンペーン名"].dropna().astype(str).nunique()) if "キャンペーン名" in df.columns else 0
    ad_groups = int(df["広告グループ名"].dropna().astype(str).nunique()) if "広告グループ名" in df.columns else 0
    if "ターゲティング" in df.columns and "マッチタイプ" in df.columns:
        targetings = int(df[["ターゲティング", "マッチタイプ"]].dropna().astype(str).drop_duplicates().shape[0])
    elif "ターゲティング" in df.columns:
        targetings = int(df["ターゲティング"].dropna().astype(str).nunique())
    else:
        targetings = 0

    # Bid is not included in this report export; leave 0.
    avg_bid = 0.0

    # Second dataset breakdown (SP-only) from this report:
    # - auto: rows where ターゲティング in auto buckets OR campaign name indicates auto
    auto_targets = {"close-match", "loose-match", "substitutes", "complements"}
    tgt = df["ターゲティング"].astype(str) if "ターゲティング" in df.columns else pd.Series([""] * len(df))
    camp = df["キャンペーン名"].astype(str) if "キャンペーン名" in df.columns else pd.Series([""] * len(df))
    is_auto = tgt.str.lower().isin(auto_targets) | camp.str.contains("オート", regex=False) | camp.str.contains("auto", case=False, regex=False)
    sp_auto_sales = float(df.loc[is_auto, "広告がクリックされてから7日間の総売上高"].sum())
    sp_auto_spend = float(df.loc[is_auto, "費用"].sum())

    # - own/competitor ASIN targeting: rows where ターゲティング contains ASIN
    asin = tgt.map(_extract_asin)
    is_asin = asin.notna()
    own_upper = {a.upper() for a in own_asins}
    is_own = asin.isin(own_upper)
    sp_own_pt_sales = float(df.loc[is_asin & is_own, "広告がクリックされてから7日間の総売上高"].sum())
    sp_comp_pt_sales = float(df.loc[is_asin & ~is_own, "広告がクリックされてから7日間の総売上高"].sum())
    sp_own_pt_spend = float(df.loc[is_asin & is_own, "費用"].sum())
    sp_comp_pt_spend = float(df.loc[is_asin & ~is_own, "費用"].sum())

    return AdsAgg(
        impressions=impressions,
        clicks=clicks,
        spend=spend,
        sales=sales,
        orders=orders,
        units=units,
        portfolios=portfolios,
        campaigns=campaigns,
        ad_groups=ad_groups,
        targetings=targetings,
        avg_bid=avg_bid,
        sp_auto_sales=sp_auto_sales,
        sp_own_pt_sales=sp_own_pt_sales,
        sp_comp_pt_sales=sp_comp_pt_sales,
        sp_auto_spend=sp_auto_spend,
        sp_own_pt_spend=sp_own_pt_spend,
        sp_comp_pt_spend=sp_comp_pt_spend,
    )


def build_first_table(traffic_before: TrafficAgg, traffic_after: TrafficAgg, ads_before: AdsAgg, ads_after: AdsAgg) -> pd.DataFrame:
    def row(item: str, b: float, a: float) -> dict[str, Any]:
        diff = a - b
        ratio = _safe_div(a, b)
        return {"項目": item, "Before": b, "After": a, "前後差": diff, "前後比": ratio}

    total_sales_b = traffic_before.total_sales
    total_sales_a = traffic_after.total_sales

    ad_spend_b = ads_before.spend
    ad_spend_a = ads_after.spend

    ad_sales_b = ads_before.sales
    ad_sales_a = ads_after.sales

    imps_b, imps_a = ads_before.impressions, ads_after.impressions
    clicks_b, clicks_a = ads_before.clicks, ads_after.clicks

    orders_b, orders_a = ads_before.orders, ads_after.orders

    units_b, units_a = traffic_before.total_units, traffic_after.total_units

    rows: list[dict[str, Any]] = []
    rows.append(row("総売上高", total_sales_b, total_sales_a))
    rows.append(row("広告費", ad_spend_b, ad_spend_a))
    rows.append(row("TACOS", _safe_div(ad_spend_b, total_sales_b), _safe_div(ad_spend_a, total_sales_a)))
    rows.append(row("広告経由売上", ad_sales_b, ad_sales_a))
    rows.append(row("広告経由売上比率", _safe_div(ad_sales_b, total_sales_b), _safe_div(ad_sales_a, total_sales_a)))
    rows.append(row("広告経由売上-広告費", ad_sales_b - ad_spend_b, ad_sales_a - ad_spend_a))
    rows.append(row("ROAS（費用対効果)", _safe_div(ad_sales_b, ad_spend_b), _safe_div(ad_sales_a, ad_spend_a)))
    rows.append(row("インプレッション", imps_b, imps_a))
    rows.append(row("クリック", clicks_b, clicks_a))
    rows.append(row("CTR（クリック率）", _safe_div(clicks_b, imps_b), _safe_div(clicks_a, imps_a)))
    rows.append(row("入札単価", ads_before.avg_bid, ads_after.avg_bid))
    rows.append(row("CPC（クリック単価）", _safe_div(ad_spend_b, clicks_b), _safe_div(ad_spend_a, clicks_a)))
    rows.append(row("販売数", units_b, units_a))
    rows.append(row("CVR（購入転換率）", _safe_div(orders_b, clicks_b), _safe_div(orders_a, clicks_a)))
    rows.append(row("平均販売単価", _safe_div(total_sales_b, units_b), _safe_div(total_sales_a, units_a)))
    rows.append(row("ポートフォリオ数", float(ads_before.portfolios), float(ads_after.portfolios)))
    rows.append(row("キャンペーン数", float(ads_before.campaigns), float(ads_after.campaigns)))
    rows.append(row("広告グループ数", float(ads_before.ad_groups), float(ads_after.ad_groups)))
    rows.append(row("ターゲティング数", float(ads_before.targetings), float(ads_after.targetings)))
    return pd.DataFrame(rows)


def build_second_table(ads_before: AdsAgg, ads_after: AdsAgg) -> pd.DataFrame:
    rows = [
        (
            "자사 상품 타게팅 경유 매상(ASIN) 총합",
            ads_before.sp_own_pt_sales,
            ads_after.sp_own_pt_sales,
            ads_before.sp_own_pt_spend,
            ads_after.sp_own_pt_spend,
        ),
        (
            "오토 광고 경유 매상 총합",
            ads_before.sp_auto_sales,
            ads_after.sp_auto_sales,
            ads_before.sp_auto_spend,
            ads_after.sp_auto_spend,
        ),
        (
            "타사 상품(ASIN) 타게팅 경유 매상 총합",
            ads_before.sp_comp_pt_sales,
            ads_after.sp_comp_pt_sales,
            ads_before.sp_comp_pt_spend,
            ads_after.sp_comp_pt_spend,
        ),
    ]
    return pd.DataFrame(rows, columns=["항목", "before_sales", "after_sales", "before_spend", "after_spend"])


def write_excel_first(df: pd.DataFrame, out_path: Path) -> None:
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="first_data")
        wb = writer.book
        ws = writer.sheets["first_data"]

        fmt_int = wb.add_format({"num_format": "#,##0"})
        fmt_money = wb.add_format({"num_format": "#,##0"})
        fmt_pct = wb.add_format({"num_format": "0.00%"})
        fmt_ratio = wb.add_format({"num_format": "0.0000"})

        # Column widths
        ws.set_column(0, 0, 28)  # 項目
        ws.set_column(1, 3, 16)  # Before/After/差
        ws.set_column(4, 4, 12)  # 比

        # Apply per-row formats
        pct_items = {
            "TACOS",
            "広告経由売上比率",
            "CTR（クリック率）",
            "CVR（購入転換率）",
        }
        ratio_like_items = {
            "ROAS（費用対効果)",
            "前後比",
        }

        for r in range(1, len(df) + 1):
            item = str(df.iloc[r - 1]["項目"])
            if item in pct_items:
                ws.write_number(r, 1, float(df.iloc[r - 1]["Before"]), fmt_pct)
                ws.write_number(r, 2, float(df.iloc[r - 1]["After"]), fmt_pct)
                ws.write_number(r, 3, float(df.iloc[r - 1]["前後差"]), fmt_pct)
                ws.write_number(r, 4, float(df.iloc[r - 1]["前後比"]), fmt_ratio)
            elif item in {"ポートフォリオ数", "キャンペーン数", "広告グループ数", "ターゲティング数"}:
                ws.write_number(r, 1, float(df.iloc[r - 1]["Before"]), fmt_int)
                ws.write_number(r, 2, float(df.iloc[r - 1]["After"]), fmt_int)
                ws.write_number(r, 3, float(df.iloc[r - 1]["前後差"]), fmt_int)
                ws.write_number(r, 4, float(df.iloc[r - 1]["前後比"]), fmt_ratio)
            elif item in {"ROAS（費用対効果)"}:
                ws.write_number(r, 1, float(df.iloc[r - 1]["Before"]), fmt_ratio)
                ws.write_number(r, 2, float(df.iloc[r - 1]["After"]), fmt_ratio)
                ws.write_number(r, 3, float(df.iloc[r - 1]["前後差"]), fmt_ratio)
                ws.write_number(r, 4, float(df.iloc[r - 1]["前後比"]), fmt_ratio)
            else:
                # Default: money/amount style for Before/After/差, and ratio for 前後比
                ws.write_number(r, 1, float(df.iloc[r - 1]["Before"]), fmt_money)
                ws.write_number(r, 2, float(df.iloc[r - 1]["After"]), fmt_money)
                ws.write_number(r, 3, float(df.iloc[r - 1]["前後差"]), fmt_money)
                ws.write_number(r, 4, float(df.iloc[r - 1]["前後比"]), fmt_ratio)


def write_excel_second(df: pd.DataFrame, out_path: Path) -> None:
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="second_data")
        wb = writer.book
        ws = writer.sheets["second_data"]
        fmt_money = wb.add_format({"num_format": "#,##0"})
        ws.set_column(0, 0, 40)
        ws.set_column(1, 4, 18, fmt_money)


def main() -> None:
    # Determine before/after for traffic by total sales (smaller => earlier period).
    traffic_paths = [
        RAW / "file_1WSfWFB0Gkwc9WmlEwJ9aeUjBha6OSFNI.csv",
        RAW / "file_13GTQvJU91pLXGKGOfxdIG6T6zzXk1m-N.csv",
    ]
    traffic_aggs = [(p, agg_traffic(p)) for p in traffic_paths]
    traffic_aggs.sort(key=lambda x: x[1].total_sales)
    traffic_before_path, traffic_after_path = traffic_aggs[0][0], traffic_aggs[1][0]

    # Determine before/after for SP search-term workbooks by min 開始日 (earlier => before).
    ads_paths = [
        RAW / "sheet_1dcUxn-5Ih8vH1gVVtAXQ6c2wC0hexjMm.xlsx",
        RAW / "sheet_1BBW9mBpGd7nHmvMBeRRSHV0uRV_QIQkA.xlsx",
    ]
    def min_start_date(p: Path) -> pd.Timestamp:
        sh0 = pd.ExcelFile(p).sheet_names[0]
        d = pd.read_excel(p, sheet_name=sh0, usecols=["開始日"])
        return pd.to_datetime(d["開始日"], errors="coerce").min()

    ads_paths.sort(key=min_start_date)
    ads_before_path, ads_after_path = ads_paths[0], ads_paths[1]

    traffic_before = agg_traffic(traffic_before_path)
    traffic_after = agg_traffic(traffic_after_path)
    own_asins = set().union(traffic_before.asin_set, traffic_after.asin_set)

    ads_before = agg_ads(ads_before_path, own_asins=own_asins)
    ads_after = agg_ads(ads_after_path, own_asins=own_asins)

    first = build_first_table(traffic_before, traffic_after, ads_before, ads_after)
    second = build_second_table(ads_before, ads_after)

    out_first = ROOT / "first_data.xlsx"
    out_second = ROOT / "second_data.xlsx"
    write_excel_first(first, out_first)
    write_excel_second(second, out_second)

    print("Wrote:", out_first)
    print("Wrote:", out_second)


if __name__ == "__main__":
    main()

