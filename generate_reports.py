#!/usr/bin/env python3
"""
Generate seller before/after summary Excel files from provided source reports.

Inputs (default):
  - /workspace/data/raw/file_1WSfWFB0Gkwc9WmlEwJ9aeUjBha6OSFNI.csv  (Before: traffic/Business report)
  - /workspace/data/raw/file_13GTQvJU91pLXGKGOfxdIG6T6zzXk1m-N.csv  (After:  traffic/Business report)
  - /workspace/data/raw/sheet_1InXM_M21D-foVVzP7nQwV-o09PiYUY9s.xlsx (Before: ads bulk/report)
  - /workspace/data/raw/sheet_1maJin4HFjRV3UgU9iCJqWZIC0TtrxCRY.xlsx (After: ads bulk/report)

Outputs:
  - /workspace/first_data.xlsx
  - /workspace/second_data.xlsx
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

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
    # Portfolio counts
    pf = pd.read_excel(workbook_path, sheet_name="ポートフォリオ")
    pf_status_col = "ステータス（情報提供のみ）"
    portfolios = int(pf.loc[pf[pf_status_col].astype(str) == "有効", "ポートフォリオID"].nunique())

    # Campaign performance totals (avoid double-counting by using エンティティ == キャンペーン only)
    totals = {"impressions": 0.0, "clicks": 0.0, "spend": 0.0, "sales": 0.0, "orders": 0.0, "units": 0.0}
    campaign_ids: set[str] = set()

    # SP
    sp = pd.read_excel(workbook_path, sheet_name="スポンサープロダクト広告キャンペーン")
    sp_campaign = sp.loc[(sp["エンティティ"] == "キャンペーン") & (sp["ステータス"] == "有効")].copy()
    totals_sp = _sum_campaign_metrics(sp_campaign)
    for k in totals:
        totals[k] += totals_sp[k]
    campaign_ids.update(sp_campaign["キャンペーンID"].dropna().astype(str).tolist())

    # SB
    sb = pd.read_excel(workbook_path, sheet_name="スポンサーブランド広告キャンペーン")
    sb_campaign = sb.loc[(sb["エンティティ"] == "キャンペーン") & (sb["ステータス"] == "有効")].copy()
    totals_sb = _sum_campaign_metrics(sb_campaign)
    for k in totals:
        totals[k] += totals_sb[k]
    campaign_ids.update(sb_campaign["キャンペーンID"].dropna().astype(str).tolist())

    # SD
    sd = pd.read_excel(workbook_path, sheet_name="スポンサーディスプレイ広告キャンペーン")
    sd_campaign = sd.loc[(sd["エンティティ"] == "キャンペーン") & (sd["ステータス"] == "有効")].copy()
    totals_sd = _sum_campaign_metrics(sd_campaign)
    for k in totals:
        totals[k] += totals_sd[k]
    campaign_ids.update(sd_campaign["キャンペーンID"].dropna().astype(str).tolist())

    campaigns = int(len(campaign_ids))

    # Ad groups count (SP + SD + SB複数広告グループ)
    sp_adg = int(sp.loc[(sp["エンティティ"] == "広告グループ") & (sp["ステータス"] == "有効"), "広告グループID"].nunique())
    sd_adg = int(sd.loc[(sd["エンティティ"] == "広告グループ") & (sd["ステータス"] == "有効"), "広告グループID"].nunique())
    sb_multi = pd.read_excel(workbook_path, sheet_name="SB複数広告グループ")
    sb_adg = 0
    if not sb_multi.empty and "エンティティ" in sb_multi.columns and "広告グループID" in sb_multi.columns:
        status_col = "状態" if "状態" in sb_multi.columns else "ステータス"
        if status_col in sb_multi.columns:
            sb_adg = int(
                sb_multi.loc[(sb_multi["エンティティ"] == "広告グループ") & (sb_multi[status_col].astype(str) == "有効"), "広告グループID"].nunique()
            )
    ad_groups = int(sp_adg + sd_adg + sb_adg)

    # Targeting count (keywords + product targeting + SD targetings)
    targeting_keys: set[tuple[str, str]] = set()

    # SP keywords + product targeting
    if "キーワードID" in sp.columns:
        ids = sp.loc[(sp["エンティティ"] == "キーワード") & (sp["ステータス"] == "有効"), "キーワードID"].dropna().astype(str)
        targeting_keys.update({("sp_kw", i) for i in ids.tolist()})
    if "商品ターゲティングID" in sp.columns:
        ids = sp.loc[(sp["エンティティ"] == "商品ターゲティング") & (sp["ステータス"] == "有効"), "商品ターゲティングID"].dropna().astype(str)
        targeting_keys.update({("sp_pt", i) for i in ids.tolist()})

    # SB keywords + product targeting
    if "キーワードID" in sb.columns:
        ids = sb.loc[(sb["エンティティ"] == "キーワード") & (sb["ステータス"] == "有効"), "キーワードID"].dropna().astype(str)
        targeting_keys.update({("sb_kw", i) for i in ids.tolist()})
    if "商品ターゲティングID" in sb.columns:
        ids = sb.loc[(sb["エンティティ"] == "商品ターゲティング") & (sb["ステータス"] == "有効"), "商品ターゲティングID"].dropna().astype(str)
        targeting_keys.update({("sb_pt", i) for i in ids.tolist()})

    # SD targetings
    if "ターゲティングID" in sd.columns:
        ids = sd.loc[(sd["エンティティ"].isin(["コンテキストターゲティング", "オーディエンスターゲティング"])) & (sd["ステータス"] == "有効"), "ターゲティングID"].dropna().astype(str)
        targeting_keys.update({("sd_tg", i) for i in ids.tolist()})

    targetings = int(len(targeting_keys))

    # Avg bid (weighted by clicks) from search term reports (SP + SB)
    bid_clicks = 0.0
    bid_weighted_sum = 0.0
    for sh in ["SP検索ワードレポート", "SB検索ワードレポート"]:
        st = pd.read_excel(workbook_path, sheet_name=sh)
        if "入札額" not in st.columns or "クリック数" not in st.columns:
            continue
        bids = pd.to_numeric(st["入札額"], errors="coerce").fillna(0)
        clicks = pd.to_numeric(st["クリック数"], errors="coerce").fillna(0)
        bid_weighted_sum += float((bids * clicks).sum())
        bid_clicks += float(clicks.sum())
    avg_bid = float(bid_weighted_sum / bid_clicks) if bid_clicks else 0.0

    # Second dataset breakdown (SP-only)
    # - auto sales: SP campaign rows where ターゲティングの種類 == オート
    sp_auto_sales = 0.0
    if "ターゲティングの種類" in sp_campaign.columns and "売上" in sp_campaign.columns:
        sp_auto_sales = float(sp_campaign.loc[sp_campaign["ターゲティングの種類"].astype(str) == "オート", "売上"].sum())

    # - own/competitor product targeting sales: SP product targeting entity rows
    sp_pt = sp.loc[(sp["エンティティ"] == "商品ターゲティング") & (sp["ステータス"] == "有効")].copy()
    if "売上" in sp_pt.columns:
        sp_pt["売上"] = pd.to_numeric(sp_pt["売上"], errors="coerce").fillna(0)
    else:
        sp_pt["売上"] = 0
    asin = sp_pt.get("商品ターゲティング式", pd.Series([None] * len(sp_pt))).map(_extract_asin)
    sp_pt["target_asin"] = asin
    # IMPORTANT:
    # 商品ターゲティング式 can be non-ASIN expressions (e.g. close-match/loose-match/complements/substitutes).
    # Those are NOT "competitor ASIN targeting", so we must exclude them from own/competitor ASIN buckets.
    sp_pt_asin = sp_pt.loc[sp_pt["target_asin"].notna()].copy()
    own_upper = {a.upper() for a in own_asins}
    is_own = sp_pt_asin["target_asin"].isin(own_upper)
    sp_own_pt_sales = float(sp_pt_asin.loc[is_own, "売上"].sum())
    sp_comp_pt_sales = float(sp_pt_asin.loc[~is_own, "売上"].sum())

    return AdsAgg(
        impressions=totals["impressions"],
        clicks=totals["clicks"],
        spend=totals["spend"],
        sales=totals["sales"],
        orders=totals["orders"],
        units=totals["units"],
        portfolios=portfolios,
        campaigns=campaigns,
        ad_groups=ad_groups,
        targetings=targetings,
        avg_bid=avg_bid,
        sp_auto_sales=sp_auto_sales,
        sp_own_pt_sales=sp_own_pt_sales,
        sp_comp_pt_sales=sp_comp_pt_sales,
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
        ("자사 상품 타게팅 경유 매상의 총합", ads_before.sp_own_pt_sales, ads_after.sp_own_pt_sales),
        ("오토 광고 경유 매상의 총합", ads_before.sp_auto_sales, ads_after.sp_auto_sales),
        ("타사 상품 광고 경유 매상의 총합", ads_before.sp_comp_pt_sales, ads_after.sp_comp_pt_sales),
    ]
    return pd.DataFrame(rows, columns=["항목", "before", "after"])


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
        ws.set_column(1, 2, 18, fmt_money)


def main() -> None:
    traffic_before_path = RAW / "file_1WSfWFB0Gkwc9WmlEwJ9aeUjBha6OSFNI.csv"
    traffic_after_path = RAW / "file_13GTQvJU91pLXGKGOfxdIG6T6zzXk1m-N.csv"
    ads_before_path = RAW / "sheet_1InXM_M21D-foVVzP7nQwV-o09PiYUY9s.xlsx"
    ads_after_path = RAW / "sheet_1maJin4HFjRV3UgU9iCJqWZIC0TtrxCRY.xlsx"

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

