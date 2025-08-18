import React from 'react'
import UploadArea from './components/UploadArea'
import PreviewTable from './components/PreviewTable'
import ArtifactsPanel from './components/ArtifactsPanel'
import { processFiles, ingest } from './lib/api'
import type { Artifact, ProcessResponse } from './types'

export default function App() {
  const [client, setClient] = React.useState('DEFAULT')
  const [selected, setSelected] = React.useState<File[]>([])
  const [processing, setProcessing] = React.useState(false)
  const [resp, setResp] = React.useState<ProcessResponse | null>(null)

  const [esUrl, setEsUrl] = React.useState('')
  const [esKey, setEsKey] = React.useState('')
  const [ingesting, setIngesting] = React.useState(false)
  const [ingestResult, setIngestResult] = React.useState<any>(null)
  const [error, setError] = React.useState<string | null>(null)

  async function onProcess() {
    try {
      setError(null)
      setProcessing(true)
      const r = await processFiles(selected, client)
      setResp(r)
    } catch (e: any) {
      setError(e?.message || String(e))
    } finally {
      setProcessing(false)
    }
  }

  async function onIngest() {
    if (!resp) return
    try {
      setError(null)
      setIngesting(true)
      const r = await ingest(resp.run.run_id, { es_base_url: esUrl, es_api_key: esKey })
      setIngestResult(r)
    } catch (e: any) {
      setError(e?.message || String(e))
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Qualys CSV Processor</h1>
        <div className="flex items-center gap-2">
          <input
            className="px-3 py-2 rounded-xl border border-slate-300 bg-white text-sm"
            placeholder="Nombre de Cliente"
            value={client}
            onChange={e => setClient(e.target.value)}
          />
        </div>
      </header>

      <UploadArea onFiles={setSelected} />

      {selected.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm p-4">
          <div className="text-slate-700 text-sm mb-2">Archivos seleccionados:</div>
          <ul className="flex flex-wrap gap-2 text-sm text-slate-700">
            {selected.map(f => <li key={f.name} className="px-2 py-1 bg-slate-100 rounded-xl">{f.name}</li>)}
          </ul>
          <button
            className="mt-4 px-4 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-700 disabled:opacity-50"
            onClick={onProcess}
            disabled={processing}
          >{processing ? 'Procesando…' : 'Procesar'}</button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4">{error}</div>
      )}

      {resp && (
        <>
          <section className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-4">
              <PreviewTable title="Vista previa — Control Statistics" rows={resp.preview?.control_stats || []} />
              <PreviewTable title="Vista previa — RESULTS" rows={resp.preview?.results || []} />
            </div>
            <ArtifactsPanel artifacts={resp.artifacts as Artifact[]} />
          </section>

          <section className="bg-white rounded-2xl shadow-sm p-4 space-y-3">
            <div className="font-semibold text-slate-700">Ingesta a Elasticsearch</div>
            <div className="grid md:grid-cols-2 gap-3">
              <input className="px-3 py-2 rounded-xl border border-slate-300 bg-white text-sm" placeholder="ES Base URL (https://es.ejemplo.com)" value={esUrl} onChange={e=>setEsUrl(e.target.value)} />
              <input className="px-3 py-2 rounded-xl border border-slate-300 bg-white text-sm" placeholder="ES API Key" value={esKey} onChange={e=>setEsKey(e.target.value)} />
            </div>
            <button
              className="px-4 py-2 rounded-xl bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
              onClick={onIngest}
              disabled={ingesting || !resp}
            >{ingesting ? 'Ingestando…' : 'Enviar 4 artefactos (_bulk)'}</button>
            {ingestResult && (
              <pre className="bg-slate-900 text-slate-100 rounded-xl p-3 text-xs overflow-auto">{JSON.stringify(ingestResult, null, 2)}</pre>
            )}
          </section>
        </>
      )}

      <footer className="text-center text-slate-500 text-xs">FS storage • sin BD • © Qualys CSV Processor</footer>
    </div>
  )
}
