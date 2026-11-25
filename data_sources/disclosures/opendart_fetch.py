"""키가 있을 때만 OpenDART 지분공시 API를 회사별로 이어받아 수집한다."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path.home() / "CODE/Coin_Trade/trading_data/external/disclosures/opendart"
ENDPOINTS = {"elestock": "https://opendart.fss.or.kr/api/elestock.json",
             "majorstock": "https://opendart.fss.or.kr/api/majorstock.json"}
DAILY_LIMIT = 20_000


class OpenDartFetcher:
    def __init__(self, api_key: str, output: Path = BASE, opener=None, sleeper=time.sleep):
        self._key = api_key
        self.output = output
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper
        self.state_path = output / "state.json"
        self.count_path = output / f"calls-{date.today().isoformat()}.json"
        self.state = self._read_json(self.state_path, {"done": []})
        self.daily_count = self._read_json(self.count_path, {"count": 0})["count"]

    @staticmethod
    def _read_json(path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default

    def _save(self):
        self.output.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        self.count_path.write_text(json.dumps({"count": self.daily_count}), encoding="utf-8")

    def fetch_one(self, endpoint: str, corp_code: str, retries: int = 4):
        if endpoint not in ENDPOINTS:
            raise ValueError(f"지원하지 않는 API: {endpoint}")
        key = f"{endpoint}:{corp_code}"
        if key in self.state["done"]:
            return "already_done"
        if self.daily_count >= DAILY_LIMIT:
            return "daily_limit"
        params = urllib.parse.urlencode({"crtfc_key": self._key, "corp_code": corp_code})
        url = f"{ENDPOINTS[endpoint]}?{params}"
        for attempt in range(retries):
            if self.daily_count >= DAILY_LIMIT:
                return "daily_limit"
            try:
                self.daily_count += 1
                self._save()
                with self.opener(url, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") not in {"000", "013"}:
                    self._save()
                    return "api_error"
                self.output.mkdir(parents=True, exist_ok=True)
                path = self.output / f"{endpoint}.jsonl"
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"corp_code": corp_code, "response": payload}, ensure_ascii=False) + "\n")
                self.state["done"].append(key)
                self._save()
                return "ok"
            except Exception:
                if attempt + 1 == retries:
                    return "retry_exhausted"
                self.sleeper(min(2 ** attempt, 30))
        return "retry_exhausted"

    def run(self, corp_codes, endpoints=tuple(ENDPOINTS)):
        counts = {"ok": 0, "already_done": 0, "daily_limit": 0, "api_error": 0, "retry_exhausted": 0}
        for endpoint in endpoints:
            for corp_code in corp_codes:
                status = self.fetch_one(endpoint, corp_code)
                counts[status] += 1
                if status == "daily_limit":
                    return counts
        return counts


def main():
    if not os.environ.get("OPENDART_API_KEY"):
        print("OPENDART_API_KEY 환경변수가 없습니다. 수집하지 않았습니다.")
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corp_codes", nargs="+", help="OpenDART 고유번호 8자리 목록")
    args = ap.parse_args()
    result = OpenDartFetcher(os.environ["OPENDART_API_KEY"]).run(args.corp_codes)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
