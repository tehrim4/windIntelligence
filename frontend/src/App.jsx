const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  Download,
  RefreshCw,
  Wind,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
const fmt = (v, d = 1) =>
  v == null || Number.isNaN(Number(v))
    ? "—"
    : Number(v).toLocaleString("en-GB", {
        maximumFractionDigits: d,
        minimumFractionDigits: d,
      });
const day = (v) =>
  v
    ? new Date(v + "T00:00:00Z").toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
      })
    : "—";
function csv(rows) {
  const keys = [
    "timestamp",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "absolute_error_mw",
    "forecast_published_at",
  ];
  const q = (v) => '"' + String(v ?? "").replaceAll('"', '""') + '"';
  const text = [
    keys.join(","),
    ...rows.map((r) => keys.map((k) => q(r[k])).join(",")),
  ].join("\\n");
  const u = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = u;
  a.download = "wind-forecast-analysis.csv";
  a.click();
  URL.revokeObjectURL(u);
}
export default function App() {
  const [from, SF] = useState("2026-01-01"),
    [to, ST] = useState("2026-01-31"),
    [data, SD] = useState(null),
    [status, SS] = useState("loading"),
    [error, SE] = useState("");
  async function load() {
    SS("loading");
    SE("");

    try {
      const r = await fetch(
        `${API_BASE_URL}/api/analysis?` + new URLSearchParams({ from, to }),
      );
      const b = await r.json();
      if (!r.ok) throw Error(b.detail || "Request failed");
      SD(b);
      SS("ok");
    } catch (e) {
      SD(null);
      SE(e.message + " Ensure the backend is running and Elexon is reachable.");
      SS("error");
    }
  }
  useEffect(() => {
    load();
  }, []);
  const m = data?.metrics || {},
    records = data?.records || [],
    daily = (data?.daily || []).map((r) => ({ ...r, day: day(r.date) }));
  const card = (label, value, unit, note, Icon) => (
    <article className="metric">
      <div className="metric-label">
        {label}
        <span>
          <Icon size={17} />
        </span>
      </div>
      <strong>
        {value}
        <small>{unit}</small>
      </strong>
      <p>{note}</p>
    </article>
  );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="mark">
            <Wind />
          </span>
          <div>
            <b>gridbricks</b>
            <small>ENERGY INTELLIGENCE</small>
          </div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <div className="nav-active">
          <Activity size={17} /> Forecast analysis
        </div>
        <p className="nav-label">DATA SOURCES</p>
        <div className="source">
          <i className="blue" />{" "}
          <div>
            <b>WINDFOR</b>
            <small>Wind forecast</small>
          </div>
          <CheckCircle2 size={15} />
        </div>
        <div className="source">
          <i className="orange" />{" "}
          <div>
            <b>FUELHH</b>
            <small>Actual generation</small>
          </div>
          <CheckCircle2 size={15} />
        </div>
        <div className="side-foot">
          ●{" "}
          <span>
            Historical analysis
            <br />
            <small>United Kingdom · UTC</small>
          </span>
        </div>
      </aside>
      <main>
        <header>
          <span>
            Workspace <b>/</b> Forecast analysis
          </span>
          <span className="pill">● Historical analysis</span>
        </header>
        <section className="hero">
          <div>
            <div className="eyebrow">RENEWABLES / WIND</div>
            <h1>
              Wind generation <em>intelligence.</em>
            </h1>
            <p>
              Understand day-ahead forecast performance against actual UK wind
              generation.
            </p>
          </div>
          <button
            className="secondary"
            disabled={!records.length}
            onClick={() => csv(records)}
          >
            <Download size={16} /> Export CSV
          </button>
        </section>
        <section className="filters">
          <b>
            <CalendarDays size={17} /> Analysis period
          </b>
          <label>
            From{" "}
            <input
              type="date"
              value={from}
              max={to}
              onChange={(e) => SF(e.target.value)}
            />
          </label>
          <label>
            To{" "}
            <input
              type="date"
              value={to}
              min={from}
              onChange={(e) => ST(e.target.value)}
            />
          </label>
          <button onClick={load} disabled={status === "loading"}>
            <RefreshCw size={15} />{" "}
            {status === "loading" ? "Loading…" : "Run analysis"}
          </button>
        </section>
        {status === "loading" && (
          <div className="notice">
            Loading forecast and actual data from Elexon…
          </div>
        )}
        {status === "error" && (
          <div className="notice error">
            <AlertCircle />
            <div>
              <b>Could not load analysis</b>
              <p>{error}</p>
              <button className="retry" onClick={load}>
                Try again
              </button>
            </div>
          </div>
        )}
        {status === "ok" && !records.length && (
          <div className="notice error">
            <AlertCircle />
            <div>
              <b>No matched intervals found</b>
              <p>
                No real records matched for this period and cutoff. Check API
                response fields and date parameters. No sample measurements have
                been substituted.
              </p>
            </div>
          </div>
        )}
        {status === "ok" && (
          <>
            <div className="section-title">
              <div>
                <h2>Performance overview</h2>
                <p>
                  Calculated only from matched forecast and actual intervals.
                </p>
              </div>
              <span>● API-connected data</span>
            </div>
            <section className="metrics">
              {card(
                "Mean absolute error",
                fmt(m.mae_mw),
                "MW",
                "Average size of forecast miss",
                Activity,
              )}
              {card(
                "Root mean square error",
                fmt(m.rmse_mw),
                "MW",
                "Highlights larger misses",
                Activity,
              )}
              {card(
                "Weighted absolute error",
                m.wape_pct == null ? "—" : fmt(m.wape_pct),
                "%",
                "Error relative to actual output",
                Activity,
              )}
              {card(
                "Matched interval coverage",
                fmt(m.coverage_pct),
                "%",
                `${m.matched_intervals || 0} matched half-hours`,
                CheckCircle2,
              )}
            </section>
            <section className="charts">
              <article className="panel">
                <div className="panel-head">
                  <div>
                    <h3>Forecast vs actual</h3>
                    <p>Daily average generation · MW</p>
                  </div>
                  <div className="legend">
                    <span>🔵 Forecast</span>
                    <span>🟠 Actual</span>
                  </div>
                </div>
                <div className="chart">
                  {daily.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={daily}>
                        <CartesianGrid strokeDasharray="3 5" vertical={false} />
                        <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Line
                          dataKey="forecast_mw_average"
                          name="Forecast"
                          stroke="#4779dc"
                          strokeWidth={2.5}
                          dot={false}
                        />
                        <Line
                          dataKey="actual_mw_average"
                          name="Actual"
                          stroke="#e7a05b"
                          strokeWidth={2.5}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="empty">No chart data available.</div>
                  )}
                </div>
                <p className="chart-foot">
                  Half-hour intervals aggregated by delivery day ·{" "}
                  {daily.length} days
                </p>
              </article>
              <article className="panel">
                <div className="panel-head">
                  <div>
                    <h3>Daily forecast error</h3>
                    <p>Mean absolute error · MW</p>
                  </div>
                </div>
                <div className="chart short">
                  {daily.length ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={daily}>
                        <defs>
                          <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                            <stop
                              offset="0%"
                              stopColor="#e7a05b"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="100%"
                              stopColor="#e7a05b"
                              stopOpacity={0.02}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 5" vertical={false} />
                        <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Area
                          dataKey="mae_mw"
                          name="MAE (MW)"
                          stroke="#e7a05b"
                          fill="url(#fill)"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="empty">No error series available.</div>
                  )}
                </div>
                <div className="bias">
                  <span>Average bias</span>
                  <b>
                    {m.bias_mw == null
                      ? "—"
                      : (m.bias_mw > 0 ? "+" : "") + fmt(m.bias_mw) + " MW"}
                  </b>
                  <small>Positive means forecast above actual.</small>
                </div>
              </article>
            </section>
            <article className="panel table-panel">
              <div className="panel-head">
                <div>
                  <h3>Settlement interval records</h3>
                  <p>Matched records used in accuracy calculations</p>
                </div>
                <span className="count">{records.length} records</span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>DELIVERY TIME (UTC)</th>
                      <th>FORECAST (MW)</th>
                      <th>ACTUAL (MW)</th>
                      <th>ERROR (MW)</th>
                      <th>ABS. ERROR</th>
                      <th>FORECAST PUBLISHED</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.slice(0, 1000).map((r) => (
                      <tr key={r.timestamp}>
                        <td>
                          <b>{day(r.date)}</b> <span>{r.time}</span>
                        </td>
                        <td>{fmt(r.forecast_mw, 2)}</td>
                        <td>{fmt(r.actual_mw, 2)}</td>
                        <td
                          className={
                            r.error_mw > 0
                              ? "warm"
                              : r.error_mw < 0
                                ? "cool"
                                : ""
                          }
                        >
                          {r.error_mw > 0 ? "+" : ""}
                          {fmt(r.error_mw, 2)}
                        </td>
                        <td>{fmt(r.absolute_error_mw, 2)}</td>
                        <td>
                          {r.forecast_published_at
                            ? new Date(r.forecast_published_at).toLocaleString(
                                "en-GB",
                                {
                                  day: "2-digit",
                                  month: "short",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                  timeZone: "UTC",
                                  timeZoneName: "short",
                                },
                              )
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="table-foot">
                Showing {Math.min(records.length, 1000)} of {records.length}{" "}
                matched intervals
              </div>
            </article>
            <section className="method">
              <Activity />
              <div>
                <b>Methodology & data quality</b>
                <p>
                  {data.methodology.forecast_selection} {data.methodology.note}
                </p>
                <span>WINDFOR forecast</span>
                <span>FUELHH actuals</span>
                <span>UTC aligned</span>
                <span>
                  {data.source_counts.normalized_forecast_rows} forecasts
                  normalized
                </span>
                <span>
                  {data.source_counts.normalized_actual_wind_intervals} actual
                  intervals
                </span>
              </div>
            </section>
          </>
        )}
        <footer>
          GRIDBRICKS · WIND INTELLIGENCE{" "}
          <span>Decision support, not a trading recommendation</span>
        </footer>
      </main>
    </div>
  );
}
