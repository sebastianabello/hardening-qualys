import { FileSpreadsheet } from "lucide-react"
import type { Artifact } from "../types"

type Props = {
  artifacts: Artifact[]
  counts?: Record<string, number>
  confirmed: boolean
  setConfirmed: (v: boolean) => void
  ingesting: boolean
  onIngest: () => void
  ingestResult?: any
}

function labelFromName(name: string) {
  const isControl = name.toLowerCase().includes("-control-statics")
  const isAjust = name.toLowerCase().includes("-ajustado")
  return `${isControl ? "Control" : "Results"}${isAjust ? " · Ajustada" : ""}`
}

export default function ArtifactsIngestPanel({
  artifacts, counts, confirmed, setConfirmed, ingesting, onIngest, ingestResult
}: Props) {
  const total =
    (counts?.t1_normal || 0) + (counts?.t1_ajustada || 0) +
    (counts?.t2_normal || 0) + (counts?.t2_ajustada || 0)

  return (
    <section className="bg-white rounded-2xl shadow-sm p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-slate-700">
          Excel generados (hasta 4)
          {typeof total === "number" ? (
            <span className="ml-2 text-xs text-slate-500">· {total} filas</span>
          ) : null}
        </div>
      </div>

      <ul className="space-y-2 max-h-56 overflow-y-auto pr-1">
        {artifacts.length === 0 && (
          <li className="text-sm text-slate-500">No hay archivos generados.</li>
        )}
        {artifacts.map(a => (
          <li key={a.name} className="flex items-center justify-between gap-3 text-sm">
            <div className="min-w-0 flex items-center gap-2">
              <FileSpreadsheet size={16} className="shrink-0 text-slate-500" />
              <div className="min-w-0">
                <div className="text-slate-700 truncate">{a.name}</div>
                <div className="text-[11px] text-slate-500">{labelFromName(a.name)}</div>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="text-[11px] text-slate-500">
                {(a.size/1024).toFixed(1)} KB
              </span>
              <a className="text-blue-600 hover:underline" href={a.download_url} download>
                Descargar
              </a>
            </div>
          </li>
        ))}
      </ul>

      <div className="border-t border-slate-200 pt-3 space-y-3">
        <div className="font-semibold text-slate-700">Validación e Ingesta</div>
        <div className="text-sm text-slate-700">
          Revisa los archivos generados. Al confirmar, se enviarán a Elasticsearch usando la configuración del backend.
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
          Confirmo que la información es correcta para enviar a Elasticsearch.
        </label>
        <button
          className="px-4 py-2 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          onClick={onIngest}
          disabled={ingesting || !confirmed || artifacts.length === 0}
        >
          {ingesting ? "Ingestando…" : "Enviar a Elasticsearch"}
        </button>

        {ingestResult && (
          <pre className="bg-slate-900 text-slate-100 rounded-xl p-3 text-xs overflow-auto">
            {JSON.stringify(ingestResult, null, 2)}
          </pre>
        )}
      </div>
    </section>
  )
}
