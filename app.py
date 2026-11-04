import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.data_provider import TwelveDataError, TwelveDataProvider
from sp500_strategy_simulator.performance import build_equity_curve, calculate_metrics
from sp500_strategy_simulator.simulation import simulate, Trade
from sp500_strategy_simulator.congress_data import (
    fetch_congress_trades,
    fetch_congress_transactions,
    get_top_politicians,
)

st.set_page_config(page_title="S&P 500 Strategy Simulator", layout="wide", page_icon="📈")

# Helper pour compatibilité Streamlit selon les versions
def _dataframe_compat(df):
    try:
        st.dataframe(df, width="stretch")
    except TypeError:
        st.dataframe(df, use_container_width=True)

def _line_chart_compat(data):
    try:
        st.line_chart(data, width="stretch")
    except TypeError:
        st.line_chart(data, use_container_width=True)

# --- Simulation spécifique au Congress Tracker ---
def simulate_congress_tracker(
    trades_congress,
    bars_by_symbol,
    holding_days: int,
    initial_capital: float,
    fixed_fee: float,
    start_date: date,
    end_date: date,
):
    """
    Simule une stratégie de copie des élus US :
    - On achète à la date de divulgation (disclosure_date) ou premier jour de cotation suivant
    - On revend après `holding_days` jours calendaires (ou dernier cours disponible)
    - Le capital est réparti équitablement sur les positions
    """
    sim_trades = []
    cash = initial_capital
    active_positions = {}  # ticker -> {'shares': float, 'buy_date': date, 'buy_price': float}

    # Récupérer toutes les dates de bourse disponibles ordonnées
    all_dates = sorted({b.session_date for bars in bars_by_symbol.values() for b in bars})
    date_to_bars = {}
    for sym, bars in bars_by_symbol.items():
        for b in bars:
            if b.session_date not in date_to_bars:
                date_to_bars[b.session_date] = {}
            date_to_bars[b.session_date][sym] = b

    # Indexer les achats du congrès par date de divulgation
    purchases_by_date = {}
    for t in trades_congress:
        if start_date <= t.disclosure_date <= end_date:
            purchases_by_date.setdefault(t.disclosure_date, []).append(t.ticker)

    for current_date in all_dates:
        if current_date < start_date or current_date > end_date:
            continue

        daily_bars = date_to_bars.get(current_date, {})

        # 1. Vérifier si des positions doivent être vendues (délai holding_days dépassé)
        tickers_to_close = []
        for ticker, pos in list(active_positions.items()):
            days_held = (current_date - pos["buy_date"]).days
            if days_held >= holding_days and ticker in daily_bars:
                bar = daily_bars[ticker]
                sell_price = bar.open_price if bar.open_price > 0 else bar.close_price
                proceeds = pos["shares"] * sell_price - fixed_fee
                cash += proceeds
                sim_trades.append(
                    Trade(
                        session_date=current_date,
                        symbol=ticker,
                        side="SELL",
                        quantity=pos["shares"],
                        price=sell_price,
                        commission=fixed_fee,
                    )
                )
                tickers_to_close.append(ticker)

        for ticker in tickers_to_close:
            del active_positions[ticker]

        # 2. Exécuter les nouveaux achats prévus aujourd'hui
        new_targets = purchases_by_date.get(current_date, [])
        for ticker in new_targets:
            if ticker in daily_bars and ticker not in active_positions:
                bar = daily_bars[ticker]
                buy_price = bar.open_price if bar.open_price > 0 else bar.close_price
                if buy_price <= 0:
                    continue

                # Allocation : fraction du cash disponible
                target_allocation = max(500.0, cash / max(1, (4 - len(active_positions))))
                budget = min(cash - fixed_fee, target_allocation)

                if budget > buy_price:
                    shares = (budget - fixed_fee) / buy_price
                    cash -= (shares * buy_price + fixed_fee)
                    active_positions[ticker] = {
                        "shares": shares,
                        "buy_date": current_date,
                        "buy_price": buy_price,
                    }
                    sim_trades.append(
                        Trade(
                            session_date=current_date,
                            symbol=ticker,
                            side="BUY",
                            quantity=shares,
                            price=buy_price,
                            commission=fixed_fee,
                        )
                    )

    # Fermer les positions ouvertes à la toute fin pour le calcul final
    last_date = all_dates[-1] if all_dates else end_date
    daily_bars = date_to_bars.get(last_date, {})
    for ticker, pos in list(active_positions.items()):
        bar = daily_bars.get(ticker)
        if bar:
            sell_price = bar.close_price
            proceeds = pos["shares"] * sell_price - fixed_fee
            cash += proceeds
            sim_trades.append(
                Trade(
                    session_date=last_date,
                    symbol=ticker,
                    side="SELL",
                    quantity=pos["shares"],
                    price=sell_price,
                    commission=fixed_fee,
                )
            )

    return sim_trades

