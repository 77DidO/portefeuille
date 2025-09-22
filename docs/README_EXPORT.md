# Export & Import — Modèle de données (CSV)

L'export `GET /export/zip` retourne une archive ZIP contenant les fichiers ci-dessous. Les mêmes structures peuvent être réutilisées pour réimporter des données via `POST /transactions/import` (un ZIP contenant au minimum `transactions.csv`).

Chaque fichier est encodé en UTF-8 avec séparateur `,` et inclut une ligne d'en-tête.

## transactions.csv

`source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,fee_asset,fx_rate,total_eur,ts,notes,external_ref`

- `ts` doit être au format ISO 8601 (UTC ou avec décalage horaire explicite). Lors de l'import, les timestamps sont convertis en UTC.
- `external_ref` est utilisé pour détecter les doublons : si une transaction avec la même référence existe déjà, elle est mise à jour au lieu d'être dupliquée.
- `operation` accepte les mêmes valeurs que dans l'application (ex. `BUY`, `SELL`, `DIVIDEND`, `TRANSFER`, etc.).
- `fee_asset` permet d'indiquer la devise d'origine des frais si différente de l'euro.
- `fx_rate` correspond au taux de change appliqué pour convertir la transaction en EUR (par défaut `1.0`).

## holdings.csv

`as_of,type_portefeuille,asset,symbol_or_isin,quantity,pru_eur,invested_eur,market_price_eur,market_value_eur,pl_eur,pl_pct`

- Les holdings sont calculés à partir des transactions et sont fournis à titre informatif dans l'export.
- `as_of` correspond à la date/heure de calcul (ISO 8601). Lors d'un import, ce fichier est ignoré : les positions sont recalculées côté serveur.

## snapshots.csv

`ts,value_pea_eur,value_crypto_eur,value_total_eur,pnl_total_eur`

- Chaque ligne représente une prise de snapshot quotidienne. `pnl_total_eur` correspond au P&L réalisé + latent à la date `ts`.
- Lors de l'import CSV, ce fichier est facultatif ; si présent, les snapshots sont réinjectés tels quels.

## journal_trades.csv

`id,asset,pair,setup,entry,sl,tp,risk_r,status,opened_at,closed_at,result_r,notes`

- Les dates (`opened_at`, `closed_at`) sont au format ISO 8601. Elles peuvent être vides.
- `status` correspond au statut librement défini dans l'application (ex. `OPEN`, `CLOSED`, `INVALIDATED`).
- `risk_r` et `result_r` sont exprimés en multiple de risque (R) et restent optionnels.

> ℹ️ Des exemples complets sont disponibles dans le dossier [`samples/`](../samples/).
