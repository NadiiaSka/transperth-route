import { useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BusFront,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  MapPin,
  Search,
  Sparkles,
} from "lucide-react";
import "./route-desk.css";

type RouteVariant = {
  route_id: string;
  route_number: string;
  agency_id: string | null;
  direction_id: number | null;
  headsign: string | null;
  shape_id: string | null;
  trip_count: number;
  sample_trip_id: string;
};

type DriverStep = {
  step: number;
  type: string;
  instruction: string;
  maneuver: string | null;
  modifier: string | null;
  road: string | null;
  distance_m: number;
  cumulative_m: number;
  stop_sequence: number | null;
  stop_code: string | null;
  stop_name: string | null;
};

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function formatDistance(meters: number) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${meters} m`;
}

function App() {
  const [routeNumber, setRouteNumber] = useState("");
  const [variants, setVariants] = useState<RouteVariant[]>([]);
  const [selectedTrip, setSelectedTrip] = useState("");
  const [steps, setSteps] = useState<DriverStep[]>([]);
  const [useAi, setUseAi] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [built, setBuilt] = useState(false);

  async function searchRoutes(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const number = routeNumber.trim();
    if (!number) return;

    setLoading(true);
    setError("");
    setVariants([]);
    setSelectedTrip("");
    setSteps([]);
    setBuilt(false);
    try {
      const response = await fetch(
        `${API}/api/routes?number=${encodeURIComponent(number)}`,
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? "Could not find this route.");
      setVariants(payload);
      setSelectedTrip(payload[0]?.sample_trip_id ?? "");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to the route service.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function buildDirections() {
    if (!selectedTrip) return;
    setLoading(true);
    setError("");
    setSteps([]);
    setBuilt(false);
    try {
      const response = await fetch(
        `${API}/api/trips/${encodeURIComponent(selectedTrip)}/steps?ai=${useAi}`,
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? "Could not build directions.");
      setSteps(payload);
      setBuilt(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to the routing service.",
      );
    } finally {
      setLoading(false);
    }
  }

  function updateInstruction(stepNumber: number, instruction: string) {
    setSteps((current) =>
      current.map((step) =>
        step.step === stepNumber ? { ...step, instruction } : step,
      ),
    );
  }

  const activeVariant = variants.find(
    (variant) => variant.sample_trip_id === selectedTrip,
  );
  const drivingDistance = steps.reduce(
    (total, step) => total + step.distance_m,
    0,
  );
  const stopCount = steps.filter((step) => step.type === "stop").length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Transperth Route Desk home">
          <span className="brand-mark">
            <BusFront size={19} strokeWidth={2.4} />
          </span>
          <span>
            TRANSIT<span className="brand-light"> / ROUTE DESK</span>
          </span>
        </a>
        <div className="topbar-meta">
          <span className="status-dot" /> ROUTE OPERATIONS{" "}
          <span className="meta-divider">/</span> PERTH, WA
        </div>
      </header>

      <main id="top" className="workspace">
        <section className="intro-row">
          <div>
            <p className="eyebrow">
              <span className="eyebrow-line" /> DRIVER ROUTE BUILDER
            </p>
            <h1>
              Make every turn
              <br />
              <span>clear.</span>
            </h1>
          </div>
          <p className="intro-copy">
            Build a road-level run sheet from Transperth route data. Review each
            instruction before it reaches the cab.
          </p>
        </section>

        <section className="search-panel" aria-label="Find a bus route">
          <div className="panel-heading">
            <div className="step-index">01</div>
            <div>
              <h2>Find a route</h2>
              <p>Search by route number, then choose direction and pattern.</p>
            </div>
          </div>
          <form className="route-form" onSubmit={searchRoutes}>
            <label className="field-label" htmlFor="route-number">
              BUS ROUTE
            </label>
            <div className="form-controls">
              <div className="route-input-wrap">
                <BusFront size={18} />
                <input
                  id="route-number"
                  value={routeNumber}
                  onChange={(event) => setRouteNumber(event.target.value)}
                  placeholder="e.g. 950"
                  inputMode="numeric"
                />
              </div>
              <button
                className="primary-button"
                type="submit"
                disabled={loading || !routeNumber.trim()}
              >
                <Search size={16} /> Find route
              </button>
            </div>
          </form>
          {variants.length > 0 && (
            <div className="variant-row">
              <label className="field-label" htmlFor="route-variant">
                DIRECTION &amp; PATTERN
              </label>
              <div className="select-wrap">
                <select
                  id="route-variant"
                  value={selectedTrip}
                  onChange={(event) => {
                    setSelectedTrip(event.target.value);
                    setSteps([]);
                    setBuilt(false);
                  }}
                >
                  {variants.map((variant) => (
                    <option
                      key={variant.sample_trip_id}
                      value={variant.sample_trip_id}
                    >
                      {variant.agency_id ?? "Operator"} ·{" "}
                      {variant.headsign ?? "Route pattern"} ·{" "}
                      {variant.trip_count} trips
                    </option>
                  ))}
                </select>
                <ChevronDown size={17} />
              </div>
              <button
                className="build-button"
                type="button"
                onClick={buildDirections}
                disabled={loading || !selectedTrip}
              >
                <Sparkles size={16} />{" "}
                {loading ? "Building…" : "Build directions"}
              </button>
            </div>
          )}
          {error && (
            <div className="error-message" role="alert">
              <CircleAlert size={17} /> {error}
            </div>
          )}
        </section>

        {activeVariant && (
          <section className="run-summary" aria-label="Selected route">
            <div className="route-badge">
              <span>ROUTE</span>
              <strong>{activeVariant.route_number}</strong>
            </div>
            <div className="summary-main">
              <span className="summary-kicker">
                {activeVariant.agency_id ?? "TRANSPERTH"} <span>·</span>{" "}
                DIRECTION {activeVariant.direction_id ?? "—"}
              </span>
              <strong>
                {activeVariant.headsign ?? "Selected route pattern"}
              </strong>
            </div>
            <div className="summary-stats">
              <span>
                <MapPin size={15} /> {stopCount || "—"} stops
              </span>
              <span>
                <ArrowRight size={15} />{" "}
                {steps.length ? formatDistance(drivingDistance) : "—"}
              </span>
              <span>
                <Clock3 size={15} /> {activeVariant.trip_count} trips
              </span>
            </div>
          </section>
        )}

        <section className="directions-section">
          <div className="section-title-row">
            <div className="panel-heading compact-heading">
              <div className="step-index">02</div>
              <div>
                <h2>Driver directions</h2>
                <p>
                  {built
                    ? "Review and edit the route instructions below."
                    : "Choose a route pattern and build the driving sequence."}
                </p>
              </div>
            </div>
            <label className="ai-toggle">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(event) => setUseAi(event.target.checked)}
              />
              <span className="toggle-track" />
              <span>
                <Sparkles size={14} /> AI wording
              </span>
            </label>
          </div>

          {steps.length > 0 ? (
            <div className="table-wrap">
              <table className="directions-table">
                <thead>
                  <tr>
                    <th className="col-step">NO.</th>
                    <th className="col-action">ACTION</th>
                    <th>
                      DRIVER INSTRUCTION{" "}
                      <span className="edit-hint">EDITABLE</span>
                    </th>
                    <th className="col-distance">DISTANCE</th>
                    <th className="col-total">CUMULATIVE</th>
                  </tr>
                </thead>
                <tbody>
                  {steps.map((step) => (
                    <tr
                      className={step.type === "stop" ? "stop-row" : ""}
                      key={step.step}
                    >
                      <td className="step-number">
                        {String(step.step).padStart(2, "0")}
                      </td>
                      <td>
                        <span className={`action-icon action-${step.type}`}>
                          {step.type === "stop" ? (
                            <MapPin size={15} />
                          ) : step.modifier?.includes("left") ? (
                            <ArrowLeft size={15} />
                          ) : step.modifier?.includes("right") ? (
                            <ArrowRight size={15} />
                          ) : (
                            <ArrowUp size={15} />
                          )}
                        </span>
                      </td>
                      <td className="instruction-cell">
                        {step.type === "stop" ? (
                          <div className="stop-instruction">
                            <strong>{step.instruction}</strong>
                            {step.stop_code && (
                              <span>STOP {step.stop_code}</span>
                            )}
                          </div>
                        ) : (
                          <input
                            aria-label={`Edit instruction ${step.step}`}
                            value={step.instruction}
                            onChange={(event) =>
                              updateInstruction(step.step, event.target.value)
                            }
                          />
                        )}
                      </td>
                      <td className="numeric-cell">
                        {step.distance_m
                          ? formatDistance(step.distance_m)
                          : "—"}
                      </td>
                      <td className="numeric-cell cumulative-cell">
                        {step.cumulative_m
                          ? formatDistance(step.cumulative_m)
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  <Check size={15} /> {steps.length} instructions in this
                  pattern
                </span>
                <span>ROUTE DATA · OSM / OSRM</span>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-route-icon">
                <ArrowDown size={22} />
              </div>
              <strong>
                {loading
                  ? "Building your route…"
                  : "Your run sheet will appear here"}
              </strong>
              <span>
                {loading
                  ? "Fetching road maneuvers and stop data."
                  : "Search for a bus route to begin."}
              </span>
            </div>
          )}
        </section>
        <footer className="page-footer">
          <span>TRANSIT / ROUTE DESK</span>
          <span>
            PREVIEW ONLY <i /> HUMAN REVIEW REQUIRED
          </span>
        </footer>
      </main>
    </div>
  );
}

export default App;
