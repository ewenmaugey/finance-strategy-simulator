import os
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.data_provider import TwelveDataError, TwelveDataProvider
from sp500_strategy_simulator.performance import build_equity_curve, calculate_metrics
from sp500_strategy_simulator.simulation import simulate
from sp500_strategy_simulator.congress_data import fetch_congress_transactions, get_top_politicians

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
    default_start = today - timedelta(days=365)
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
    with st.spinner("Chargement des transactions du Congrès..."):
        pol_filter = None if politician_choice == "Tous les membres" else politician_choice
        df_congress = fetch_congress_transactions(politician=pol_filter)
        if not df_congress.empty:
            _dataframe_compat(
                df_congress.head(20)[["disclosure_date", "transaction_date", "representative", "ticker", "type", "amount"]]
            )
        else:
            st.info("Aucune transaction trouvée.")

# --- Exécution ---
if run_btn:
    if "[À venir]" in selected_strategy:
        st.warning(f"La stratégie '{selected_strategy}' n'est pas encore implémentée.")
        st.stop()

    if selected_strategy == "🏛️ Congress Tracker (Copie des élus US)":
        st.success(f"Déclarations récupérées avec succès pour **{politician_choice}**. Prochaine étape : génération des ordres d'achat à chaque date de déclaration !")
        st.stop()

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
                commission_rate=0.0,
                fixed_commission=fixed_fee,
                tax_rate=tax_percent / 100.0,
                start_date=start_date,
                end_date=end_date,
            )

            history_start = start_date - timedelta(days=int((lookback + skip) * 1.5) + 30)

            provider = TwelveDataProvider(api_key=api_key)
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

    final_val_brut = curve[-1].value
    gain_brut = final_val_brut - anchor_value
    tax = max(0.0, gain_brut * config.tax_rate) if gain_brut > 0 else 0.0
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
