from datetime import date, timedelta

import pytest

from sp500_strategy_simulator.cli import _parse_date, main
from sp500_strategy_simulator.models import DailyBar


def test_parse_date_rejects_invalid_format():
    with pytest.raises(Exception):
        _parse_date("not-a-date")


def test_main_rejects_invalid_symbol_list():
    with pytest.raises(SystemExit) as exc:
        main(["--symbols", "AAPL,,MSFT", "--start", "2024-01-01", "--end", "2024-02-01"])
    assert exc.value.code == 2


def test_main_reports_metrics_and_exports_only_requested_period(tmp_path, monkeypatch, capsys):
    import sp500_strategy_simulator.cli as cli

    start = date(2024, 1, 3)
    bars = {}
    for symbol, multiplier in (("AAA", 1.0), ("BBB", 1.1)):
        rows = []
        for index in range(6):
            day = start - timedelta(days=3 - index)
            close = (100 + index) * multiplier
            rows.append(DailyBar(symbol, day, close, close, close, close, 1000))
        bars[symbol] = rows

    class FakeProvider:
        def fetch_daily_bars(self, symbols, start_date, end_date):
            return bars

    monkeypatch.setattr(cli, "TwelveDataProvider", FakeProvider)
    output = tmp_path / "nested" / "equity.csv"
    result = main([
        "--symbols", "aaa,BBB,AAA", "--start", start.isoformat(),
        "--end", (start + timedelta(days=2)).isoformat(), "--assets", "1",
        "--lookback", "2", "--skip", "0", "--commission", "0",
        "--output-csv", str(output),
    ])
    assert result == 0
    captured = capsys.readouterr()
    assert "Period: 2024-01-03 to 2024-01-05" in captured.out
    assert "Symbols requested: 2" in captured.out
    assert "Initial portfolio value for evaluation: 10,000.00" in captured.out
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "date,portfolio_value,daily_return"
    rows = [line.split(",") for line in lines[1:]]
    assert all(row[0] >= "2024-01-03" for row in rows)
    assert all(row[0] <= "2024-01-05" for row in rows)
    assert float(rows[0][2]) == pytest.approx(float(rows[0][1]) / 10_000 - 1)
