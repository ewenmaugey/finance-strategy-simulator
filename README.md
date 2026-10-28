# S&P 500 Strategy Simulator

Un projet de recherche pour récupérer des données de marché via Twelve Data, classer des actions du S&P 500 selon une règle statistique explicite et simuler l’évolution d’un portefeuille fictif. Les résultats sont reproductibles et accompagnés de leurs hypothèses.

> **Avertissement :** ce projet est un outil éducatif de simulation. Il ne fournit pas de conseil financier et ne passe aucun ordre réel.

## Objectif de la version 1

Construire un backtest simple, compréhensible et testable, sans fuite de données futures :

1. Récupérer les données historiques nécessaires pour les titres de l’univers étudié.
2. À chaque séance, classer les titres à partir des seules données disponibles à la clôture de cette séance.
3. Retenir les cinq meilleurs titres éligibles.
4. Acheter les titres retenus à la clôture de la séance de décision, puis les vendre à l’ouverture de la séance suivante. Le cycle se répète chaque séance, avec une allocation équipondérée.
5. Déduire les frais configurés et suivre la valeur du portefeuille au fil du temps.

La stratégie a donc une fréquence **journalière avec deux exécutions par cycle** : achat à la clôture, puis vente à l’ouverture suivante. « x2 » désigne ces deux opérations à des moments différents, pas deux cycles complets par jour.

## Règle de classement initiale

La stratégie v1 utilise le **momentum sur 12 mois, en excluant le mois le plus récent**. Le score est calculé à partir des cours historiques disponibles à la clôture de la date de décision. Les paramètres de la stratégie doivent être fixés avant l’évaluation sur la période de test.

La simulation doit respecter l’ordre temporel : le score connu à la clôture détermine l’achat à cette clôture, et la vente est valorisée à l’ouverture de la séance suivante. Les conventions précises d’éligibilité, de frais, d’allocation et de données manquantes seront documentées et testées avant d’interpréter les résultats.

## Principes du projet

- **Pas de données futures :** le classement ne peut utiliser que des informations disponibles au moment de l’achat.
- **Reproductibilité :** chaque simulation doit exposer ses paramètres, sa période et ses hypothèses.
- **Tests sans clé API :** les calculs et le moteur doivent fonctionner avec des données synthétiques ; Twelve Data sera isolé derrière une interface de fournisseur.
- **Limites visibles :** la liste actuelle des membres du S&P 500 ne représente pas automatiquement sa composition historique. Son utilisation pour une période passée peut créer un biais de survivance et devra être signalée.
- **Référence de comparaison :** les résultats seront comparés à un benchmark adapté sur la même période et avec des conventions de valorisation comparables.

## État d’avancement

Le périmètre initial est défini : classement quotidien par momentum, achat à la clôture et vente à l’ouverture suivante. Le moteur, l’intégration Twelve Data, les tests et le rapport restent à construire.
