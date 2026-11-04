# S&P 500 Strategy Simulator 📈

Simulateur de stratégie de trading quantitative (momentum) sur un univers d'actions américaines, avec interface web Streamlit.

> ⚠️ **Avertissement :** Projet éducatif et de recherche. Ne constitue pas un conseil financier et ne passe aucun ordre réel.

---

## 🎯 Fonctionnalités

- **Données réelles :** Récupération de l'historique des cours de clôture/ouverture via l'API [Twelve Data](https://twelvedata.com/).
- **Stratégie Momentum :**
  - **Lookback :** Sélection des actions les plus performantes sur une fenêtre passée (ex. 252 jours).
  - **Skip :** Exclusion des derniers jours (ex. 21 jours) pour éviter l'effet de surchauffe à court terme (*short-term reversal*).
- **Exécution réaliste :**
  - Achat à la clôture (*Close*) et revente à l'ouverture (*Open*).
  - Prise en compte de **frais fixes par ordre** (ex. 1 €/ordre à l'achat et à la revente).
- **Analyse financière :**
  - Métriques clés : Rendement annualisé, volatilité, ratio de Sharpe, Max Drawdown.
  - Calcul de la **fiscalité** (Flat Tax 30 % sur la plus-value nette).
  - Graphique d'évolution de l'équité et historique complet des ordres.

---

## 🚀 Démarrage rapide

### 1. Prérequis & Installation

```bash
git clone https://github.com/ewenmaugey/sp500-strategy-simulator.git
cd sp500-strategy-simulator

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows : .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration API

Créez un fichier `.env` à la racine :

```env
TWELVE_DATA_API_KEY="votre_cle_api"
```

### 3. Lancer l'application

```bash
streamlit run app.py
```