# --- Barre latérale : Sélection de Stratégie & Paramètres ---
with st.sidebar:
    st.header("🎯 Stratégie")
    selected_strategy = st.selectbox(
        "Choisir la stratégie de trading",
        options=[
            "Momentum (Close-to-Next-Open)",
            "🏛️ Congress Tracker (Copie des élus US)",
            "Buy & Hold (Equi-pondéré) [À venir]",
            "Croisement Moyennes Mobiles (SMA) [À venir]",
        ],
        index=0,
        help="Sélectionnez la logique d'investissement à tester",
    )

    st.markdown("---")
    st.header("⚙️ Paramètres généraux")

    api_key_env = os.getenv("TWELVE_DATA_API_KEY", "")
    api_key_input = st.text_input(
        "Clé API Twelve Data",
        value=api_key_env,
        type="password",
        help="Détectée automatiquement depuis .env si présent",
    )

    col_d1, col_d2 = st.columns(2)
    today = date.today()
    default_start = today - timedelta(days=365 * 2)
    start_date = col_d1.date_input("Date de début", value=default_start)
    end_date = col_d2.date_input("Date de fin", value=today)

    capital = st.number_input("Capital initial ($)", min_value=100.0, value=10000.0, step=1000.0)

    # Paramètres spécifiques selon la stratégie
    if selected_strategy == "Momentum (Close-to-Next-Open)":
        st.subheader("Paramètres Momentum")
        top_20_sp500 = (
            "AAPL, MSFT, NVDA, AMZN, GOOGL, META, BRK.B, LLY, AVGO, TSLA, "
            "JPM, UNH, V, XOM, MA, JNJ, COST, HD, PG, ABBV"
        )
        symbols_input = st.text_area(
            "Univers d'actions (séparées par virgules)",
            value=top_20_sp500,
            help="Sélection d'actions du S&P 500 à analyser",
            height=90,
        )
        assets = st.number_input("Nombre d'actifs sélectionnés", min_value=1, max_value=50, value=5)
        lookback = st.number_input("Fenêtre Lookback (jours)", min_value=10, value=252)
        skip = st.number_input("Fenêtre Skip (jours)", min_value=0, value=21)

    elif selected_strategy == "🏛️ Congress Tracker (Copie des élus US)":
        st.subheader("Paramètres Congress Tracker")
        politician_choice = st.selectbox(
            "Membre du Congrès à copier",
            options=get_top_politicians(),
            index=0,
            help="Sélectionnez un membre ou suivez l'ensemble des transactions publiées",
        )
        holding_days = st.slider(
            "Durée de détention de chaque position (jours)",
            min_value=15,
            max_value=365,
            value=90,
            step=15,
            help="Combien de jours après la déclaration officielle l'action est conservée",
        )
        st.caption("ℹ️ *Achat exécuté à la date de divulgation publique (Disclosure Date) pour respecter le délai légal du STOCK Act.*")
        symbols_input = ""
        assets = 5
        lookback = 252
        skip = 21

    else:
        st.info("Cette stratégie est en cours d'intégration.")
        symbols_input = ""
        assets = 5
        lookback = 252
        skip = 21

    st.subheader("Frais & Fiscalité")
    col_frais1, col_frais2 = st.columns(2)
    fixed_fee = col_frais1.number_input("Frais fixes / ordre ($)", min_value=0.0, value=1.0, step=0.5)
    tax_percent = col_frais2.number_input("Flat Tax / Impôt (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0)

    try:
        run_btn = st.button("🚀 Lancer la simulation", type="primary", width="stretch")
    except TypeError:
        run_btn = st.button("🚀 Lancer la simulation", type="primary", use_container_width=True)

st.title(f"📈 {selected_strategy}")

# --- Aperçu en direct des déclarations pour Congress Tracker ---
if selected_strategy == "🏛️ Congress Tracker (Copie des élus US)":
    st.markdown("### 🏛️ Flux des déclarations STOCK Act")
    st.write("Ce module récupère les déclarations officielles (PTR) déposées par les membres du Congrès américain.")
    pol_filter = None if politician_choice == "Tous les membres" else politician_choice
    df_congress = fetch_congress_transactions(politician=pol_filter)
    if not df_congress.empty:
        _dataframe_compat(
            df_congress.head(50)[["disclosure_date", "transaction_date", "representative", "ticker", "type", "amount"]]
        )
    else:
        st.info("Aucune transaction trouvée.")

# --- Exécution ---
if run_btn:
    if "[À venir]" in selected_strategy:
        st.warning(f"La stratégie '{selected_strategy}' n'est pas encore implémentée.")
        st.stop()

    api_key = api_key_input.strip()
    if not api_key:
        st.error("Veuillez renseigner votre clé API Twelve Data.")
        st.stop()

    if start_date >= end_date:
        st.error("La date de début doit précéder la date de fin.")
        st.stop()

    provider = TwelveDataProvider(api_key=api_key)

    if selected_strategy == "🏛️ Congress Tracker (Copie des élus US)":
        pol_filter = None if politician_choice == "Tous les membres" else politician_choice
        trades_congress = fetch_congress_trades(
            min_disclosure_date=start_date,
            max_disclosure_date=end_date,
            politician_filter=pol_filter,
            only_purchases=True,
        )

        tickers_to_fetch = list(dict.fromkeys(t.ticker for t in trades_congress))

        if not tickers_to_fetch:
            st.warning("Aucune déclaration d'achat trouvée pour cette période et ce membre.")
            st.stop()

        with st.spinner(f"Récupération des cours boursiers pour les {len(tickers_to_fetch)} actions ciblées par le Congrès..."):
            try:
                bars_by_symbol = provider.fetch_daily_bars(
                    symbols=tickers_to_fetch,
                    start_date=start_date - timedelta(days=10),
                    end_date=end_date + timedelta(days=holding_days + 10),
                )
                trades = simulate_congress_tracker(
                    trades_congress=trades_congress,
                    bars_by_symbol=bars_by_symbol,
                    holding_days=holding_days,
                    initial_capital=capital,
                    fixed_fee=fixed_fee,
                    start_date=start_date,
                    end_date=end_date,
                )
                full_curve = build_equity_curve(bars_by_symbol, trades, capital)
                curve = [pt for pt in full_curve if start_date <= pt.session_date <= end_date]
                if not curve:
                    curve = full_curve

                anchor_value = capital
                metrics = calculate_metrics(curve, anchor_value)
            except (TwelveDataError, ValueError) as exc:
                st.error(f"Erreur durant la simulation Congress : {exc}")
                st.stop()

    elif selected_strategy == "Momentum (Close-to-Next-Open)":
        symbols = list(dict.fromkeys(s.strip().upper() for s in symbols_input.split(",") if s.strip()))
        if not symbols:
            st.error("Veuillez renseigner au moins un ticker valide.")
            st.stop()

        with st.spinner(f"Récupération des données pour {len(symbols)} actifs et calcul du backtest..."):
            try:
                config = StrategyConfig(
                    initial_capital=capital,
                    n_assets=assets,
                    momentum_lookback_days=lookback,
                    momentum_skip_days=skip,
                    commission_rate=0.0,
                    fixed_commission=fixed_fee,
                    tax_rate=tax_percent / 100.0,
                    start_date=start_date,
                    end_date=end_date,
                )

                history_start = start_date - timedelta(days=int((lookback + skip) * 1.5) + 30)
                bars_by_symbol = provider.fetch_daily_bars(
                    symbols=symbols,
                    start_date=history_start,
                    end_date=end_date,
                )

                trades = simulate(bars_by_symbol, config)
                full_curve = build_equity_curve(bars_by_symbol, trades, config.initial_capital)

                start_index = next(
                    (i for i, pt in enumerate(full_curve) if pt.session_date >= start_date),
                    None,
                )

                if start_index is None:
                    st.warning("Aucune donnée disponible sur la période sélectionnée.")
                    st.stop()

                curve = [pt for pt in full_curve[start_index:] if pt.session_date <= end_date]
                anchor_value = full_curve[start_index - 1].value if start_index > 0 else config.initial_capital
                metrics = calculate_metrics(curve, anchor_value)

            except (TwelveDataError, ValueError) as exc:
                st.error(f"Erreur durant la simulation : {exc}")
                st.stop()

    # --- Métriques & Résultats communs ---
    final_val_brut = curve[-1].value if curve else capital
    gain_brut = final_val_brut - anchor_value
    tax = max(0.0, gain_brut * (tax_percent / 100.0)) if gain_brut > 0 else 0.0
    final_val_net = final_val_brut - tax
    total_commissions = sum(t.commission for t in trades)

    st.subheader("📊 Résultats de la stratégie")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    kpi1.metric(
        "Valeur finale Nette",
        f"${final_val_net:,.2f}",
        f"Brut: ${final_val_brut:,.2f} | Impôt ({tax_percent:.0f}%): -${tax:,.2f}",
    )
    kpi2.metric("Rendement Annuel (Brut)", f"{metrics.annualized_return:.2%}")
    kpi3.metric("Volatilité Annuelle", f"{metrics.annualized_volatility:.2%}")
    kpi4.metric("Ratio de Sharpe", f"{metrics.sharpe_ratio:.2f}")
    kpi5.metric("Max Drawdown", f"{metrics.max_drawdown:.2%}")

    st.info(
        f"💳 **Frais totaux de courtage :** ${total_commissions:,.2f} "
        f"({len(trades)} ordres exécutés à ${fixed_fee:.2f}/ordre). "
        f"🏛️ **Impôt prélevé sur les gains :** ${tax:,.2f} ({tax_percent:.0f}%)."
    )

    df_curve = pd.DataFrame([{"Date": pt.session_date, "Portfolio Value": pt.value} for pt in curve])
    df_curve.set_index("Date", inplace=True)
    _line_chart_compat(df_curve)

    with st.expander(f"📝 Historique des transactions ({len(trades)} trades)"):
        if trades:
            df_trades = pd.DataFrame([
                {
                    "Date": t.session_date,
                    "Symbole": t.symbol,
                    "Type": "ACHAT" if t.side == "BUY" else "VENTE",
                    "Quantité": f"{t.quantity:.4f}",
                    "Prix": f"${t.price:.2f}",
                    "Frais": f"${t.commission:.2f}",
                }
                for t in trades
            ])
            _dataframe_compat(df_trades)
        else:
            st.info("Aucune transaction exécutée sur la période.")
