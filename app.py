import os
from datetime import date, timedelta
from dotenv import load_dotenv

# Charger les variables du fichier .env
load_dotenv()

import pandas as pd
import streamlit as st
from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.data_provider import TwelveDataError, TwelveDataProvider
from sp500_strategy_simulator.performance import build_equity_curve, calculate_metrics
from sp500_strategy_simulator.simulation import simulate

st.set_page_config(page_title="S&P 500 Strategy Simulator", layout="wide", page_icon="📈")
st.title("📈 S&P 500 Momentum Strategy Simulator")

# --- Barre latérale : Paramètres ---
with st.sidebar:
    st.header("⚙️ Configuration")

    api_key_env = os.getenv("TWELVE_DATA_API_KEY", "")
    api_key_input = st.text_input(
        "Clé API Twelve Data",
        value=api_key_env,
        type="password",
        help="Détectée automatiquement depuis .env si présent",
    )

    # Top 20 des plus grandes capitalisations du S&P 500
    top_20_sp500 = (
        "AAPL, MSFT, NVDA, AMZN, GOOGL, META, BRK.B, LLY, AVGO, TSLA, "
        "JPM, UNH, V, XOM, MA, JNJ, COST, HD, PG, ABBV"
    )

    symbols_input = st.text_area(
        "Symboles (séparés par des virgules)",
        value=top_20_sp500,
        help="20 leaders du S&P 500",
        height=100,
    )

    col_d1, col_d2 = st.columns(2)
    today = date.today()
    default_start = today - timedelta(days=365)
    start_date = col_d1.date_input("Date de début", value=default_start)
    end_date = col_d2.date_input("Date de fin", value=today)

    capital = st.number_input("Capital initial ($)", min_value=100.0, value=10000.0, step=1000.0)
    # Sélection de 5 actifs en portefeuille
    assets = st.number_input("Nombre d'actifs en portefeuille", min_value=1, max_value=50, value=5)
    lookback = st.number_input("Fenêtre Lookback (jours)", min_value=10, value=252)
    skip = st.number_input("Fenêtre Skip (jours)", min_value=0, value=21)
    commission = st.number_input("Commission (%)", min_value=0.0, max_value=5.0, value=0.1) / 100.0

    run_btn = st.button("🚀 Lancer la simulation", type="primary", use_container_width=True)

# --- Exécution ---
if run_btn:
    api_key = api_key_input.strip()
    if not api_key:
        st.error("Veuillez renseigner votre clé API Twelve Data.")
        st.stop()

    symbols = list(dict.fromkeys(s.strip().upper() for s in symbols_input.split(",") if s.strip()))

    if not symbols:
        st.error("Veuillez renseigner au moins un ticker valide.")
        st.stop()

    if start_date >= end_date:
        st.error("La date de début doit précéder la date de fin.")
        st.stop()

    with st.spinner(f"Récupération des données pour {len(symbols)} actifs et calcul du backtest..."):
        try:
            config = StrategyConfig(
                initial_capital=capital,
                n_assets=assets,
                momentum_lookback_days=lookback,
                momentum_skip_days=skip,
                commission_rate=commission,
                start_date=start_date,
                end_date=end_date,
            )

            # Lookback étendu pour avoir l'historique suffisant au premier jour du backtest
            history_start = start_date - timedelta(days=int((lookback + skip) * 1.5) + 30)

            provider = TwelveDataProvider(api_key=api_key)
            bars_by_symbol = provider.fetch_daily_bars(
                symbols=symbols,
                start_date=history_start,
                end_date=end_date,
            )

            trades = simulate(bars_by_symbol, config)
            full_curve = build_equity_curve(bars_by_symbol, trades, config)

            # Filtrer sur la période demandée
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

    # --- Affichage des KPIs ---
    st.subheader("📊 Résultats de la stratégie")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    final_val = curve[-1].value
    kpi1.metric("Valeur finale", f"${final_val:,.2f}", f"{(final_val / anchor_value - 1.0):.2%}")
    kpi2.metric("Rendement Annuel", f"{metrics.annualized_return:.2%}")
    kpi3.metric("Volatilité Annuelle", f"{metrics.annualized_volatility:.2%}")
    kpi4.metric("Ratio de Sharpe", f"{metrics.sharpe_ratio:.2f}")
    kpi5.metric("Max Drawdown", f"{metrics.max_drawdown:.2%}")

    # --- Graphique de la courbe d'équité ---
    df_curve = pd.DataFrame([{"Date": pt.session_date, "Portfolio Value": pt.value} for pt in curve])
    df_curve.set_index("Date", inplace=True)
    st.line_chart(df_curve, use_container_width=True)

    # --- Détails des transactions ---
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
            st.dataframe(df_trades, use_container_width=True)
        else:
            st.info("Aucune transaction exécutée sur la période.")