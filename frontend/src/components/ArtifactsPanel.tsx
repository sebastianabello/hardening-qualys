import { FileSpreadsheet, AlertCircle, CheckCircle, Loader2 } from "lucide-react"
import { useEffect, useState } from "react"
import type { Artifact } from "../types"
import { checkElasticsearchStatus } from "../lib/api"

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
  const [esStatus, setEsStatus] = useState<{
    loading: boolean
    ok: boolean
    error?: string
    elasticsearch?: { version: string; cluster_name: string; url: string }
  }>({ loading: true, ok: false })

  const total =
    (counts?.t1_normal || 0) + (counts?.t1_ajustada || 0) +
    (counts?.t2_normal || 0) + (counts?.t2_ajustada || 0)

  useEffect(() => {
    checkElasticsearchStatus()
      .then(status => setEsStatus({ loading: false, ...status }))
      .catch(err => setEsStatus({ loading: false, ok: false, error: err.message }))
  }, [])

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
        
        {/* Estado de Elasticsearch */}
        <div className="p-3 rounded-lg border">
          {esStatus.loading ? (
            <div className="flex items-center gap-2 text-slate-600">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Verificando conexión con Elasticsearch...</span>
            </div>
          ) : esStatus.ok ? (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle size={16} />
                <span className="text-sm font-medium">Elasticsearch conectado</span>
              </div>
              {esStatus.elasticsearch && (
                <div className="text-xs text-slate-500 pl-6">
                  Cluster: {esStatus.elasticsearch.cluster_name} • Versión: {esStatus.elasticsearch.version}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-red-700">
                <AlertCircle size={16} />
                <span className="text-sm font-medium">Error de conexión con Elasticsearch</span>
              </div>
              <div className="text-xs text-red-600 pl-6">{esStatus.error}</div>
            </div>
          )}
        </div>

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
          disabled={ingesting || !confirmed || artifacts.length === 0 || !esStatus.ok}
        >
          {ingesting ? "Ingestando…" : esStatus.ok ? "Enviar a Elasticsearch" : "Elasticsearch no disponible"}
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
