from __future__ import annotations

"""Versioned issuer-to-sector-ETF taxonomy for the US signal adapter.

Nasdaq's broad ``sector`` labels are useful display metadata, but they are not
the same taxonomy as the eleven Select Sector SPDR proxies used by the signal.
The signal therefore keys its proxy classification by the SEC issuer CIK and
fails closed for an issuer that has not yet been reviewed for this version.
"""

from typing import Final


US_SECTOR_ETF_CLASSIFICATION_VERSION: Final = "us-sector-etf-cik-v5"
US_SECTOR_ETFS: Final[frozenset[str]] = frozenset(
    {"XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"}
)


def _cik_map(etf: str, values: str) -> dict[str, str]:
    return {cik: etf for cik in values.split()}


# Reviewed against the GICS sector represented by the corresponding State
# Street Select Sector ETF. Foreign issuers use the equivalent sector proxy.
# An issuer absent from this immutable allowlist is deliberately unclassified;
# it must not inherit Nasdaq's display label or a broad-market fallback.
US_SECTOR_ETF_BY_CIK: Final[dict[str, str]] = {
    **_cik_map(
        "XLK",
        """
        0001045810 0000320193 0000789019 0001046179 0001730168 0002120882
        0000723125 0000002488 0000937966 0000050863 0001341439 0000858877
        0001321655 0000707549 0000006951 0001571996 0001973239 0001327567
        0001000184 0002023554 0001596532 0000319201 0000097476 0000051143
        0001535527 0001108524 0001137789 0001835632 0000804328 0000006281
        0000106040 0001594805 0000820313
        """,
    ),
    **_cik_map(
        "XLC",
        """
        0001652044 0001326801 0001065280 0000732712 0001283699 0001744489
        0000732717 0001166691 0001181412
        """,
    ),
    **_cik_map(
        "XLY",
        """
        0001018724 0001318605 0000354950 0001577552 0001094517 0000063908
        """,
    ),
    **_cik_map(
        "XLP",
        """
        0000104169 0000909832 0000021344 0000080424 0001413329 0000077476
        """,
    ),
    **_cik_map(
        "XLF",
        """
        0001067983 0000019617 0001403161 0001141391 0000070858 0001089113
        0000895421 0000886982 0001000275 0000067088 0000072971 0000831001
        0000004962 0000891478 0000947263 0000316709 0001610520 0002012383
        0000842180 0001022837
        """,
    ),
    **_cik_map(
        "XLV",
        """
        0000059478 0000200406 0001551152 0000310158 0000731766 0001114448
        0000901832 0000097745 0000318154 0000353278 0000001800 0000882095
        0000078003
        """,
    ),
    **_cik_map(
        "XLE",
        """
        0002115436 0000093410 0001306965 0000879764 0001163165
        """,
    ),
    **_cik_map(
        "XLI",
        """
        0000018230 0000040545 0000101829 0001996810 0000315189 0000100885
        0000012927 0001551182
        """,
    ),
    **_cik_map("XLB", "0001707925 0000811809 0001001838"),
    **_cik_map("XLU", "0000753308"),
    **_cik_map("XLRE", "0000766704"),
}


def normalize_sec_cik(value: object) -> str:
    text = str(value or "").strip()
    return text.zfill(10) if text.isdigit() else ""


def sector_etf_for_cik(value: object) -> str:
    """Return the reviewed sector proxy, or an empty string to fail closed."""

    return US_SECTOR_ETF_BY_CIK.get(normalize_sec_cik(value), "")
