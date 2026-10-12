"""Read-only, bounded KIS regular-session source diagnostic; no account APIs."""
import json
from app.config import get_settings
from app.collectors.briefing import KisRestBriefingProvider

provider = KisRestBriefingProvider(get_settings())
keys = ("stck_bsop_date", "stck_cntg_hour", "stck_oprc", "stck_hgpr", "stck_lwpr", "stck_prpr", "cntg_vol", "acml_vol", "acml_tr_pbmn")
for day in ("20260914", "20260930", "20261008", "20261012"):
    for cursor in ("153100", "153000", "090100"):
        payload = provider._get(
            "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice", "FHKST03010230",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930", "FID_INPUT_HOUR_1": cursor,
             "FID_INPUT_DATE_1": day, "FID_PW_DATA_INCU_YN": "Y", "FID_FAKE_TICK_INCU_YN": ""},
        )
        rows = [x for x in payload.get("output2", []) if x.get("stck_bsop_date") == day]
        selected = [x for x in rows if "151800" <= x.get("stck_cntg_hour", "") <= "153100" or "085800" <= x.get("stck_cntg_hour", "") <= "090100"]
        print(json.dumps({"date": day, "cursor": cursor, "count": len(rows), "first": rows[0].get("stck_cntg_hour") if rows else None, "last": rows[-1].get("stck_cntg_hour") if rows else None, "rows": [{k: x.get(k) for k in keys} for x in selected]}), flush=True)
