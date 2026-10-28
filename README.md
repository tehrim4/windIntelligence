# Gridbricks — Wind Generation Forecast Accuracy Dashboard

A data-driven dashboard for analyzing UK wind generation forecast accuracy by comparing forecast generation against reported actual generation. The project retrieves data from the Elexon BMRS API, aligns forecast and actual values by hourly delivery timestamps, calculates accuracy metrics, and presents the results through a dashboard powered by a Python FastAPI backend.

## Project Overview

Wind generation forecasts play an important role in understanding renewable electricity production. Comparing forecast values with actual generation helps quantify forecast errors and identify systematic over-forecasting or under-forecasting.

Gridbricks provides a workflow to:

- Retrieve wind generation forecast and actual generation data.
- Normalize timestamps and generation values.
- Align hourly forecasts with hourly actual generation.
- Calculate forecast accuracy metrics.
- Visualize analysis results through a dashboard.
- Inspect API responses and data-processing behavior using debugging endpoints.
- Validate timestamp completeness for a selected evaluation period.

**Project objective:** Make wind generation forecast performance easier to understand through transparent data processing, measurable accuracy metrics, and an interactive dashboard.

## Key Features

- Date-range-based forecast analysis.
- Forecast versus actual generation comparison.
- Hourly alignment of forecast and actual values.
- MAE, RMSE, WAPE, and forecast bias calculations.
- Matched-interval coverage reporting.
- Detailed matched records, including forecast values, actual values, and errors.
- API endpoints for health checks, analysis, raw data inspection, and debugging.
- Timestamp completeness validation.

## Technology Stack

- **Frontend:** React
- **Backend:** Python and FastAPI
- **Data source:** Elexon BMRS API
- **HTTP communication:** HTTPX
- **Data processing:** Python timestamp normalization, filtering, aggregation, and metric calculations
- **Development server:** Uvicorn

The deployment platform and additional frontend libraries depend on the actual project configuration.

## Data Sources

The application uses two datasets from Elexon BMRS.

### 1. Wind Generation Forecasts — WINDFOR

Dataset documentation:

https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream

API endpoint:

`https://bmrs.elexon.co.uk/api/datasets/WINDFOR/stream`

Forecast records include fields such as:

- `startTime` — forecast delivery timestamp.
- `publishTime` — forecast publication timestamp.
- `generation` — forecast generation in megawatts (MW).

The publication timestamp helps determine whether a forecast was available by the selected cutoff time.

### 2. Actual Generation — FUELHH

Dataset documentation:

https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream

API endpoint:

`https://bmrs.elexon.co.uk/api/datasets/FUELHH/stream`

This dataset contains half-hourly generation records for multiple fuel types. The application filters the data to obtain wind generation observations for comparison with the forecast series.

Relevant fields include:

- `startTime`
- `settlementDate`
- `settlementPeriod`
- `fuelType`
- `generation`

**Measurement unit:** Generation is represented in megawatts (MW).

## Forecast Evaluation Methodology

Gridbricks evaluates existing wind generation forecasts against actual generation. It does not currently train or deploy its own wind forecasting model.

### Step 1 — Retrieve source data

The backend requests forecast and actual generation records from the Elexon BMRS API for the selected analysis period.

### Step 2 — Normalize records

The backend converts timestamps into timezone-aware UTC values and parses generation values into numeric MW measurements. Invalid or unusable observations are excluded from the calculations.

### Step 3 — Apply forecast eligibility rules

Forecasts are filtered according to delivery timestamps, publication timestamps, and the configured cutoff policy.

The implementation uses the `CUTOFF_HOUR` environment variable, which defaults to `23` UTC. The intended evaluation policy selects forecasts published by the cutoff on the day before delivery.

This prevents the evaluation from using information that would not have been available by the chosen forecast cutoff. The exact publication-selection rule should be interpreted according to the implementation and verified against the source dataset's timestamp conventions.

### Step 4 — Convert actual generation to hourly values

