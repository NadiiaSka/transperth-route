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
  Flag,
  MapPin,
  Plus,
  Search,
  Sparkles,
  Trash2,
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
  traffic_signal?: boolean;
  rowId?: number;
};

const API = (
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "")
).replace(/\/+$/, "");

function formatDistance(meters: number) {
  return meters >= 1000
    ? `${(meters / 1000).toFixed(1)} km`
    : `${Math.round(meters)} m`;
}

function formatTurnDetails(step: DriverStep) {
  const distance = formatDistance(step.distance_m);
  const maneuver = step.maneuver?.toLowerCase() ?? "";
  const action =
    ROUNDABOUT_MANEUVERS.has(maneuver) && step.roundabout_exit
      ? `Exit ${step.roundabout_exit}`
      : step.turn
        ? `${maneuver === "fork" ? "keep" : "turn"} ${step.turn}`
        : "continue";
  return `${distance} · ${action}`;
}

function displayStopName(name: string | null, fallback: string) {
  const displayName = name
    ?.replace(/\s+(?:stand|zone)\s+[a-z0-9]+$/i, "")
    .trim();
  return displayName || fallback;
}

const ROUNDABOUT_MANEUVERS = new Set([
  "roundabout",
  "rotary",
  "roundabout turn",
]);

type ManeuverContext = {
  kind: "roundabout" | "end-of-road" | "fork" | "traffic-light" | "street";
  label: string;
};

const MANEUVER_TAGS: { kind: ManeuverContext["kind"]; label: string }[] = [
  { kind: "street", label: "STREET" },
  { kind: "roundabout", label: "ROUNDABOUT" },
  { kind: "end-of-road", label: "END OF ROAD" },
  { kind: "fork", label: "FORK" },
  { kind: "traffic-light", label: "TRAFFIC LIGHT" },
];

function maneuverTagChanges(
  kind: ManeuverContext["kind"],
): Partial<DriverStep> {
  const maneuverByKind: Record<ManeuverContext["kind"], string> = {
    street: "turn",
    roundabout: "roundabout",
    "end-of-road": "end of road",
    fork: "fork",
    "traffic-light": "turn",
  };
  return {
    maneuver: maneuverByKind[kind],
    traffic_signal: kind === "traffic-light",
  };
}

