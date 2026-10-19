import type { Observation } from "../api";
import { MONTHS, ndviColor } from "../format";

/** One band per month, coloured by mean NDVI. Cloudy months (low valid coverage) fade and are hatched. */
export default function EvidenceRibbon({ observations }: { observations: Observation[] }) {
  const byMonth = new Map(observations.map((o) => [o.month, o]));
  const summary = MONTHS.map((m, i) => {
    const o = byMonth.get(i + 1);
    return o ? `${m} NDVI ${o.mean_ndvi.toFixed(2)}` : `${m} no data`;
  }).join(", ");
  return (
    <figure className="ribbon" aria-label={`Monthly vegetation index for the year. ${summary}`}>
      <div className="ribbon-bands">
        {MONTHS.map((m, i) => {
          const o = byMonth.get(i + 1);
          const cloudy = !o || o.valid_fraction < 0.5;
          return (
            <div key={m} className="ribbon-col" title={o ? `${m}: NDVI ${o.mean_ndvi.toFixed(2)}, ${Math.round(o.valid_fraction * 100)}% clear sky` : `${m}: no usable scene`}>
              <div
                className={`ribbon-band${cloudy ? " cloudy" : ""}`}
                style={{ background: o ? ndviColor(o.mean_ndvi) : "transparent", opacity: o ? 0.45 + 0.55 * o.valid_fraction : 1 }}
              />
              <span className="ribbon-val">{o ? o.mean_ndvi.toFixed(2) : "–"}</span>
              <span className="ribbon-month">{m[0]}</span>
            </div>
          );
        })}
      </div>
      <figcaption>
        <span className="ribbon-scale" aria-hidden="true" />
        <span>Bare ground</span><span className="grow" /><span>Dense forest</span>
        <span className="muted"> · Hatched months were mostly cloud-covered</span>
      </figcaption>
    </figure>
  );
}
