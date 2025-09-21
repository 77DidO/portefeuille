
# Export — Modèle de données (CSV)
## transactions.csv
id,source,type_portefeuille,operation,asset,symbol_or_isin,quantity,unit_price_eur,fee_eur,total_eur,ts,notes,external_ref
## holdings.csv
as_of,type_portefeuille,asset,symbol_or_isin,quantity,pru_eur,invested_eur,market_price_eur,market_value_eur,pl_eur,pl_pct
## snapshots.csv
ts,value_pea_eur,value_crypto_eur,value_total_eur,pnl_total_eur
## journal_trades.csv
id,asset,pair,setup,entry,sl,tp,risk_r,status,opened_at,closed_at,result_r,notes

