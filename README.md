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

La simulation respecte l’ordre temporel suivant : le score connu à la clôture détermine l’achat à cette clôture, puis la position est vendue à l’ouverture de la séance de marché suivante. Les paramètres de classement sont exprimés en observations de marché (252 séances de lookback et 21 séances exclues par défaut), et non en jours calendaires.

## Hypothèses et limites actuelles

- Les frais sont appliqués sur chaque transaction et les fractions d’actions sont autorisées.
- L’allocation est équipondérée entre les titres sélectionnés, dans la limite des liquidités disponibles.
- La simulation utilise les dates présentes dans les données fournies comme calendrier des séances. Une ouverture absente pour un titre ne génère pas de vente fictive ; le comportement des positions bloquées par des données manquantes doit être interprété avec prudence.
- La valorisation conserve le dernier cours de clôture connu lorsqu’un titre détenu n’a pas de nouvelle clôture. Cela évite de valoriser arbitrairement la position à zéro, mais peut laisser une valorisation périmée.
- Les métriques annualisées supposent des observations régulièrement espacées. Le ratio de Sharpe est calculé avec le taux sans risque fourni (zéro par défaut).
- La liste actuelle des membres du S&P 500 ne représente pas sa composition historique. L’utiliser sur une période passée peut introduire un biais de survivance.
- Le fournisseur Twelve Data requiert une clé API (`TWELVE_DATA_API_KEY`) et peut imposer des limites de requêtes et de profondeur historique. La disponibilité des données doit être vérifiée pour chaque période et chaque symbole.

## Principes du projet

- **Pas de données futures :** le classement ne peut utiliser que les informations disponibles au moment de l’achat.
- **Reproductibilité :** chaque simulation doit exposer ses paramètres, sa période et ses hypothèses.
- **Tests sans clé API :** les calculs et le moteur doivent fonctionner avec des données synthétiques ; les tests du fournisseur utilisent des réponses simulées.
- **Référence de comparaison :** les résultats devront être comparés à un benchmark adapté sur la même période et avec des conventions de valorisation comparables.

## État d’avancement

Le dépôt contient les modèles de données, la configuration, le classement par momentum, le moteur de simulation close-to-next-open, le fournisseur Twelve Data et les fonctions de valorisation et de calcul des métriques. Des tests unitaires couvrent ces composants. L’interface de ligne de commande, la constitution fiable de l’univers historique, la comparaison à un benchmark et un rapport de backtest restent à construire.
