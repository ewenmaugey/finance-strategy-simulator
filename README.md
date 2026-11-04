# S&P 500 Strategy Simulator 📈

Simulateur de stratégies de trading quantitatives sur actions américaines, avec interface web Streamlit.

> ⚠️ **Avertissement :** Projet éducatif et de recherche. Ne constitue pas un conseil financier et n'exécute aucun ordre réel.

---

## 🎯 Stratégies disponibles

### 1. 🚀 Momentum (S&P 500)
- **Lookback & Skip :** Sélection des meilleures actions sur une fenêtre passée (ex. 252 jours), en ignorant les derniers jours (ex. 21 jours) pour éviter l'effet de retournement à court terme (*short-term reversal*).
- **Rééquilibrage périodique :** Allocation équitable sur les $N$ meilleurs actifs.

### 2. 🏛️ Congress Tracker (Copie des élus US)
- **Suivi du STOCK Act :** Analyse des déclarations publiques obligatoires (*Periodic Transaction Reports*) déposées par les membres du Congrès américain (ex. Nancy Pelosi, Michael McCaul, Ro Khanna...).
- **Respect du délai légal :** Les ordres d'achat sont exécutés à la date de divulgation publique (*Disclosure Date*) et non à la date secrète de transaction de l'élu.
- **Gestion de position :** Vente automatique après une durée de détention paramétrable (ex. 90 ou 360 jours).

---

## ⚙️ Moteur d'exécution & Fiscalité

- **Données de marché :** Historique des cours via l'API [Twelve Data](https://twelvedata.com/).
- **Frais de courtage réalistes :** Prise en compte de frais fixes par ordre (ex. 1 $/ordre à l'achat et à la revente).
- **Fiscalité :** Déduction optionnelle d'une Flat Tax (30 % par défaut) sur les plus-values nettes réalisées.
- **Analyse de performance :** Valeur finale, rendement annualisé, volatilité, ratio de Sharpe, Max Drawdown, courbe d'équité interactive et historique complet des ordres.

---

## 🚀 Démarrage rapide

### 1. Installation

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