Forecast data is hourly, while actual generation data is half-hourly.

To compare equivalent time intervals, the backend groups half-hourly wind generation observations by hour and calculates the hourly average. Only hours containing both expected half-hourly observations are retained.

This provides a consistent hourly comparison while excluding incomplete actual-generation hours.

### Step 5 — Match forecasts with actual generation

Forecasts and actual values are matched using their normalized hourly delivery timestamps.

Only timestamps containing both a forecast and an actual value are included in the accuracy calculations.

For each matched interval:

`Forecast error = Forecast generation − Actual generation`

- Positive error means the forecast exceeded actual generation.
- Negative error means the forecast was below actual generation.
- Zero error means forecast and actual generation were equal.

### Step 6 — Calculate accuracy metrics

The backend calculates error metrics from the matched observations and returns the results to the frontend.

## Forecast Accuracy Metrics

Let:

- \(F_i\) = forecast generation for interval \(i\)
- \(A_i\) = actual generation for interval \(i\)
- \(e_i = F_i - A_i\)
- \(N\) = number of matched intervals

### Mean Absolute Error (MAE)

\[
\mathrm{MAE}=\frac{1}{N}\sum_{i=1}^{N}|F_i-A_i|
\]

MAE measures the average absolute difference between forecast and actual generation, in MW. Lower values indicate smaller average errors.

### Root Mean Squared Error (RMSE)

\[
\mathrm{RMSE}=\sqrt{\frac{1}{N}\sum_{i=1}^{N}(F_i-A_i)^2}
\]

RMSE penalizes larger errors more heavily because errors are squared before averaging. Lower values generally indicate better forecast accuracy.

### Weighted Absolute Percentage Error (WAPE)

\[
\mathrm{WAPE}=
\frac{\sum_{i=1}^{N}|F_i-A_i|}
{\sum_{i=1}^{N}|A_i|}\times100
\]

WAPE expresses the sum of absolute forecast errors as a percentage of total absolute actual generation. Lower values indicate better accuracy when the denominator is meaningful and non-zero.

### Forecast Bias

\[
\mathrm{Bias}=\frac{1}{N}\sum_{i=1}^{N}(F_i-A_i)
\]

Bias measures the average signed forecast error.

- Positive bias indicates average over-forecasting.
- Negative bias indicates average under-forecasting.
- Bias near zero indicates little average directional error, although individual errors may still be large.

### Matched-Interval Coverage

Coverage measures the proportion of actual intervals that have a corresponding eligible forecast:

\[
\mathrm{Coverage}=
\frac{\text{Matched intervals}}
{\text{Actual intervals}}\times100
\]

Coverage must be interpreted with the requested date range, the actual intervals included in the denominator, and the timestamps returned by the API.

## Verified Example Results

**Evaluation period:** January 6–7, 2026 (UTC)

An automated timestamp validation script checked the hourly records returned by the analysis API. It confirmed the following:

- First timestamp: `2026-01-06T00:00:00Z`
- Last timestamp: `2026-01-07T23:00:00Z`
- Expected hourly timestamps: 48
- Missing hourly timestamps: 0
- Unexpected timestamps: 0
- Duplicate timestamps: 0
- Full 48-hour timestamp coverage: confirmed

The current API response reports these forecast accuracy metrics:

| Metric | Result |
|---|---:|
| Matched hourly intervals | 48 |
| Actual intervals reported by API | 48 |
| Reported matched-interval coverage | 100.000% |
| Mean Absolute Error (MAE) | 1,561.271 MW |
| Root Mean Squared Error (RMSE) | 2,015.920 MW |
| Weighted Absolute Percentage Error (WAPE) | 14.462% |
| Mean forecast bias | +66.854 MW |

The positive mean bias indicates that forecasts were higher than actual generation on average under the project's forecast-minus-actual error convention.

These results describe the selected historical period only. Timestamp validation confirms that all expected hourly timestamps are present in the returned analysis records; it does not independently validate the underlying source data or the forecast publication cutoff policy.

