from app.main import analyze, metrics, norm_actuals, norm_forecasts

def test_metrics():
    result=metrics([{"forecast_mw":110,"actual_mw":100},{"forecast_mw":80,"actual_mw":100}],4)
    assert result["mae_mw"] == 15
    assert result["bias_mw"] == -5
    assert result["coverage_pct"] == 50

def test_normalize_rows():
    f=norm_forecasts([{"startTime":"2026-01-02T00:00:00Z","publishTime":"2026-01-01T12:00:00Z","generation":123.4}])
    a=norm_actuals([{"startTime":"2026-01-02T00:00:00Z","fuelType":"WIND","generation":120}])
    assert len(f)==1 and f[0]["forecast_mw"]==123.4
    assert len(a)==1 and a[0]["actual_mw"]==120

def test_match():
    result=analyze([{"startTime":"2026-01-02T00:00:00Z","publishTime":"2026-01-01T12:00:00Z","generation":123.4}],
                   [{"startTime":"2026-01-02T00:00:00Z","fuelType":"WIND","generation":120}])
    assert result["metrics"]["matched_intervals"]==1
    assert result["records"][0]["error_mw"]==3.4
