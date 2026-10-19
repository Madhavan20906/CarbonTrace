import { useEffect, useMemo, useState } from "react";
import { api, type Activity, type ProjectRow, type Stats } from "../api";
import { useApp } from "../state";
import MapView, { type MapPoint } from "../components/MapView";
import { date, shortAddr, tonnes } from "../format";

const go = (hash: string) => { window.location.hash = hash; };

export default function Registry() {
  const { cfg } = useApp();
  const [stats, setStats] = useState<Stats | null>(null);
  const [projects, setProjects] = useState<ProjectRow[] | null>(null);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cfg) return;
    Promise.all([api.stats(), api.projects(), api.activity()])
      .then(([s, p, a]) => { setStats(s); setProjects(p); setActivity(a); })
      .catch((e: Error) => setError(e.message));
  }, [cfg]);

  const points = useMemo<MapPoint[]>(
    () => (projects ?? []).map((p) => ({
      id: p.id, lat: p.lat, lon: p.lon, radius: 8 + Math.min(14, Math.sqrt(p.tonnes) / 3),
      color: p.revoked ? "#d64545" : "#3fae6a", label: `#${p.id}: ${tonnes(p.tonnes)} (${p.vintage})`,
      onClick: () => go(`#/project/${p.id}`),
    })),
    [projects],
  );

  return (
    <>
      <section className="hero">
        <h1>Credits you can trace back to the ground.</h1>
        <p className="lede">
          Every credit is checked against satellite evidence before it exists. The land behind it is then locked on-chain,
          so the same forest can never be sold twice.
        </p>
        <div className="cta-row">
          <a className="btn primary" href="#/verify">Verify a project</a>
          <a className="btn" href="#/lab">Watch it catch fraud</a>
        </div>
      </section>

      <MapView points={points} height={400} label="Map of projects that have issued credits" />

      {error && <p className="notice err">{error}</p>}

      {stats && (
        <p className="ledger" aria-label="Registry totals">
          <span><b>{stats.projects}</b> projects</span>
          <span><b>{tonnes(stats.minted)}</b> issued</span>
          <span><b>{tonnes(stats.retired)}</b> retired for good</span>
          <span><b>{tonnes(stats.outstanding)}</b> available</span>
          {stats.revoked > 0 && <span className="bad"><b>{tonnes(stats.revoked)}</b> revoked</span>}
        </p>
      )}

      {projects && projects.length === 0 && (
        <div className="empty">
          <h2>No credits issued yet</h2>
          <p>Verify a project to issue the first credits, or run the fraud lab to see good and bad claims handled side by side.</p>
          <a className="btn primary" href="#/verify">Verify a project</a>
        </div>
      )}

      {projects && projects.length > 0 && (
        <div className="split">
          <section>
            <h2>Projects</h2>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Project</th><th>Year</th><th>Score</th><th className="num">Issued</th><th className="num">Retired</th><th>Status</th></tr></thead>
                <tbody>
                  {projects.map((p) => (
                    <tr key={p.id}>
                      <td><a href={`#/project/${p.id}`}>#{p.id}</a> <span className="muted">{shortAddr(p.developer)}</span></td>
                      <td>{p.vintage}</td>
                      <td>{p.scoreBps / 100}</td>
                      <td className="num">{p.tonnes.toLocaleString("en-US")}</td>
                      <td className="num">{p.retired.toLocaleString("en-US")}</td>
                      <td>{p.revoked ? <span className="tag bad">Revoked</span> : <span className="tag good">Active</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section>
            <h2>Latest activity</h2>
            <ol className="feed">
              {activity.map((a) => (
                <li key={`${a.tx}-${a.type}`}>
                  <a href={`#/project/${a.projectId}`}>Project #{a.projectId}</a>{" "}
                  {a.type === "minted" && <>issued {tonnes(a.amount ?? 0)} to {shortAddr(a.account ?? "")}</>}
                  {a.type === "retired" && <>retired {tonnes(a.amount ?? 0)} for {a.beneficiary || "an unnamed buyer"}{a.reason ? `: ${a.reason}` : ""}</>}
                  {a.type === "revoked" && <span className="bad">revoked: {a.reason}</span>}
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
      {projects && projects.length > 0 && <p className="muted small">Most recent issuance: {date(Math.max(...projects.map((p) => p.mintedAt)))}</p>}
    </>
  );
}
