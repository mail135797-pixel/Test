#!/usr/bin/env python3
import html as html_lib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Tuple

import requests
from openpyxl import Workbook


ASIN_INPUT = """
B0BSXGSTNY,B00IR4ZA7E,B0B24LGZTS,B0F79QSV6P,B09D3KCN3G,B01KXDQJCQ,B00UL6L2WI,B01J1FODT8,B0090VFMHG,B0DG8LMFMC,B0FDF7LRDP,B0B2W51T38,B0B2W6RC63,B0CRT7KCVM,B000V2F37W,B0BB2MJDR5,B01AULWXJO,B00EZL8SI6,B0DZ66L1QX,B0CGRPHXT2,B0CZ92T3Y8,B086MPLZVK,B0FRG3NSPM,B0CVS3GZC6,B0FL244B66,B0DT59244M,B0D5CC65PJ,B00IR4Y458,B0FQBZNGZP,B0868VLJ7K,B08H5KJ253,B0FL24YXBH,B09L421QHH,B000FQUDBK,B008MH8UIC,B0026RAVNG,B07MC799BM,B0CWZHBGLQ,B08NKJ4MDV,B08WQ3BCW4,B002TV3HGC,B09D3K7P7C,B00EPYLGMS,B005FO82BU,B08H5N4558,B0090VFFMI,B00MT6TAD6,B00EP7XZ24,B08WQ8FVVK,B0792TNPTK,B002P6Y0HG,B0DHCXZ41X,B0DLL1SCXD,B0D2ZWPR3X,B0D9LLM6FX,B0CVN9H69S,B099NQ5K8V,B0FL24VHKH,B073XMN2TR,B09SNV919Z

B0DBLL61WS,B0B24LGZTS,B014KNY5QM,B0DP9W53QB,B07YVMJ9V2,B0DC5YCHBC,B06XDJMCM2,B08NKJ4MDD,B0834CVMX3,B00E575QO4,B00IR4ZA7E,B0C65NFHLH,B0BJ2C93N8,B0FDFDJ38J,B0FNRCSC1S,B0CD2S6GYP,B001F7BE1Q,B07NV489RC,B0FL818JVG,B0CZ92T3Y8,B0CP5YPMY4,B0B2W4W7Q8,B08H5KT1GJ,B0FL26WKXV,B001PLXN8Y,B098J7X6DR,B0BV698HYS,B08R45XWRL,B075DXWSR7,B08H5LJFC5,B08KVNTP2V,B00KMTQK4O,B078Y5STKD,B00E5765W6,B07XD9LGSP,B0BT4DPCNH,B07MR8W166,B0026R4WSG,B00E575NQK,B0CHLTY67B,B09F394SB9,B0CD76TPJC,B0DG8NDRJ7,B07LB79RZZ,B0CGTFKVNC,B08H5NHL3Q,B09SP8T4K3,B075XLRRW7,B0CWZS3KC3,B08KVSF8Z4,B0DBSKSFY7,B0CDBXZV1M,B078Y4JY4F,B07LB16JC2,B0DPQ8WC9J,B005C0VYUI,B0D9W62Y15,B0DPFXWZWV,B083MCJ94W,B0CD74TJDN

B0DBLL61WS,B014KNYD0A,B0DP9W53QB,B0BSXGSTNY,B0DNZ1VBC4,B08P6Y6Z63,B0GD93SHTG,B0C1JT8QCK,B09MLWMKL6,B07D2JWGQM,B00IR4ZA7E,B08MT67PLB,B0FZFNQQQJ,B0GCK6DJZ1,B07TZS7P8Z,B0CXPL8VFW,B00JKOGP0G,B0BQ1KPJ78,B0BJ2C8VTQ,B0DFH3KB59,B0DBGYWSMJ,B014KNY5SU,B0DZ271VXY,B0CPRQ8W9W,B014KNY81E,B0FNZZS7Z3,B07BFGLY8X,B01CG1TZ2Y,B0834CWSBW,B000FQUD9M,B07J2XXFQ1,B08M9KJXCT,B07VHBNK5B,B08DHL74BX,B01IQHFZEE,B08P6FCBBP,B07BFFR5NZ,B07C53BC1J,B09RG5KRF9,B00N2E3D82,B0834CCX2P,B0B8YWLG5V,B004WMFHXC,B0FP15PXZ7,B0088B7YLQ,B00IOAP5IA,B005FO86HK,B0F4Q8Y7Q6,B08455RZ2Z,B0DBLHP4TZ,B0D9LMN8R9,B09QKG53PL,B07YDWH1SV,B00MWKGBH2,B0FP1BRSGM,B0BJJZ8H4Z,B013D3W3GY
""".strip()

MOBILE_URL = "https://www.amazon.co.jp/gp/aw/d/{}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def parse_asins(text: str) -> List[str]:
    seen = set()
    result = []
    for asin in re.findall(r"[A-Z0-9]{10}", text):
        if asin not in seen:
            seen.add(asin)
            result.append(asin)
    return result


def is_asin(token: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Z0-9]{10}", token)
        and re.search(r"[A-Z]", token)
        and re.search(r"[0-9]", token)
    )