## Backend API Endpoints

The FastAPI backend exposes the following endpoints.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Checks whether the backend is responding. |
| `GET /api/analysis?from=YYYY-MM-DD&to=YYYY-MM-DD` | Returns forecast accuracy metrics and matched records for the requested period. |
| `GET /api/forecast` | Retrieves or inspects forecast records for a selected period. |
| `GET /api/actual` | Retrieves or inspects actual generation records for a selected period. |
| `GET /api/debug` | Reports raw data counts, normalized samples, and forecast eligibility details. |

### Example Analysis Request

```http
GET /api/analysis?from=2026-01-06&to=2026-01-07
```

### Local API Documentation

When the backend is running locally, interactive API documentation is available at:

http://127.0.0.1:8000/docs

## Local Setup and Installation

### Prerequisites

- Python
- Node.js and npm
- Internet access to retrieve data from Elexon BMRS
- The project's frontend and backend source code

### 1. Start the Backend

Open a terminal in the project directory and navigate to the backend folder:

```powershell
cd backend
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the API server:

```powershell
uvicorn app.main:app --reload --port 8000
```

The backend should be available at:

http://127.0.0.1:8000

### 2. Start the Frontend

Open a separate terminal and navigate to the frontend directory.

If the project uses a folder named `frontend`:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by the frontend development server.

**Note:** Adjust the folder names and commands if the repository uses a different frontend structure or package configuration.

## Testing and Validation

The project supports manual API verification and timestamp completeness checks.

Recommended checks include:

1. Confirm that `/api/health` responds successfully.
2. Confirm that the analysis endpoint returns valid JSON.
3. Check that forecast and actual values are present for matched records.
4. Verify that timestamps are in UTC and ordered correctly.
5. Validate that the expected number of hourly timestamps is present.
6. Check for missing or duplicate timestamps.
7. Confirm that the dashboard displays the API's metric values correctly.

For the January 6–7, 2026 example, an automated coverage check confirmed all 48 expected hourly timestamps were present exactly once.

## Limitations

### Forecast cutoff assumptions

Accuracy results depend on the publication cutoff and forecast-selection logic. The selected forecast must be available by the intended cutoff to support a valid forecast evaluation.

### Different data resolutions

Forecasts are hourly and actual observations are half-hourly. Averaging actual observations into hourly values loses some short-term variation.

### Incomplete observations

Hours with fewer than two half-hourly actual readings are excluded. Missing source observations may reduce the number of matched intervals.

### Historical sample size

A two-day evaluation is useful for demonstrating the workflow, but it is not enough to establish long-term forecasting performance across different seasons, weather conditions, and generation levels.

### Source-data quality

Missing records, revised publications, delayed updates, or changes to the upstream API may affect the analysis.

### Metric interpretation

MAE and RMSE are expressed in MW and depend on generation scale. WAPE may be unstable when total actual generation is very low. Bias can be near zero even when individual forecast errors are large.

### Forecast evaluation rather than forecast generation

The application compares existing forecasts with actual generation. It does not independently predict future wind generation.

## Potential Future Improvements

- Evaluate longer historical periods and different forecast horizons.
- Validate forecast publication timing against the official dataset definitions.
- Add daily and weekly accuracy summaries.
- Display forecast-versus-actual charts and error distributions.
- Improve caching, retry behavior, and upstream API error handling.
- Add automated tests for timestamp alignment and metric calculations.
- Add monitoring for data freshness and missing intervals.
- Document the production deployment configuration.

## Conclusion

Gridbricks demonstrates an end-to-end approach to renewable-energy forecast evaluation by retrieving operational datasets, aligning observations with different time resolutions, calculating interpretable accuracy metrics, and presenting the results through an API-backed dashboard.

The verified January 6–7, 2026 example confirms complete hourly timestamp coverage for the returned 48-hour analysis period. Accuracy results should still be interpreted in the context of forecast publication timing, source-data quality, and the selected evaluation period.
