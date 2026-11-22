"""올웨더 연구 유니버스. 코드는 수집 결과를 확인해 후속 수정한다."""
from __future__ import annotations

import ast
from pathlib import Path


def _stock_constant(filename: str):
    """기존 상수 목록만 AST 리터럴로 읽어 무거운 검색 모듈 import를 피한다."""
    path = Path(__file__).with_name(filename)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "STOCK_UNIVERSE" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"{filename}에 STOCK_UNIVERSE 리터럴이 없습니다")


KR_STOCKS = _stock_constant("ema_cross_watchlist.py")
US_STOCKS = _stock_constant("us_swing_search.py")


def _rows(items, role, excd="KRX"):
    return [{"code": code, "name": name, "excd": excd, "role": role} for code, name in items]


KR_ETFS = (
    _rows([("069500", "KODEX 200"), ("229200", "KODEX 코스닥150"), ("133690", "TIGER 미국나스닥100"), ("360750", "TIGER 미국S&P500"), ("102110", "TIGER 200")], "index")
    + _rows([(c, n) for c, n in [("091160", "KODEX 반도체"), ("091170", "KODEX 은행"), ("091180", "KODEX 자동차"), ("117700", "KODEX 건설"), ("117680", "KODEX 철강"), ("117460", "KODEX 에너지화학"), ("102970", "KODEX 증권"), ("140700", "KODEX 보험"), ("140710", "KODEX 운송"), ("244580", "KODEX 바이오"), ("305720", "KODEX 2차전지산업"), ("139260", "TIGER 200 IT"), ("139230", "TIGER 200 중공업"), ("143860", "TIGER 헬스케어"), ("157490", "TIGER 소프트웨어"), ("228790", "TIGER 화장품"), ("449450", "PLUS K방산")]], "sector")
    + _rows([(c, n) for c, n in [("153130", "KODEX 단기채권"), ("114260", "KODEX 국고채3년"), ("148070", "KOSEF 국고채10년"), ("132030", "KODEX 골드선물(H)"), ("261240", "KODEX 미국달러선물")]], "defensive")
    + _rows([("114800", "KODEX 인버스")], "inverse")
)

US_ETFS = (
    _rows([(x, x) for x in ("SPY", "IWM")], "index", "AMS")
    + _rows([("QQQ", "QQQ")], "index", "NAS")
    + _rows([(x, x) for x in ("XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC", "MTUM", "USMV", "QUAL", "VLUE", "DBC", "EFA", "EEM", "VNQ", "XBI", "ITA", "KRE", "XHB", "XME", "SMH", "SOXX", "IBB")], "sector", "AMS")
    + _rows([(x, x) for x in ("BIL", "GLD", "TIP", "SHY", "UUP")], "defensive", "AMS")
    + _rows([(x, x) for x in ("IEF", "TLT")], "defensive", "NAS")
    + _rows([("SH", "ProShares Short S&P500")], "inverse", "AMS")
)

UNIVERSES = {"KR": KR_ETFS, "US": US_ETFS}

# Static current-sector assignments for the research stock baskets.  Codes are
# mapped only where the listed sector ETF is a reasonable explicit proxy.
KR_STOCK_SECTOR = {
    **dict.fromkeys(("005930","000660","009150","058470","042700","007660","022100","011790","402340"), "091160"),
    **dict.fromkeys(("005380","000270","012330","005490","003670","010130","373220","006400","051910"), "091180"),
    **dict.fromkeys(("105560","055550","086790","316140","024110","029780","006800","005940","001270","003540","001510"), "091170"),
    **dict.fromkeys(("000810","032830","003690","082640"), "140700"),
    **dict.fromkeys(("000720","298040"), "117700"),
    **dict.fromkeys(("096770","010950","011170"), "117460"),
    **dict.fromkeys(("011200",), "140710"),
    **dict.fromkeys(("068270","207940","214150","041830","214450"), "244580"),
    **dict.fromkeys(("035420","035720","018260","017670","030200","259960","036570","352820","307950"), "157490"),
    **dict.fromkeys(("090430","051900","161890"), "228790"),
    **dict.fromkeys(("047810",), "449450"),
    **dict.fromkeys(("097950","003230","005180"), "OTHER"),
}
KR_STOCK_SECTOR.update({"005490":"117680","010130":"117680","003670":"305720","006400":"305720","373220":"305720","051910":"117460","011790":"117460","402340":"OTHER","015760":"OTHER","034730":"OTHER","028260":"OTHER","323410":"091170"})
US_STOCK_SECTOR = {
    **dict.fromkeys(("AAPL","MSFT","GOOGL","META","ADBE","NFLX","INTC","AMD","QCOM","CSCO","NVDA","CIEN","LRCX","DELL","IBM","AMAT","GLW"), "XLK"),
    **dict.fromkeys(("JPM","BAC","KEY","RF","HBAN","NTRS","IBKR","APO","KKR","HOOD"), "XLF"),
    **dict.fromkeys(("XOM","KMI","GOLD"), "XLE"),
    **dict.fromkeys(("JNJ","UNH"), "XLV"),
    **dict.fromkeys(("GE","NUE","FIX","AAON"), "XLI"),
    **dict.fromkeys(("TSLA","AMZN","DIS","RCL","BKNG","CVNA"), "XLY"),
    **dict.fromkeys(("COST","PEP","PG","KO","CASY","WMT"), "XLP"),
    **dict.fromkeys(("T",), "XLC"),
    **dict.fromkeys(("HD",), "XLY"),
    **dict.fromkeys(("SAIA",), "XLI"),
    **dict.fromkeys(("FICO",), "XLK"),
    **dict.fromkeys(("NUE",), "XLB"),
    **dict.fromkeys(("V","MA"), "XLF"),
    **dict.fromkeys(("GRC",), "XLI"),
}
STOCK_SECTOR = {"KR": KR_STOCK_SECTOR, "US": US_STOCK_SECTOR}


def etfs(market: str) -> list[dict]:
    return [dict(row) for row in UNIVERSES[market.upper()]]


def stocks(market: str) -> list[dict]:
    market = market.upper()
    if market == "KR":
        return [{"code": c, "name": n, "excd": "KRX", "role": "stock"} for c, n in KR_STOCKS]
    if market == "US":
        return [{"code": c, "name": n, "excd": ex, "role": "stock"} for c, ex, n in US_STOCKS]
    raise ValueError(f"알 수 없는 시장: {market}")


def all_symbols(market: str) -> list[dict]:
    return etfs(market) + stocks(market)