def extract_variation_asins(html: str, main_asin: str) -> List[str]:
    pattern = r'dims-to-asin-list&quot;\}">(\{.*?\})</script>'
    matches = re.findall(pattern, html, re.S)
    asins: List[str] = []
    for match in matches:
        try:
            data = json.loads(html_lib.unescape(match))
        except json.JSONDecodeError:
            continue
        asins.extend([value for value in data.values() if is_asin(value)])

    if main_asin not in asins:
        asins.insert(0, main_asin)

    deduped: List[str] = []
    seen = set()
    for asin in asins:
        if asin not in seen:
            seen.add(asin)
            deduped.append(asin)
    return deduped


def extract_title(html: str) -> str:
    for pattern in [
        r'id="title"[^>]*>\s*(.*?)\s*<',
        r'id="productTitle"[^>]*>\s*(.*?)\s*<',
    ]:
        match = re.search(pattern, html, re.S)
        if match:
            return html_lib.unescape(match.group(1)).strip()

    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if match:
        return html_lib.unescape(match.group(1)).strip()

    return ""


class AmazonFetcher:
    def __init__(self, min_interval: float = 0.1, max_attempts: int = 2) -> None:
        self.session = requests.Session()
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self.last_request = 0.0

    def fetch(self, asin: str) -> str:
        url = MOBILE_URL.format(asin)
        last_text = ""
        for attempt in range(1, self.max_attempts + 1):
            self._wait()
            try:
                response = self.session.get(url, headers=HEADERS, timeout=20)
                self.last_request = time.time()
                text = response.text
                last_text = text
                if self._is_usable(text, response.status_code):
                    return text
            except requests.RequestException:
                pass
            time.sleep(0.2 * attempt)
        return last_text

    def _is_usable(self, html: str, status_code: int) -> bool:
        if status_code != 200:
            return False
        if len(html) < 20000:
            return False
        if "Service Unavailable" in html or "503" in html:
            return False
        return True

    def _wait(self) -> None:
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)


def write_excel(path: str, rows: Iterable[Tuple[str, str, str, str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ASIN Variations"
    sheet.append(["Main ASIN", "ASIN", "TITLE", "ASIN LINK"])
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)


def main() -> None:
    main_asins = parse_asins(ASIN_INPUT)
    title_cache: Dict[str, str] = {}
    variation_map: Dict[str, List[str]] = {}

    fetcher = AmazonFetcher()

    rows: List[Tuple[str, str, str, str]] = []
    for idx, main_asin in enumerate(main_asins, start=1):
        html = fetcher.fetch(main_asin)
        variation_asins = extract_variation_asins(html, main_asin)
        if not variation_asins:
            variation_asins = [main_asin]
        variation_map[main_asin] = variation_asins

        if main_asin not in title_cache:
            title_cache[main_asin] = extract_title(html) or "TITLE_NOT_FOUND"

        print(
            f"[{idx}/{len(main_asins)}] {main_asin} -> {len(variation_asins)} variations",
            flush=True,
        )

    all_variation_asins: List[str] = []
    seen_asins = set()
    for variation_asins in variation_map.values():
        for asin in variation_asins:
            if asin not in seen_asins:
                seen_asins.add(asin)
                all_variation_asins.append(asin)

    asins_to_fetch = [asin for asin in all_variation_asins if asin not in title_cache]

    thread_local = threading.local()

    def get_thread_fetcher() -> AmazonFetcher:
        if not hasattr(thread_local, "fetcher"):
            thread_local.fetcher = AmazonFetcher()
        return thread_local.fetcher

    def fetch_title_task(asin: str) -> Tuple[str, str]:
        local_fetcher = get_thread_fetcher()
        html = local_fetcher.fetch(asin)
        title = extract_title(html) or "TITLE_NOT_FOUND"
        return asin, title

    if asins_to_fetch:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(fetch_title_task, asin): asin for asin in asins_to_fetch}
            total = len(futures)
            completed = 0
            for future in as_completed(futures):
                asin, title = future.result()
                title_cache[asin] = title
                completed += 1
                if completed % 50 == 0 or completed == total:
                    print(f"[titles] {completed}/{total} fetched", flush=True)

    for main_asin in main_asins:
        for asin in variation_map.get(main_asin, [main_asin]):
            rows.append(
                (
                    main_asin,
                    asin,
                    title_cache.get(asin, "TITLE_NOT_FOUND"),
                    f"https://www.amazon.co.jp/dp/{asin}",
                )
            )

    all_path = "/workspace/asin_variations_all.xlsx"
    filtered_path = "/workspace/asin_variations_shiragazome.xlsx"

    write_excel(all_path, rows)

    filtered_rows = [row for row in rows if "白髪染め" in row[2]]
    write_excel(filtered_path, filtered_rows)

    print(f"Total rows: {len(rows)}")
    print(f"Filtered rows (白髪染め): {len(filtered_rows)}")
    print(f"Removed rows: {len(rows) - len(filtered_rows)}")


if __name__ == "__main__":
    main()
