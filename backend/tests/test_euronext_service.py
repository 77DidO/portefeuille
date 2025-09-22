from __future__ import annotations

import httpx
import pytest

from app.services import euronext


class DummyResponse:
    def __init__(self, json_data, raise_error: Exception | None = None):
        self._json_data = json_data
        self._raise_error = raise_error

    def raise_for_status(self) -> None:
        if self._raise_error:
            raise self._raise_error

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class DummyClient:
    def __init__(self, expected_url: str, expected_params: dict[str, str], response: DummyResponse):
        self.expected_url = expected_url
        self.expected_params = expected_params
        self.response = response
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, params: dict[str, str] | None = None):
        self.calls.append((url, params))
        assert url == self.expected_url
        assert params == self.expected_params
        return self.response


@pytest.fixture(autouse=True)
def _clear_cache():
    euronext.clear_cache()
    yield
    euronext.clear_cache()


def test_fetch_price_by_isin(monkeypatch):
    expected_params = {"isin": "FR0000123456"}
    dummy_client = DummyClient(
        euronext._API_URL,  # type: ignore[attr-defined]
        expected_params,
        DummyResponse({"data": {"lastPrice": "123.45", "currency": "EUR"}}),
    )
    monkeypatch.setattr(euronext.httpx, "Client", lambda *args, **kwargs: dummy_client)

    price = euronext.fetch_price("fr0000123456")
    assert price == pytest.approx(123.45)
    assert dummy_client.calls == [(euronext._API_URL, expected_params)]  # type: ignore[attr-defined]

    # ensure cache is used on subsequent calls
    price_again = euronext.fetch_price("FR0000123456")
    assert price_again == pytest.approx(123.45)
    assert len(dummy_client.calls) == 1


def test_fetch_price_by_symbol(monkeypatch):
    expected_params = {"symbol": "MC", "mic": "XPAR"}
    dummy_client = DummyClient(
        euronext._API_URL,  # type: ignore[attr-defined]
        expected_params,
        DummyResponse({"last": 456.78, "currency": "EURO"}),
    )
    monkeypatch.setattr(euronext.httpx, "Client", lambda *args, **kwargs: dummy_client)

    price = euronext.fetch_price("mc.pa")
    assert price == pytest.approx(456.78)
    assert dummy_client.calls == [(euronext._API_URL, expected_params)]  # type: ignore[attr-defined]


def test_fetch_price_rejects_non_eur_currency(monkeypatch):
    dummy_client = DummyClient(
        euronext._API_URL,  # type: ignore[attr-defined]
        {"symbol": "MC", "mic": "XPAR"},
        DummyResponse({"data": {"lastPrice": 10.0, "currency": "USD"}}),
    )
    monkeypatch.setattr(euronext.httpx, "Client", lambda *args, **kwargs: dummy_client)

    with pytest.raises(euronext.EuronextAPIError):
        euronext.fetch_price("MC.PA")


def test_fetch_price_http_error(monkeypatch):
    dummy_client = DummyClient(
        euronext._API_URL,  # type: ignore[attr-defined]
        {"isin": "FR0000123456"},
        DummyResponse({"data": {"lastPrice": 10.0}}, raise_error=httpx.HTTPError("boom")),
    )
    monkeypatch.setattr(euronext.httpx, "Client", lambda *args, **kwargs: dummy_client)

    with pytest.raises(euronext.EuronextAPIError):
        euronext.fetch_price("FR0000123456")
