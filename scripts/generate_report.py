from __future__ import annotations

import math
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Source sheets provided by user (Google Sheets -> export xlsx)
SOURCES = {
    "past_campaigns": {
        "xlsx": DATA_DIR / "past_campaigns.xlsx",
        "url": "https://docs.google.com/spreadsheets/d/1MDPtkamnYcnuEsR0XMup-Kx28MT4PAg8/export?format=xlsx",
    },
    "asin_overview": {
        "xlsx": DATA_DIR / "asin_overview.xlsx",
        "url": "https://docs.google.com/spreadsheets/d/1R34bPbnDaU4sNAFkT4puAUW0qfNgcVV7/export?format=xlsx",
    },
    "ads_bulk": {
        "xlsx": DATA_DIR / "ads_bulk.xlsx",
        "url": "https://docs.google.com/spreadsheets/d/1CUKSQEHIyue5ZFYvJ0Uktgr4c3gUT8gv/export?format=xlsx",
    },
}


def _download_if_missing(path: Path, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    print(f"[download] {url} -> {path}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp:  # noqa: S310 (trusted user-provided URL)
        path.write_bytes(resp.read())


def _to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _month_sort_key(m: str) -> int:
    m = str(m)
    m = m.replace("月", "")
    try:
        return int(m)
    except ValueError:
        return 999


def _find_header_row_by_cells(
    df_raw: pd.DataFrame,
    required_cells: dict[int, str],
    *,
    contains: bool = False,
) -> int | None:
    """
    Find a row index where df_raw.iloc[i, col] equals (or contains) the required string.
    """
    for i in range(len(df_raw)):
        ok = True
        row = df_raw.iloc[i]
        for col, val in required_cells.items():
            cell = row.iloc[col]
            if pd.isna(cell):
                ok = False
                break
            cell_s = str(cell).strip()
            if contains:
                if val not in cell_s:
                    ok = False
                    break
            else:
                if cell_s != val:
                    ok = False
                    break
        if ok:
            return i
    return None


def load_past_campaigns() -> pd.DataFrame:
    """
    The file contains a flattened header section with columns like:
    広告費_10月, 広告経由売上_10月, ...
    We'll locate that header row and load the table from there.
    """
    xlsx = SOURCES["past_campaigns"]["xlsx"]
    df_raw = pd.read_excel(xlsx, sheet_name="Sheet1", header=None)

    hdr = _find_header_row_by_cells(
        df_raw,
        {
            0: "キャンペーン",
            3: "広告費_10月",  # observed in this file
        },
    )
    if hdr is None:
        # fallback: locate any row containing "広告費_" in column 3 and "キャンペーン" in column 0
        hdr = _find_header_row_by_cells(df_raw, {0: "キャンペーン", 3: "広告費_"}, contains=True)
    if hdr is None:
        raise RuntimeError("Could not locate flattened header row in past_campaigns.xlsx")

    df = pd.read_excel(xlsx, sheet_name="Sheet1", skiprows=hdr, header=0)
    # Drop fully empty rows
    df = df.dropna(how="all").copy()
    return df


def load_asin_overview() -> pd.DataFrame:
    """
    asin_overview.xlsx uses 2 header rows for groups (e.g., 売上 / GV) and a base header row.
    We'll synthesize unique column names like '売上_12月', 'GV_11月', etc.
    """
    xlsx = SOURCES["asin_overview"]["xlsx"]
    df_raw = pd.read_excel(xlsx, sheet_name="Sheet1", header=None)

    hdr = _find_header_row_by_cells(df_raw, {0: "GL", 4: "親ASIN"})
    if hdr is None or hdr < 1:
        raise RuntimeError("Could not locate header row in asin_overview.xlsx")

    # Group labels (e.g., 売上 / GV) are often only written once and then left blank.
    # Forward-fill across columns so each month column inherits the correct group.
    group_row = df_raw.iloc[hdr - 1].ffill()
    header_row = df_raw.iloc[hdr]

    cols: list[str] = []
    for j in range(df_raw.shape[1]):
        base = header_row.iloc[j]
        grp = group_row.iloc[j]
        base_s = "" if pd.isna(base) else str(base).strip()
        grp_s = "" if pd.isna(grp) else str(grp).strip()
        if base_s == "":
            base_s = f"col{j}"
        if grp_s != "" and grp_s != "基本情報":
            cols.append(f"{grp_s}_{base_s}")
        else:
            cols.append(base_s)

    data = df_raw.iloc[hdr + 1 :].copy()
    data.columns = cols
    data = data.dropna(how="all").copy()
    return data


def _extract_month_columns(df: pd.DataFrame, prefix: str) -> list[str]:
    pat = re.compile(rf"^{re.escape(prefix)}_(\d+月)$")
    months: list[str] = []
    for c in df.columns:
        m = pat.match(str(c))
        if m:
            months.append(m.group(1))
    months = sorted(set(months), key=_month_sort_key)
    return months


def _safe_div(n: float, d: float) -> float | None:
    if d == 0 or (isinstance(d, float) and math.isnan(d)):
        return None
    if isinstance(n, float) and math.isnan(n):
        return None
    return n / d


def _fmt_money(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:,.0f}"


def _fmt_ratio(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return f"{x:.{digits}f}"


def _normalize_text(s: str) -> str:
    s = str(s)
    s = s.lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[\[\]（）\(\)【】「」『』・,，/\\:_\-]+", "", s)
    return s


def _extract_campaign_keyword(campaign_name: str) -> str:
    s = str(campaign_name)
    s = re.sub(r"^\s*\[[^\]]+\]\s*", "", s)  # drop leading [SP] etc
    s = s.replace("オート", "")
    # Often campaign names include portfolio-ish suffix after underscore
    s = s.split("_")[0]
    s = s.strip(" -–—\t")
    return s.strip()


@dataclass(frozen=True)
class BulkTotals:
    impressions: float
    clicks: float
    spend: float
    sales: float

    @property
    def roas(self) -> float | None:
        return _safe_div(self.sales, self.spend)


def _bulk_campaign_totals(xlsx: Path, sheet_name: str) -> BulkTotals:
    df = pd.read_excel(xlsx, sheet_name=sheet_name)
    if "エンティティ" not in df.columns:
        raise RuntimeError(f"Missing エンティティ in sheet: {sheet_name}")
    camp = df[df["エンティティ"].astype(str) == "キャンペーン"].copy()
    for c in ["インプレッション数", "クリック数", "支出", "売上"]:
        if c not in camp.columns:
            raise RuntimeError(f"Missing {c} in sheet: {sheet_name}")
        camp[c] = _to_number(camp[c]).fillna(0)
    return BulkTotals(
        impressions=float(camp["インプレッション数"].sum()),
        clicks=float(camp["クリック数"].sum()),
        spend=float(camp["支出"].sum()),
        sales=float(camp["売上"].sum()),
    )


ASIN_RE = re.compile(r"\bB0[0-9A-Z]{8}\b")


def _extract_asin_from_expression(expr: str | float) -> str | None:
    if pd.isna(expr):
        return None
    s = str(expr)
    m = ASIN_RE.search(s)
    return m.group(0) if m else None


def bulk_sp_competitor_product_targeting_sales(xlsx: Path) -> tuple[float, float, float | None]:
    """
    Interpretation of "SP広告の他社商品経由の売上":
    - Sponsored Products (SP)
    - Product targeting rows (商品ターゲティング) that target ASINs not in our own advertised ASIN set
    Returns: (sales, spend, roas)
    """
    df = pd.read_excel(xlsx, sheet_name="スポンサープロダクト広告キャンペーン")
    own = set(
        df.loc[df["エンティティ"].astype(str) == "プロダクト広告", "ASIN（情報提供のみ）"]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    pt = df[df["エンティティ"].astype(str) == "商品ターゲティング"].copy()
    # Prefer resolved expression if present
    expr_col = "解決済みの商品ターゲティング式（情報提供のみ）" if "解決済みの商品ターゲティング式（情報提供のみ）" in pt.columns else "商品ターゲティング式"
    pt["target_asin"] = pt[expr_col].apply(_extract_asin_from_expression)

    for c in ["支出", "売上"]:
        pt[c] = _to_number(pt[c]).fillna(0)

    competitor = pt[pt["target_asin"].notna() & ~pt["target_asin"].isin(own)]
    sales = float(competitor["売上"].sum())
    spend = float(competitor["支出"].sum())
    return sales, spend, _safe_div(sales, spend)


def generate_report() -> str:
    # Ensure inputs exist (download if missing)
    for cfg in SOURCES.values():
        _download_if_missing(cfg["xlsx"], cfg["url"])

    past = load_past_campaigns()
    asin = load_asin_overview()
    ads_xlsx = SOURCES["ads_bulk"]["xlsx"]

    # -------- (1) Parent-ASIN auto campaigns: monthly avg spend/sales/ROAS --------
    auto = past[past["キャンペーン"].astype(str).str.contains("オート", na=False)].copy()

    spend_months = _extract_month_columns(past, "広告費")
    sales_months = _extract_month_columns(past, "広告経由売上")

    # Prefer the user's requested months if present.
    preferred = ["10月", "11月"]
    months = [m for m in preferred if (m in spend_months and m in sales_months)]
    if not months:
        # Fallback: use intersection of available months (sorted) and pick the latest 2 (or all)
        common = [m for m in spend_months if m in sales_months]
        months = common[-2:] if len(common) >= 2 else common

    for m in months:
        auto[f"広告費_{m}"] = _to_number(auto.get(f"広告費_{m}", pd.Series(dtype=float))).fillna(0)
        auto[f"広告経由売上_{m}"] = _to_number(auto.get(f"広告経由売上_{m}", pd.Series(dtype=float))).fillna(0)

    def _row_avg(cols: Iterable[str]) -> pd.Series:
        cols = list(cols)
        if not cols:
            return pd.Series([float("nan")] * len(auto), index=auto.index)
        return auto[cols].mean(axis=1)

    auto["月平均_広告費"] = _row_avg([f"広告費_{m}" for m in months])
    auto["月平均_広告経由売上"] = _row_avg([f"広告経由売上_{m}" for m in months])
    auto["月平均_ROAS"] = auto.apply(lambda r: _safe_div(float(r["月平均_広告経由売上"]), float(r["月平均_広告費"])), axis=1)

    # Summary table (top by avg spend)
    auto_summary = (
        auto[["キャンペーン", "ポートフォリオ", "タイプ", "月平均_広告費", "月平均_広告経由売上", "月平均_ROAS"]]
        .copy()
        .sort_values("月平均_広告費", ascending=False)
    )

    # -------- (2) Map auto campaigns to ASIN overview & share of total sales --------
    # Use simple keyword extraction + substring match against 親ASIN名.
    asin_names = asin[["親ASIN", "親ASIN名"]].copy()
    asin_names["norm_name"] = asin_names["親ASIN名"].astype(str).map(_normalize_text)

    auto_map_rows = []
    for camp in auto_summary["キャンペーン"].astype(str).tolist():
        kw = _extract_campaign_keyword(camp)
        n_kw = _normalize_text(kw)
        candidates = asin_names[asin_names["norm_name"].str.contains(n_kw, na=False)]
        chosen = None
        if len(candidates) == 1:
            chosen = candidates.iloc[0]
        elif len(candidates) > 1:
            # pick the shortest name (usually closest match)
            chosen = candidates.iloc[candidates["norm_name"].str.len().argmin()]
        else:
            # fallback: try partial (first 6 chars) if kw is long enough
            if len(n_kw) >= 6:
                part = n_kw[:6]
                candidates2 = asin_names[asin_names["norm_name"].str.contains(part, na=False)]
                if len(candidates2) >= 1:
                    chosen = candidates2.iloc[0]
        auto_map_rows.append(
            {
                "キャンペーン": camp,
                "keyword": kw,
                "親ASIN": None if chosen is None else chosen["親ASIN"],
                "親ASIN名": None if chosen is None else chosen["親ASIN名"],
            }
        )

    auto_map = pd.DataFrame(auto_map_rows)

    # Sales columns in asin overview
    sales_cols = [c for c in asin.columns if str(c).startswith("売上_") and re.search(r"売上_\d+月$", str(c))]
    sales_months2 = sorted({re.search(r"(\d+月)$", c).group(1) for c in sales_cols}, key=_month_sort_key) if sales_cols else []
    # Use overlap months if possible (otherwise use whatever is there)
    months_sales = [m for m in months if m in sales_months2] or sales_months2[-2:]
    months_sales = [m for m in months_sales if m]  # drop empties

    # compute total sales for those months
    totals = {}
    if months_sales:
        # Identify total row if present
        total_row = asin[asin["GL"].astype(str) == "合計"]
        for m in months_sales:
            col = f"売上_{m}"
            if col not in asin.columns:
                continue
            if len(total_row) == 1:
                total_sales = float(_to_number(total_row.iloc[0][col]))
            else:
                total_sales = float(_to_number(asin[col]).fillna(0).sum())
            totals[m] = total_sales

    # Sum sales of matched 親ASINs
    share_rows = []
    matched_asins = set(auto_map["親ASIN"].dropna().astype(str).tolist())
    for m, total_sales in totals.items():
        col = f"売上_{m}"
        sub = asin[asin["親ASIN"].astype(str).isin(matched_asins)].copy()
        sub_sales = float(_to_number(sub[col]).fillna(0).sum()) if col in asin.columns else 0.0
        share = _safe_div(sub_sales, total_sales)
        share_rows.append({"month": m, "auto_parent_asin_sales": sub_sales, "total_sales": total_sales, "share": share})
    share_df = pd.DataFrame(share_rows)

    # -------- (3) From bulk: ad-attributed sales / ROAS / SP competitor product targeting sales / total impressions --------
    bulk_sp = _bulk_campaign_totals(ads_xlsx, "スポンサープロダクト広告キャンペーン")
    bulk_sb = _bulk_campaign_totals(ads_xlsx, "スポンサーブランド広告キャンペーン")
    bulk_sd = _bulk_campaign_totals(ads_xlsx, "スポンサーディスプレイ広告キャンペーン")
    bulk_all = BulkTotals(
        impressions=bulk_sp.impressions + bulk_sb.impressions + bulk_sd.impressions,
        clicks=bulk_sp.clicks + bulk_sb.clicks + bulk_sd.clicks,
        spend=bulk_sp.spend + bulk_sb.spend + bulk_sd.spend,
        sales=bulk_sp.sales + bulk_sb.sales + bulk_sd.sales,
    )
    comp_sales, comp_spend, comp_roas = bulk_sp_competitor_product_targeting_sales(ads_xlsx)

    # -------- (4) Total GV from asin overview --------
    gv_cols = [c for c in asin.columns if str(c).startswith("GV_") and re.search(r"GV_\d+月$", str(c))]
    gv_months = sorted({re.search(r"(\d+月)$", c).group(1) for c in gv_cols}, key=_month_sort_key) if gv_cols else []
    gv_totals = []
    if gv_months:
        total_row = asin[asin["GL"].astype(str) == "合計"]
        for m in gv_months[-2:]:
            col = f"GV_{m}"
            if col not in asin.columns:
                continue
            if len(total_row) == 1:
                total_gv = float(_to_number(total_row.iloc[0][col]))
            else:
                total_gv = float(_to_number(asin[col]).fillna(0).sum())
            gv_totals.append({"month": m, "gv": total_gv})
    gv_df = pd.DataFrame(gv_totals)

    # -------- Markdown output --------
    lines: list[str] = []
    lines.append("## 결과 요약")
    lines.append("")
    if months:
        lines.append(f"- **(1) 오토(オート) 캠페인 월평균**: past_campaigns 기준 `{', '.join(months)}` 컬럼으로 계산")
    else:
        lines.append("- **(1) 오토(オート) 캠페인 월평균**: past_campaigns에서 월 컬럼을 찾지 못해 계산 불가")
    lines.append(f"- **(3) 벌크 총 임프레션(캠페인 합)**: {_fmt_money(bulk_all.impressions)}")
    lines.append(f"- **(3) 벌크 광고 경유 매출(캠페인 합)**: {_fmt_money(bulk_all.sales)} / **ROAS**: {_fmt_ratio(bulk_all.roas)}")
    lines.append(f"- **(3) SP 타사(자사 ASIN 제외) 상품타겟 매출(상품ターゲティング 합)**: {_fmt_money(comp_sales)} / **ROAS**: {_fmt_ratio(comp_roas)}")
    if len(gv_df):
        for _, r in gv_df.iterrows():
            lines.append(f"- **(4) 총 GV ({r['month']})**: {_fmt_money(float(r['gv']))}")
    lines.append("")

    lines.append("## (1) 親ASIN 단위 오토(オート) 광고: 월 평균 광고비/광고경유매상/ROAS")
    lines.append("")
    if len(auto_summary) == 0:
        lines.append("- 오토(オート)로 판별되는 캠페인이 없습니다.")
    else:
        # show top 30 to keep report readable
        show = auto_summary.head(30).copy()
        lines.append("| 캠페인 | 포트폴리오 | 타입 | 월평균 광고비 | 월평균 광고경유매상 | 월평균 ROAS |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for _, r in show.iterrows():
            lines.append(
                f"| {r['キャンペーン']} | {r['ポートフォリオ'] if not pd.isna(r['ポートフォリオ']) else '-'} | {r['タイプ'] if not pd.isna(r['タイプ']) else '-'}"
                f" | {_fmt_money(float(r['月平均_広告費']))} | {_fmt_money(float(r['月平均_広告経由売上']))} | {_fmt_ratio(r['月平均_ROAS'])} |"
            )
        if len(auto_summary) > len(show):
            lines.append("")
            lines.append(f"- (표는 상위 {len(show)}개만 표시, 전체 오토 캠페인 수: {len(auto_summary)})")

    lines.append("")
    lines.append("## (2) 오토 캠페인(메인 ASIN/親ASIN 추정) 매출 비중")
    lines.append("")
    lines.append("- 매핑 방식: `キャンペーン名`에서 `オート`/접두어/포트폴리오 꼬리표를 제거한 키워드로, `ASIN의 전반적인 정보`의 `親ASIN名`에 **부분일치** 검색했습니다.")
    lines.append("")
    matched = int(auto_map["親ASIN"].notna().sum())
    lines.append(f"- **매핑 성공**: {matched} / {len(auto_map)}")
    if len(share_df):
        lines.append("")
        lines.append("| 월 | 오토 親ASIN 매출 합 | 전체 매출 | 비중 |")
        lines.append("|---:|---:|---:|---:|")
        for _, r in share_df.iterrows():
            share_pct = None if r["share"] is None else float(r["share"]) * 100
            lines.append(
                f"| {r['month']} | {_fmt_money(float(r['auto_parent_asin_sales']))} | {_fmt_money(float(r['total_sales']))} | {_fmt_ratio(share_pct, 2)}% |"
            )
    else:
        lines.append("")
        lines.append("- 매출 비중 계산을 위한 월별 `売上_x月` 컬럼을 찾지 못했습니다.")

    lines.append("")
    lines.append("## (3) 광고 벌크 자료: 광고경유매출/ROAS/타사상품경유매출/총 임프레션")
    lines.append("")
    lines.append("| 구분 | 임프레션 | 클릭 | 지출 | 매출 | ROAS |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for name, t in [("SP(캠페인)", bulk_sp), ("SB(캠페인)", bulk_sb), ("SD(캠페인)", bulk_sd), ("전체(캠페인 합)", bulk_all)]:
        lines.append(
            f"| {name} | {_fmt_money(t.impressions)} | {_fmt_money(t.clicks)} | {_fmt_money(t.spend)} | {_fmt_money(t.sales)} | {_fmt_ratio(t.roas)} |"
        )
    lines.append("")
    lines.append("### SP 타사 상품(자사 ASIN 제외) 타겟팅 매출")
    lines.append("")
    lines.append("- 기준: `スポンサープロダクト広告キャンペーン` 시트의 `エンティティ=商品ターゲティング` 행 중, 타겟 ASIN이 `プロダクト広告`의 `ASIN（情報提供のみ）`(자사 광고 ASIN 목록)에 **포함되지 않는 것**을 타사로 간주")
    lines.append(f"- **매출**: {_fmt_money(comp_sales)} / **지출**: {_fmt_money(comp_spend)} / **ROAS**: {_fmt_ratio(comp_roas)}")

    lines.append("")
    lines.append("## (4) ASIN 전반 정보: 총 GV")
    lines.append("")
    if len(gv_df) == 0:
        lines.append("- GV 컬럼을 찾지 못했습니다.")
    else:
        lines.append("| 월 | 총 GV |")
        lines.append("|---:|---:|")
        for _, r in gv_df.iterrows():
            lines.append(f"| {r['month']} | {_fmt_money(float(r['gv']))} |")

    lines.append("")
    lines.append("## 참고/주의")
    lines.append("")
    lines.append("- 본 리포트는 제공된 파일 내부 컬럼을 기준으로 계산했습니다. 파일에 포함된 월(예: `past_campaigns`는 10월 중심, `asin_overview`는 12/11월)이 서로 다를 수 있어, **요청하신 10/11월과 파일의 월 표기가 불일치**할 경우 결과 표의 월을 우선으로 해석해 주세요.")
    lines.append("- ROAS는 기본적으로 `매출 / 지출`로 재계산(분모 0은 '-') 했습니다.")

    return "\n".join(lines) + "\n"


def main() -> None:
    report = generate_report()
    out = Path(__file__).resolve().parents[1] / "report.md"
    out.write_text(report, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

