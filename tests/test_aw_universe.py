from app.aw_universe import etfs

def test_us_exchange_codes_for_nasdaq_listed_etfs():
    codes={x['code']:x['excd'] for x in etfs('US')}
    assert codes['QQQ']=='NAS' and codes['IEF']=='NAS' and codes['TLT']=='NAS'
    assert codes['SPY']=='AMS' and codes['IWM']=='AMS' and codes['BIL']=='AMS'
