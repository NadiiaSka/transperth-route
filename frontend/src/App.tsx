import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BusFront,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Search,
  Sparkles,
} from "lucide-react";
import "./route-desk.css";
import { RouteMap } from "./RouteMap";

type RouteVariant = {
  route_id: string;
  route_number: string;
  agency_id: string | null;
  direction_id: number | null;
  headsign: string | null;
  shape_id: string | null;
  trip_count: number;
  sample_trip_id: string;
  origin_stop: string | null;
  destination_stop: string | null;
};

type DriverStep = {
  step: number;
  type: string;
  turn: string | null;
  instruction: string;
  maneuver: string | null;
  modifier: string | null;
  road: string | null;
  roundabout_exit: number | null;
  distance_m: number;
  cumulative_m: number;
};

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function formatDistance(meters: number) {
  return meters >= 1000
    ? `${(meters / 1000).toFixed(1)} km`
    : `${Math.round(meters)} m`;
}

function displayStopName(name: string | null, fallback: string) {
  const displayName = name
    ?.replace(/\s+(?:stand|zone)\s+[a-z0-9]+$/i, "")
    .trim();
  return displayName || fallback;
}

function App() {
  const [routeNumber, setRouteNumber] = useState("");
  const [variants, setVariants] = useState<RouteVariant[]>([]);
  const [selectedTrip, setSelectedTrip] = useState("");
  const [patternOpen, setPatternOpen] = useState(false);
  const [steps, setSteps] = useState<DriverStep[]>([]);
  const [routeShape, setRouteShape] = useState<[number, number][]>([]);
  const [routeMapLoading, setRouteMapLoading] = useState(false);
  const [routeMapError, setRouteMapError] = useState("");
  const [useAi, setUseAi] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [built, setBuilt] = useState(false);
  const patternPickerRef = useRef<HTMLDivElement | null>(null);
  const patternTriggerRef = useRef<HTMLButtonElement | null>(null);
  const patternOptionRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const selectedVariantIndex = variants.findIndex(
    (variant) => variant.sample_trip_id === selectedTrip,
  );

  useEffect(() => {
    if (patternOpen) patternOptionRefs.current[selectedVariantIndex]?.focus();
  }, [patternOpen, selectedVariantIndex]);

  useEffect(() => {
    if (!patternOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (!patternPickerRef.current?.contains(event.target as Node)) {
        setPatternOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setPatternOpen(false);
        patternTriggerRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [patternOpen]);

  useEffect(() => {
    if (!selectedTrip) return;

    const controller = new AbortController();

    async function loadRouteShape() {
      try {
        const response = await fetch(
          `${API}/api/trips/${encodeURIComponent(selectedTrip)}/pattern`,
          { signal: controller.signal },
        );
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail ?? "Could not load this route line.");
        }
        setRouteShape(payload.shape ?? []);
      } catch (err) {
        if (!controller.signal.aborted) {
          setRouteMapError(
            err instanceof Error
              ? err.message
              : "Could not load this route line.",
          );
        }
      } finally {
        if (!controller.signal.aborted) setRouteMapLoading(false);
      }
    }

    void loadRouteShape();
    return () => controller.abort();
  }, [selectedTrip]);

  async function searchRoutes(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const number = routeNumber.trim();
    if (!number) return;

    setLoading(true);
    setError("");
    setVariants([]);
    setSelectedTrip("");
    setSteps([]);
    setRouteShape([]);
    setRouteMapLoading(false);
    setRouteMapError("");
    setBuilt(false);
    try {
      const response = await fetch(
        `${API}/api/routes?number=${encodeURIComponent(number)}`,
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? "Could not find this route.");
      setVariants(payload);
      if (payload[0]) setRouteMapLoading(true);
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

  function chooseVariant(variant: RouteVariant) {
    setSelectedTrip(variant.sample_trip_id);
    setSteps([]);
    setRouteShape([]);
    setRouteMapLoading(true);
    setRouteMapError("");
    setBuilt(false);
    setPatternOpen(false);
  }

  function updateStep(stepNumber: number, changes: Partial<DriverStep>) {
    setSteps((current) =>
      current.map((step) =>
        step.step === stepNumber ? { ...step, ...changes } : step,
      ),
    );
  }

  const activeVariant = variants.find(
    (variant) => variant.sample_trip_id === selectedTrip,
  );

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
              <span className="field-label" id="route-variant-label">
                DIRECTION &amp; PATTERN
              </span>
              <div className="pattern-picker" ref={patternPickerRef}>
                <button
                  ref={patternTriggerRef}
                  className="pattern-trigger"
                  type="button"
                  aria-labelledby="route-variant-label"
                  aria-haspopup="listbox"
                  aria-expanded={patternOpen}
                  aria-controls="route-pattern-options"
                  onClick={() => setPatternOpen((open) => !open)}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowDown" && !patternOpen) {
                      event.preventDefault();
                      setPatternOpen(true);
                    }
                  }}
                >
                  <span className="pattern-trigger-copy">
                    <strong>
                      {activeVariant
                        ? `${displayStopName(activeVariant.origin_stop, "unknown start")} to ${displayStopName(activeVariant.destination_stop ?? activeVariant.headsign, "unknown destination")}`
                        : "Select a route pattern"}
                    </strong>
                    <span>
                      {activeVariant?.agency_id ?? "Operator"} ·{" "}
                      {activeVariant?.trip_count ?? 0} trips
                    </span>
                  </span>
                  <ChevronDown size={17} />
                </button>
                {patternOpen && (
                  <div
                    className="pattern-options"
                    id="route-pattern-options"
                    role="listbox"
                    aria-labelledby="route-variant-label"
                  >
                    {variants.map((variant, index) => {
                      const origin = displayStopName(
                        variant.origin_stop,
                        "unknown start",
                      );
                      const destination = displayStopName(
                        variant.destination_stop ?? variant.headsign,
                        "unknown destination",
                      );
                      const selected = variant.sample_trip_id === selectedTrip;

                      return (
                        <button
                          key={variant.sample_trip_id}
                          ref={(element) => {
                            patternOptionRefs.current[index] = element;
                          }}
                          className="pattern-option"
                          type="button"
                          role="option"
                          aria-selected={selected}
                          tabIndex={selected ? 0 : -1}
                          onClick={() => chooseVariant(variant)}
                          onKeyDown={(event) => {
                            if (event.key === "ArrowDown") {
                              event.preventDefault();
                              patternOptionRefs.current[
                                Math.min(index + 1, variants.length - 1)
                              ]?.focus();
                            } else if (event.key === "ArrowUp") {
                              event.preventDefault();
                              patternOptionRefs.current[
                                Math.max(index - 1, 0)
                              ]?.focus();
                            }
                          }}
                        >
                          <span className="pattern-option-route">
                            <strong>{origin}</strong>
                            <ArrowRight size={14} />
                            <strong>{destination}</strong>
                          </span>
                          <span className="pattern-option-meta">
                            {variant.agency_id ?? "Operator"} ·{" "}
                            {variant.trip_count} trips
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
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
              <strong className="summary-route">
                <span>
                  {displayStopName(
                    activeVariant.origin_stop,
                    "Origin unavailable",
                  )}
                </span>
                <ArrowRight size={15} />
                <span>
                  {displayStopName(
                    activeVariant.destination_stop ?? activeVariant.headsign,
                    "Destination unavailable",
                  )}
                </span>
              </strong>
            </div>
            <div className="summary-stats">
              <span>
                <ArrowUp size={15} /> {steps.length || "—"} directions
              </span>
              <span>
                <Clock3 size={15} /> {activeVariant.trip_count} trips
              </span>
            </div>
          </section>
        )}

        {activeVariant && (
          <section className="route-map-panel" aria-label="Route line map">
            <div className="route-map-heading">
              <span>ROUTE LINE</span>
              <span>
                {activeVariant.route_number} · {routeShape.length || "—"} points
              </span>
            </div>
            <div className="route-map-frame">
              <RouteMap coordinates={routeShape} />
              {(routeMapLoading || routeMapError || routeShape.length < 2) && (
                <div
                  className="route-map-message"
                  role={routeMapError ? "alert" : undefined}
                >
                  {routeMapError ||
                    (routeMapLoading
                      ? "Loading route line…"
                      : "Route line unavailable")}
                </div>
              )}
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
                    : "Build a concise list of turns and street changes."}
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
                    <th className="col-turn">TURN</th>
                    <th className="col-street">STREET / LANDMARK</th>
                    <th>
                      TURN / ROUTE DETAILS{" "}
                      <span className="edit-hint">EDITABLE</span>
                    </th>
                    <th className="col-distance">DISTANCE</th>
                  </tr>
                </thead>
                <tbody>
                  {steps.map((step) => (
                    <tr
                      className={`direction-${step.turn?.toLowerCase() ?? "straight"}`}
                      key={step.step}
                    >
                      <td>
                        <select
                          className="turn-cell"
                          aria-label={`Turn direction ${step.step}`}
                          value={step.turn ?? ""}
                          onChange={(event) =>
                            updateStep(step.step, {
                              turn: event.target.value || null,
                            })
                          }
                        >
                          <option value="">—</option>
                          <option value="L">L</option>
                          <option value="R">R</option>
                        </select>
                      </td>
                      <td className="street-cell">
                        <input
                          aria-label={`Edit street or landmark ${step.step}`}
                          value={step.road ?? ""}
                          placeholder="Street name unavailable"
                          onChange={(event) =>
                            updateStep(step.step, {
                              road: event.target.value || null,
                            })
                          }
                        />
                      </td>
                      <td className="details-cell">
                        <input
                          aria-label={`Edit turn details ${step.step}`}
                          value={step.instruction}
                          onChange={(event) =>
                            updateStep(step.step, {
                              instruction: event.target.value,
                            })
                          }
                        />
                      </td>
                      <td className="distance-cell">
                        {formatDistance(step.distance_m)}
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
                  ? "Reading road maneuvers and street changes."
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
