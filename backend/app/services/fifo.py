from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Tuple


@dataclass
class Lot:
    quantity: float
    cost_basis: float  # total cost in EUR including fees


@dataclass
class AssetState:
    lots: List[Lot] = field(default_factory=list)
    realized_pnl: float = 0.0


class FIFOPortfolio:
    def __init__(self) -> None:
        self.assets: Dict[Hashable, AssetState] = {}

    def _get_state(self, symbol: Hashable) -> AssetState:
        return self.assets.setdefault(symbol, AssetState())

    def buy(self, symbol: Hashable, quantity: float, total_cost_eur: float) -> None:
        state = self._get_state(symbol)
        state.lots.append(Lot(quantity=quantity, cost_basis=total_cost_eur))

    def sell(
        self,
        symbol: Hashable,
        quantity: float,
        total_proceeds_eur: float,
        fee_eur: float = 0.0,
    ) -> float:
        state = self._get_state(symbol)
        qty_to_sell = quantity
        realized_pnl = 0.0
        proceeds_net = total_proceeds_eur - fee_eur

        while qty_to_sell > 1e-12 and state.lots:
            lot = state.lots[0]
            if lot.quantity <= qty_to_sell + 1e-12:
                consumed_qty = lot.quantity
                lot_cost = lot.cost_basis
                state.lots.pop(0)
            else:
                consumed_qty = qty_to_sell
                lot_cost = lot.cost_basis * (consumed_qty / lot.quantity)
                lot.quantity -= consumed_qty
                lot.cost_basis -= lot_cost

            qty_to_sell -= consumed_qty
            proportional_proceeds = proceeds_net * (consumed_qty / quantity)
            realized_pnl += proportional_proceeds - lot_cost

        if qty_to_sell > 1e-6:
            # The dataset contains more quantity to sell than currently tracked in the
            # FIFO state. Instead of failing, treat the remaining proceeds as fully
            # realized with an unknown (assumed zero) cost basis. This keeps the
            # application responsive when historical data is incomplete.
            proportional_proceeds = proceeds_net * (qty_to_sell / quantity)
            realized_pnl += proportional_proceeds
            qty_to_sell = 0.0

        state.realized_pnl += realized_pnl
        return realized_pnl

    def dividend(self, symbol: Hashable, amount_eur: float) -> None:
        state = self._get_state(symbol)
        state.realized_pnl += amount_eur

    def current_position(self, symbol: Hashable) -> Tuple[float, float]:
        state = self._get_state(symbol)
        total_qty = sum(lot.quantity for lot in state.lots)
        total_cost = sum(lot.cost_basis for lot in state.lots)
        return total_qty, total_cost

    def as_dict(self) -> Dict[Hashable, AssetState]:
        return self.assets
