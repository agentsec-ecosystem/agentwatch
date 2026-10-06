/**
 * Operator Console page — identity/attribution, SIEM sink health, and detector telemetry.
 *
 * ## Purpose (M27 UI-2)
 * One operator view that renders the three v0.2.0 governance signals:
 * - **Identity & attribution** (IDN-1/S14): per-session agent identity, principal,
 *   delegation chain, and approval decision.
 * - **SIEM sink health** (S10): configured sink targets and a visible `degraded` state.
 * - **Detector telemetry** (DET-5): content-free fired / suppressed / false-positive markers.
 *
 * ## Data flow
 * Three `useAsync` calls (`getAttribution`, `getSiemHealth`, `getDetectorTelemetry`),
 * each read-only over a local file; absent data renders an empty/neutral state.
 */

import { useAsync } from "../hooks/useAsync";
import { api } from "../api/client";
import {
  Layout,
  PageHeader,
  PageBody,
  ErrorState,
  EmptyState,
  SkeletonList,
  TimeDisplay,
} from "../components/ui";

/** Outcome colour class (never colour-only: the label is always shown too). */
function outcomeClass(outcome: string): string {
  if (outcome === "fired") return "text-rose-400";
  if (outcome === "suppressed") return "text-slate-400";
  if (outcome === "false-positive") return "text-amber-400";
  return "text-slate-400";
}

function SectionTitle({ children }: { children: string }) {
  return <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">{children}</h2>;
}

export default function OperatorPage() {
  const attribution = useAsync(() => api.getAttribution(), []);
  const siem = useAsync(() => api.getSiemHealth(), []);
  const telemetry = useAsync(() => api.getDetectorTelemetry(), []);

  const sessions = attribution.data?.items ?? [];
  const targets = siem.data?.targets ?? [];
  const markers = telemetry.data?.items ?? [];

  return (
    <Layout>
      <PageHeader
        title="Operator Console"
        subtitle="Identity & attribution, SIEM sink health, and content-free detector telemetry"
      />
      <PageBody>
        <section aria-labelledby="attribution-heading" className="mb-8">
          <h2 id="attribution-heading" className="sr-only">Identity and attribution</h2>
          <SectionTitle>Identity &amp; attribution</SectionTitle>
          {attribution.loading && <SkeletonList rows={3} />}
          {!attribution.loading && attribution.error && (
            <ErrorState message={attribution.error} onRetry={attribution.refetch} />
          )}
          {!attribution.loading && !attribution.error && sessions.length === 0 && (
            <EmptyState title="No attribution yet" description="No agentwatch records are available to attribute." />
          )}
          {!attribution.loading && !attribution.error && sessions.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Per-session identity and approval attribution.</caption>
                <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th scope="col" className="px-4 py-3">Session</th>
                    <th scope="col" className="px-4 py-3">Identity</th>
                    <th scope="col" className="px-4 py-3">Principal</th>
                    <th scope="col" className="px-4 py-3">Approval</th>
                    <th scope="col" className="px-4 py-3">Delegation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {sessions.map((row) => (
                    <tr key={row.session_id} className="text-slate-300">
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{row.session_id}</td>
                      <td className="px-4 py-3 font-medium text-slate-100">{row.identity ?? "unknown"}</td>
                      <td className="px-4 py-3">{row.principal ?? "—"}</td>
                      <td className="px-4 py-3">{row.approval ?? "unknown"}</td>
                      <td className="px-4 py-3">
                        {row.delegation_chain && row.delegation_chain.length > 0
                          ? row.delegation_chain.join(" → ")
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section aria-labelledby="siem-heading" className="mb-8">
          <h2 id="siem-heading" className="sr-only">SIEM sink health</h2>
          <SectionTitle>SIEM sink health</SectionTitle>
          {siem.loading && <SkeletonList rows={1} />}
          {!siem.loading && siem.error && <ErrorState message={siem.error} onRetry={siem.refetch} />}
          {!siem.loading && !siem.error && (
            <div className="rounded-xl border border-slate-800 p-4 text-sm text-slate-300">
              {targets.length === 0 ? (
                <p>No SIEM sinks configured (events-only forwarding is opt-in).</p>
              ) : (
                <ul className="list-disc pl-5">
                  {targets.map((target) => (
                    <li key={target} className="font-mono text-xs">{target}</li>
                  ))}
                </ul>
              )}
              <p className={`mt-2 font-medium ${siem.data?.degraded ? "text-amber-400" : "text-emerald-400"}`}>
                {siem.data?.degraded ? `degraded${siem.data?.last_error ? `: ${siem.data.last_error}` : ""}` : "healthy"}
              </p>
            </div>
          )}
        </section>

        <section aria-labelledby="telemetry-heading">
          <h2 id="telemetry-heading" className="sr-only">Detector telemetry</h2>
          <SectionTitle>Detector telemetry</SectionTitle>
          {telemetry.loading && <SkeletonList rows={3} />}
          {!telemetry.loading && telemetry.error && (
            <ErrorState message={telemetry.error} onRetry={telemetry.refetch} />
          )}
          {!telemetry.loading && !telemetry.error && markers.length === 0 && (
            <EmptyState
              title="No detector telemetry yet"
              description="Markers are opt-in and content-free; enable local detector telemetry to populate this view."
            />
          )}
          {!telemetry.loading && !telemetry.error && markers.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Content-free detector telemetry (detector, outcome, severity, time).</caption>
                <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th scope="col" className="px-4 py-3">Detector</th>
                    <th scope="col" className="px-4 py-3">Outcome</th>
                    <th scope="col" className="px-4 py-3">Severity</th>
                    <th scope="col" className="px-4 py-3">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {markers.map((marker, index) => (
                    <tr key={`${marker.detector}-${marker.at}-${index}`} className="text-slate-300">
                      <td className="px-4 py-3 font-medium text-slate-100">{marker.detector}</td>
                      <td className={`px-4 py-3 font-medium ${outcomeClass(marker.outcome)}`}>{marker.outcome}</td>
                      <td className="px-4 py-3">{marker.severity ?? "—"}</td>
                      <td className="px-4 py-3">
                        <TimeDisplay iso={marker.at} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </PageBody>
    </Layout>
  );
}
