# Export & Import — Modèle de données (CSV)

L'export `GET /export/zip` retourne une archive ZIP contenant les fichiers décrits ci-dessous. Les mêmes structures peuvent être utilisées pour réimporter des données via `POST /transactions/import` (un ZIP contenant au minimum `transactions.csv`).

Chaque fichier est encodé en UTF-8, utilise `,` comme séparateur et inclut une ligne d'en-tête.

## transactions.csv

```
id,source,portfolio_type,operation,date,asset,symbol,isin,mic,quantity,unit_price_eur,total_eur,fee_eur,fee_asset,fee_quantity,notes
```

| Colonne | Description |
| --- | --- |
| `id` | Identifiant unique facultatif utilisé tel quel comme `transaction_uid` lors de l'import. Laisser vide pour laisser l'algorithme générer l'identifiant. |
| `source` | Plateforme ou courtier d'origine de la transaction (ex. `degiro`, `binance`). |
| `portfolio_type` | Type de portefeuille tel que défini dans l'application (`PEA`, `CTO`, `CRYPTO`, …). |
| `operation` | Type d'opération (`BUY`, `SELL`, `DIVIDEND`, `TRANSFER`, `STAKING_REWARD`, etc.). |
| `date` | Horodatage ISO 8601 (UTC ou avec décalage explicite). Les dates sont normalisées en UTC lors de l'import. |
| `asset` | Nom libre de l'actif. |
| `symbol` | Symbole de cotation facultatif. |
| `isin` | Code ISIN facultatif. |
| `mic` | Code MIC facultatif permettant d'identifier la place de cotation. |
| `quantity` | Quantité achetée / vendue (valeur positive). |
| `unit_price_eur` | Prix unitaire en euros. |
| `total_eur` | Montant total en euros (valeur absolue). |
| `fee_eur` | Montant des frais en euros. Peut être nul. |
| `fee_asset` | Devise d'origine des frais. Laisser vide si les frais sont déjà exprimés en euros. |
| `fee_quantity` | Quantité facturée dans la devise `fee_asset` si différente de l'euro (permet de conserver l'information brute). |
| `notes` | Commentaire libre. |

> ℹ️ Les transactions sont dédupliquées en fonction de `id`/`transaction_uid`. Si vous réimportez un fichier déjà chargé, seules les lignes modifiées sont mises à jour.

👉 Plusieurs exemples complets sont disponibles dans [`samples/transactions.csv`](../samples/transactions.csv).

## holdings.csv

```
as_of,portfolio_type,asset,symbol,isin,mic,symbol_or_isin,quantity,pru_eur,invested_eur,market_price_eur,market_value_eur,pl_eur,pl_pct
```

- Les holdings sont calculés à partir des transactions et sont fournis à titre informatif dans l'export.
- `as_of` correspond à la date/heure de calcul (ISO 8601). Lors d'un import, ce fichier est ignoré : les positions sont recalculées côté serveur.
- `symbol_or_isin` est le champ clé interne utilisé pour identifier la position (symbole + place de cotation ou ISIN).

## snapshots.csv

```
ts,value_pea_eur,value_crypto_eur,value_total_eur,pnl_total_eur
```

- Chaque ligne représente un snapshot quotidien. `pnl_total_eur` correspond au P&L réalisé + latent à la date `ts`.
- Lors de l'import CSV, ce fichier est facultatif ; si présent, les snapshots sont réinjectés tels quels.
- Vous pouvez importer un sous-ensemble (ex. uniquement `ts` et `value_total_eur`) : les colonnes manquantes sont ignorées.

## journal_trades.csv

```
id,asset,pair,setup,entry,sl,tp,risk_r,status,opened_at,closed_at,result_r,notes
```

- Les dates (`opened_at`, `closed_at`) sont au format ISO 8601. Elles peuvent être vides.
- `status` correspond au statut librement défini dans l'application (ex. `OPEN`, `CLOSED`, `INVALIDATED`).
- `risk_r` et `result_r` sont exprimés en multiple de risque (R) et restent optionnels.
- Lors de l'import, l'ID est utilisé pour mettre à jour un trade existant. Sans ID, un nouveau trade est créé.

> ℹ️ Des exemples complets sont disponibles dans le dossier [`samples/`](../samples/).