function maneuverContext(step: DriverStep): ManeuverContext {
  if (step.maneuver && ROUNDABOUT_MANEUVERS.has(step.maneuver.toLowerCase())) {
    return {
      kind: "roundabout",
      label: step.roundabout_exit
        ? `ROUNDABOUT · EXIT ${step.roundabout_exit}`
        : "ROUNDABOUT",
    };
  }
  if (step.maneuver === "end of road") {
    return { kind: "end-of-road", label: "END OF ROAD" };
  }
  if (step.maneuver === "fork") {
    return { kind: "fork", label: "FORK" };
  }
  if (step.traffic_signal) {
    return { kind: "traffic-light", label: "TRAFFIC LIGHT" };
  }
  return { kind: "street", label: "STREET" };
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
  const [loading, setLoading] = useState(false);
  const [buildingDirections, setBuildingDirections] = useState(false);
  const [error, setError] = useState("");
  const [built, setBuilt] = useState(false);
  const patternPickerRef = useRef<HTMLDivElement | null>(null);
  const rowIdRef = useRef(1);
  const stepsCacheRef = useRef<Map<string, DriverStep[]>>(new Map());
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
    if (!API) {
      setError(
        "Backend URL is not configured. Set VITE_API_BASE_URL in Vercel and redeploy.",
      );
      return;
    }

    setLoading(true);
    setError("");
    setVariants([]);
    setSelectedTrip("");
    setSteps([]);
    stepsCacheRef.current.clear();
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
      const sortedVariants = [...(payload as RouteVariant[])].sort(
        (a, b) => b.trip_count - a.trip_count,
      );
      setVariants(sortedVariants);
      if (sortedVariants[0]) setRouteMapLoading(true);
      setSelectedTrip(sortedVariants[0]?.sample_trip_id ?? "");
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
    setBuildingDirections(true);
    setError("");
    setSteps([]);
    setBuilt(false);
    try {
      const response = await fetch(
        `${API}/api/trips/${encodeURIComponent(selectedTrip)}/steps?ai=false`,
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? "Could not build directions.");
      const builtSteps = (payload as DriverStep[]).map((step: DriverStep) => ({
        ...step,
        instruction: formatTurnDetails(step),
        rowId: rowIdRef.current++,
      }));
      stepsCacheRef.current.set(selectedTrip, builtSteps);
      setSteps(builtSteps);
      setBuilt(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not connect to the routing service.",
      );
    } finally {
      setLoading(false);
      setBuildingDirections(false);
    }
  }

  function chooseVariant(variant: RouteVariant) {
    if (built && selectedTrip) {
      stepsCacheRef.current.set(selectedTrip, steps);
    }
    const cached = stepsCacheRef.current.get(variant.sample_trip_id);
    setSelectedTrip(variant.sample_trip_id);
    setSteps(cached ?? []);
    setRouteShape([]);
    setRouteMapLoading(true);
    setRouteMapError("");
    setBuilt(Boolean(cached));
    setPatternOpen(false);
  }

  function updateStep(stepNumber: number, changes: Partial<DriverStep>) {
    setSteps((current) =>
      current.map((step) =>
        step.step === stepNumber ? { ...step, ...changes } : step,
      ),
    );
  }

  function renumberRows(list: DriverStep[]) {
    return list.map((step, index) => ({ ...step, step: index + 1 }));
  }

  function insertRow(afterStep: number | null) {
    setSteps((current) => {
      const index =
        afterStep === null
          ? 0
          : current.findIndex((step) => step.step === afterStep) + 1;
      const previous = current[index - 1];
      const emptyRow: DriverStep = {
        step: 0,
        type: "custom",
        turn: null,
        instruction: "",
        maneuver: null,
        modifier: null,
        road: null,
        roundabout_exit: null,
        distance_m: 0,
        cumulative_m: previous?.cumulative_m ?? 0,
        rowId: rowIdRef.current++,
      };
      return renumberRows([
        ...current.slice(0, index),
        emptyRow,
        ...current.slice(index),
      ]);
    });
  }

  function deleteRow(stepNumber: number) {
    setSteps((current) =>
      renumberRows(current.filter((step) => step.step !== stepNumber)),
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
                <Sparkles
                  className={
                    buildingDirections ? "build-button-sparkles" : undefined
                  }
                  size={16}
                />{" "}
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
          </div>

          {steps.length > 0 ? (
            <div className="table-wrap">
              <table className="directions-table">
                <thead>
                  <tr>
                    <th className="col-turn">TURN</th>
                    <th className="col-street">STREET / LANDMARK</th>
                    <th>INSTRUCTIONS</th>
                    <th className="col-actions">
                      <button
                        type="button"
                        className="header-add-row"
                        aria-label="Add empty row at start"
                        title="Add empty row at start"
                        onClick={() => insertRow(null)}
                      >
                        <Plus size={14} />
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {activeVariant && (
                    <tr className="endpoint-row endpoint-start">
                      <td>
                        <span className="endpoint-icon" aria-hidden="true">
                          <Flag size={17} />
                        </span>
                      </td>
                      <td className="street-cell">
                        <span className="endpoint-title">Start</span>
                      </td>
                      <td className="endpoint-detail" colSpan={2}>
                        Start from{" "}
                        {displayStopName(
                          activeVariant.origin_stop,
                          "Origin unavailable",
                        )}
                      </td>
                    </tr>
                  )}
                  {steps.map((step) => {
                    const context = maneuverContext(step);
                    return (
                      <tr
                        className={`direction-${step.turn?.toLowerCase() ?? "straight"} context-${context.kind}`}
                        key={step.rowId ?? step.step}
                      >
                        <td className="turn-control-cell">
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
                          <select
                            className={`maneuver-badge maneuver-tag badge-${context.kind}`}
                            aria-label={`Edit maneuver tag ${step.step}`}
                            value={context.kind}
                            onChange={(event) =>
                              updateStep(
                                step.step,
                                maneuverTagChanges(
                                  event.target.value as ManeuverContext["kind"],
                                ),
                              )
                            }
                          >
                            {MANEUVER_TAGS.map((tag) => (
                              <option key={tag.kind} value={tag.kind}>
                                {tag.label}
                              </option>
                            ))}
                          </select>
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
                        <td className="row-actions">
                          <button
                            type="button"
                            className="row-action add"
                            aria-label={`Add empty row below row ${step.step}`}
                            title="Add empty row below"
                            onClick={() => insertRow(step.step)}
                          >
                            <Plus size={15} />
                          </button>
                          <button
                            type="button"
                            className="row-action delete"
                            aria-label={`Delete row ${step.step}`}
                            title="Delete row"
                            onClick={() => deleteRow(step.step)}
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                  {activeVariant && (
                    <tr className="endpoint-row endpoint-end">
                      <td>
                        <span className="endpoint-icon" aria-hidden="true">
                          <MapPin size={17} />
                        </span>
                      </td>
                      <td className="street-cell">
                        <span className="endpoint-title">End</span>
                      </td>
                      <td className="endpoint-detail" colSpan={2}>
                        Follow to{" "}
                        {displayStopName(
                          activeVariant.destination_stop ??
                            activeVariant.headsign,
                          "Destination unavailable",
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              <div className="table-footer">
                <span>
                  <Check size={15} /> {steps.length} instructions in this
                  pattern
                </span>
                <button
                  type="button"
                  className="footer-add-row"
                  onClick={() =>
                    insertRow(steps[steps.length - 1]?.step ?? null)
                  }
                >
                  <Plus size={12} /> ADD ROW
                </button>
                <button
                  type="button"
                  className="footer-add-row mobile-add-start"
                  onClick={() => insertRow(null)}
                >
                  <Plus size={12} /> ADD AT START
                </button>
                <span>ROUTE DATA · OSM / OSRM</span>
              </div>
            </div>
          ) : (
            <div
              className={`empty-state${buildingDirections ? " is-building" : ""}`}
              role={buildingDirections ? "status" : undefined}
              aria-live={buildingDirections ? "polite" : undefined}
            >
              {buildingDirections ? (
                <>
                  <div className="build-animation-track" aria-hidden="true">
                    <span className="build-route-segment segment-one" />
                    <span className="build-route-segment segment-two" />
                    <span className="build-route-segment segment-three" />
                    <span className="build-route-point route-start">START</span>
                    <span className="build-route-point route-end">END</span>
                    <span className="build-animation-bus">
                      <BusFront size={18} strokeWidth={2.2} />
                    </span>
                  </div>
                  <strong>Following the route</strong>
                  <span>Matching streets and preparing directions</span>
                </>
              ) : (
                <>
                  <div className="empty-route-icon">
                    <ArrowDown size={22} />
                  </div>
                  <strong>
                    {loading
                      ? "Searching routes…"
                      : "Your run sheet will appear here"}
                  </strong>
                  <span>
                    {loading
                      ? "Finding available patterns."
                      : "Search for a bus route to begin."}
                  </span>
                </>
              )}
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
