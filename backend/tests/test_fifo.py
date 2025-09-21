from __future__ import annotations

from app.services.fifo import FIFOPortfolio


def test_fifo_partial_sell():
    fifo = FIFOPortfolio()
    fifo.buy("BTC", quantity=1.0, total_cost_eur=10000.0)
    fifo.buy("BTC", quantity=1.0, total_cost_eur=12000.0)
    realized = fifo.sell("BTC", quantity=1.5, total_proceeds_eur=18000.0, fee_eur=0.0)
    assert round(realized, 2) == round(18000 - (10000 + 0.5 * 12000), 2)
    qty, cost = fifo.current_position("BTC")
    assert abs(qty - 0.5) < 1e-8
    assert round(cost, 2) == round(0.5 * 12000, 2)


def test_fifo_dividend_adds_realized():
    fifo = FIFOPortfolio()
    fifo.buy("ETH", 2.0, 2000.0)
    fifo.dividend("ETH", 100.0)
    assert fifo.assets["ETH"].realized_pnl == 100.0


def test_fifo_conversion_two_legs():
    fifo = FIFOPortfolio()
    fifo.buy("BTC", 1.0, 10000.0)
    fifo.sell("BTC", 1.0, 12000.0, fee_eur=100.0)
    fifo.buy("ETH", 10.0, 11900.0)
    assert fifo.assets["BTC"].realized_pnl == (12000.0 - 100.0) - 10000.0
    qty_eth, cost_eth = fifo.current_position("ETH")
    assert qty_eth == 10.0
    assert cost_eth == 11900.0
