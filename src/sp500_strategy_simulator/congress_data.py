import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

HOUSE_STOCK_WATCHER_URL = (
    "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
)


@dataclass(frozen=True)
class CongressTrade:
    politician: str
    ticker: str
    transaction_date: date
    disclosure_date: date
    type: str  # "purchase", "sale_full", "sale_partial", etc.
    amount: str
    party: Optional[str] = None


def fetch_congress_trades(
    min_disclosure_date: Optional[date] = None,
    max_disclosure_date: Optional[date] = None,
    politician_filter: Optional[str] = None,
    only_purchases: bool = True,
) -> List[CongressTrade]:
    """
    Télécharge et filtre les transactions boursières des membres du Congrès (House Stock Watcher).
    """
    req = urllib.request.Request(
        HOUSE_STOCK_WATCHER_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error(f"Erreur lors de la récupération des trades du Congrès : {exc}")
        return []

    trades: List[CongressTrade] = []

    for item in data:
        raw_ticker = item.get("ticker", "")
        if not raw_ticker:
            continue
        ticker = str(raw_ticker).strip().upper()

        if not ticker or ticker in {"--", "N/A", "NONE"} or "$" in ticker:
            continue

        raw_type = str(item.get("type", "")).lower()
        if only_purchases and "purchase" not in raw_type:
            continue

        politician = item.get("representative", "").strip()
        if politician_filter and politician_filter.lower() not in politician.lower():
            continue

        raw_disc_date = item.get("disclosure_date") or item.get("disclosure_year")
        raw_tx_date = item.get("transaction_date")

        try:
            disc_date = datetime.strptime(str(raw_disc_date).strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        try:
            tx_date = datetime.strptime(str(raw_tx_date).strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            tx_date = disc_date

        if min_disclosure_date and disc_date < min_disclosure_date:
            continue
        if max_disclosure_date and disc_date > max_disclosure_date:
            continue

        amount = item.get("amount", "")
        party = item.get("party")

        trades.append(
            CongressTrade(
                politician=politician,
                ticker=ticker,
                transaction_date=tx_date,
                disclosure_date=disc_date,
                type=raw_type,
                amount=amount,
                party=party,
            )
        )

    trades.sort(key=lambda t: t.disclosure_date)
    return trades


def fetch_congress_transactions(
    politician: Optional[str] = None,
    only_purchases: bool = True,
) -> pd.DataFrame:
    """
    Retourne un DataFrame pandas contenant les transactions pour l'affichage et l'analyse.
    """
    trades = fetch_congress_trades(politician_filter=politician, only_purchases=only_purchases)
    if not trades:
        return pd.DataFrame(columns=["disclosure_date", "transaction_date", "representative", "ticker", "type", "amount", "party"])

    df = pd.DataFrame([
        {
            "disclosure_date": t.disclosure_date,
            "transaction_date": t.transaction_date,
            "representative": t.politician,
            "ticker": t.ticker,
            "type": t.type,
            "amount": t.amount,
            "party": t.party,
        }
        for t in trades
    ])
    return df.sort_values(by="disclosure_date", ascending=False).reset_index(drop=True)


def get_top_politicians() -> List[str]:
    """
    Retourne la liste des élus les plus suivis ou actifs.
    """
    return ["Tous les membres", "Nancy Pelosi", "Ro Khanna", "Michael McCaul", "Kevin Hern", "Dan Crenshaw"]
