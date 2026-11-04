import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional
import urllib.request

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
    Télécharge et filtre les transactions boursières des membres de la Chambre des représentants
    issues de House Stock Watcher (données publiques STOCK Act).
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

        # Filtrer les tickers invalides ou non actions (ex: '--', N/A, etc.)
        if not ticker or ticker in {"--", "N/A", "NONE"} or "$" in ticker:
            continue

        raw_type = str(item.get("type", "")).lower()
        if only_purchases and "purchase" not in raw_type:
            continue

        politician = item.get("representative", "").strip()
        if politician_filter and politician_filter.lower() not in politician.lower():
            continue

        # Dates : disclosure_date (date publique légale) et transaction_date (date d'ordre réelle)
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

    # Trier par date de divulgation croissante (ordre chronologique de copie)
    trades.sort(key=lambda t: t.disclosure_date)
    return trades
