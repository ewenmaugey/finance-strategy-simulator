# S&P 500 Strategy Simulator

Un projet de recherche pour récupérer des données de marché via Twelve Data, classer des actions selon une règle statistique explicite et simuler l’évolution d’un portefeuille fictif. Les résultats sont reproductibles et accompagnés de leurs hypothèses.

> **Avertissement :** ce projet est un outil éducatif de simulation. Il ne fournit pas de conseil financier et ne passe aucun ordre réel.

## Objectif de la version 1

La stratégie classe les titres selon leur momentum sur 12 mois en excluant le mois le plus récent, achète les meilleurs à la clôture, puis revend à l’ouverture de la séance suivante. Les frais sont déduits sur chaque transaction et le portefeuille est valorisé au fil des séances.

## Lancer un backtest

Installer le projet et ses dépendances de données :

```bash
python -m pip install -e '.[data]'
```

Définir la clé API Twelve Data sans l’inscrire dans le code :

```bash
export TWELVE_DATA_API_KEY="votre_clé"
```

Puis lancer, par exemple :

```bash
sp500-backtest \
  --symbols AAPL,MSFT,NVDA \
  --start 2023-01-01 \
  --end 2024-12-31
```

Options disponibles : `--capital`, `--assets`, `--lookback`, `--skip` et `--commission`. Les dates sont au format `YYYY-MM-DD`; les jours de lookback et de skip sont des observations de marché, non des jours calendaires. `--symbols` attend une liste fournie par l’utilisateur : la CLI ne construit pas encore l’univers historique du S&P 500.

L’outil affiche la valeur finale et les métriques de rendement total et annualisé, de volatilité, de Sharpe et de drawdown maximal. La période inclut un historique de chauffe antérieur au début demandé pour calculer le momentum; les métriques reposent toutefois sur la courbe complète construite à partir des données récupérées, donc elles peuvent inclure cette période de chauffe. Il s’agit d’un point à affiner pour isoler strictement la période d’évaluation.

## Principes et limites

- Pas d’utilisation volontaire de données futures pour le signal; les choix de séance s’appuient sur les cours disponibles à la clôture.
- Le fournisseur Twelve Data nécessite une clé API et peut imposer des quotas ou limites de profondeur historique.
- Les résultats dépendent de la qualité, des ajustements et de la disponibilité des données du fournisseur.
- La composition actuelle du S&P 500 ne représente pas sa composition historique et peut créer un biais de survivance.
- Un benchmark comparable et un rapport détaillé restent à construire.
- Le backtest ne modélise pas encore l’impact de marché, le slippage, les impôts ou les restrictions de liquidité.

## Développement

Les calculs peuvent être testés sans clé API avec des données synthétiques :

```bash
python -m pip install -e '.[test,data]'
pytest
ruff check .
```
