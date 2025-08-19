import React from "react"
import UploadArea from "./components/UploadArea"
import PreviewTable from "./components/PreviewTable"
import ArtifactsIngestPanel from "./components/ArtifactsPanel"
import { processFiles, ingest } from "./lib/api"
import type { Artifact, ProcessResponse } from "./types"
import { CLIENTS } from "./data/clients"

function uniq<T>(arr: T[]): T[] {
  return Array.from(new Set(arr))
}

export default function App() {
  // --- Selección de cliente desde un catálogo fijo
  const [clientId, setClientId] = React.useState(CLIENTS[0]?.id || "")
  const selectedClient = React.useMemo(
    () => CLIENTS.find(c => c.id === clientId) || CLIENTS[0],
    [clientId]
  )

  // Empresas visibles para detección (base del cliente + agregadas por el usuario)
  const [empresas, setEmpresas] = React.useState<string[]>([])
  const [newEmpresa, setNewEmpresa] = React.useState("")

  // Archivos
  const [selected, setSelected] = React.useState<File[]>([])
  const [processing, setProcessing] = React.useState(false)
  const [resp, setResp] = React.useState<ProcessResponse | null>(null)

  // Notificaciones
  const [error, setError] = React.useState<string | null>(null)
  const [notice, setNotice] = React.useState<string | null>(null)

  // Ingesta
  const [ingesting, setIngesting] = React.useState(false)
  const [confirmed, setConfirmed] = React.useState(false)
  const [ingestResult, setIngestResult] = React.useState<any>(null)

  // Cargar/guardar overrides por cliente en localStorage
  const LS_KEY = (id: string) => `empresas_overrides_${id}`

  React.useEffect(() => {
    // Cuando cambia el cliente, cargamos su base + overrides guardados
    const base = selectedClient?.empresas || []
    let extra: string[] = []
    try {
      extra = JSON.parse(localStorage.getItem(LS_KEY(selectedClient.id)) || "[]")
    } catch {}
    setEmpresas(uniq([...base, ...extra]))
  }, [clientId])

  function persistOverride(list: string[]) {
    // Guardamos SOLO las que no están en la base como overrides
    const base = new Set((selectedClient?.empresas || []).map(s => s.toLowerCase()))
    const extra = list.filter(s => !base.has(s.toLowerCase()))
    localStorage.setItem(LS_KEY(selectedClient.id), JSON.stringify(extra))
  }

  // Manejo de archivos (agregar/quitar sin perder previos)
  function addFiles(newFiles: File[]) {
    const key = (f: File) => `${f.name}-${f.size}-${(f as any).lastModified}`
    const map = new Map(selected.map(f => [key(f), f]))
    newFiles.forEach(f => map.set(key(f), f))
    setSelected(Array.from(map.values()))
  }
  function removeFile(fileKey: string) {
    setSelected(prev => prev.filter(f => `${f.name}-${f.size}-${(f as any).lastModified}` !== fileKey))
  }

  // Manejo de empresas
  function onAddEmpresa() {
    const val = newEmpresa.trim()
    if (!val) return
    const next = uniq([...empresas, val])
    setEmpresas(next)
    setNewEmpresa("")
    persistOverride(next)
  }
  function onRemoveEmpresa(val: string) {
    const next = empresas.filter(e => e.toLowerCase() !== val.toLowerCase())
    setEmpresas(next)
    persistOverride(next)
  }
  function onResetEmpresas() {
    const base = selectedClient?.empresas || []
    setEmpresas([...base])
    localStorage.removeItem(LS_KEY(selectedClient.id))
  }

  async function onProcess() {
    try {
      setError(null); setNotice(null); setIngestResult(null); setConfirmed(false)
      setProcessing(true)
      const clientName = selectedClient?.name || "DEFAULT"
      const r = await processFiles(selected, clientName, empresas, clientName)
      setResp(r)
      const c = r.run?.counts || {}
      const total = (c.t1_normal || 0) + (c.t1_ajustada || 0) + (c.t2_normal || 0) + (c.t2_ajustada || 0)
      setNotice(`Procesamiento OK · ${r.run.source_files.length} archivo(s) · ${total} fila(s)`)
    } catch (e: any) {
      setError(e?.message || String(e))
    } finally {
      setProcessing(false)
    }
  }

  async function onIngest() {
    if (!resp) return
    try {
      setError(null); setNotice(null)
      setIngesting(true)
      const r = await ingest(resp.run.run_id)
      setIngestResult(r)
      setNotice(`Ingesta completada · ${Object.entries(r.indexed).map(([idx,n])=>`${idx}: ${n}`).join(" · ")}`)
    } catch (e: any) {
      setError(e?.message || String(e))
    } finally {
      setIngesting(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-2xl font-bold text-slate-800">Qualys Hardening</h1>

        {/* Cliente (dropdown fijo) */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-700">Cliente:</label>
          <select
            value={clientId}
            onChange={e => setClientId(e.target.value)}
            className="px-3 py-2 rounded-xl border border-slate-300 bg-white text-sm"
          >
            {CLIENTS.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
      </header>

      {/* Empresas (chips + agregar + reset) */}
      <section className="bg-white rounded-2xl shadow-sm p-4 space-y-3">
        <div className="font-semibold text-slate-700">Empresas (detección en cabecera)</div>

        <div className="flex flex-wrap gap-2">
          {empresas.map(e => (
            <span
              key={e}
              className="inline-flex items-center gap-2 bg-slate-100 text-slate-700 px-3 py-1 rounded-xl text-sm"
              title={e}
            >
              <span className="truncate max-w-[18rem]">{e}</span>
              <button
                className="text-slate-500 hover:text-red-600"
                onClick={() => onRemoveEmpresa(e)}
                title="Quitar"
              >✕</button>
            </span>
          ))}
          {empresas.length === 0 && <span className="text-slate-500 text-sm">Sin empresas configuradas.</span>}
        </div>

        <div className="flex items-center gap-2">
          <input
            className="flex-1 px-3 py-2 rounded-xl border border-slate-300 bg-white text-sm"
            placeholder="Agregar empresa/alias (se guarda para este cliente)"
            value={newEmpresa}
            onChange={e => setNewEmpresa(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") onAddEmpresa() }}
          />
          <button
            className="px-3 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-700"
            onClick={onAddEmpresa}
          >Agregar</button>
          <button
            className="px-3 py-2 rounded-xl bg-slate-100 text-slate-700 hover:bg-slate-200"
            onClick={onResetEmpresas}
          >Restablecer</button>
        </div>
        <div className="text-xs text-slate-500">Se guardan las empresas AGREGADAS en el navegador (localStorage) para este cliente.</div>
      </section>

      {/* Carga de archivos + procesar */}
      <div className="grid md:grid-cols-4 gap-4">

        <div className="md:col-span-3 bg-white rounded-2xl shadow-sm p-4 space-y-2">
          {/* header + botón limpiar */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-slate-700">
              Archivos seleccionados <span className="text-slate-400">({selected.length})</span>
            </div>
            <button
              type="button"
              className="text-xs px-2 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50"
              disabled={selected.length === 0}
              onClick={() => {
                if (selected.length <= 10 || window.confirm(`¿Quitar ${selected.length} archivo(s)?`)) {
                  setSelected([])
                }
              }}
              title="Quitar todos"
            >
              Limpiar
            </button>
          </div>

          {/* contenedor con scroll */}
          <div className="max-h-32 md:max-h-32 overflow-y-auto pr-1">
            <ul className="flex flex-col flex-wrap gap-2 text-sm text-slate-700">
              {selected.map(f => {
                const k = `${f.name}-${f.size}-${(f as any).lastModified}`
                return (
                  <li key={k} className="px-2 py-1 bg-slate-100 rounded-xl flex items-center gap-2">
                    <span className="">{f.name}</span>
                    <button
                      type="button"
                      className="text-slate-500 hover:text-red-600"
                      onClick={() => removeFile(k)}
                      title="Quitar"
                    >
                      ✕
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>

          <button
            className="w-full mt-2 px-4 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-700 disabled:opacity-50"
            onClick={onProcess}
            disabled={processing || selected.length === 0}
          >
            {processing ? "Procesando…" : "Procesar"}
          </button>
        </div>
        <div className="md:col-span-1">
          <UploadArea onAddFiles={addFiles} />
        </div>

      </div>

      {notice && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-2xl p-3">{notice}</div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-3">{error}</div>
      )}
      {!!resp?.warnings?.length && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-2xl p-3">
          <b>Warnings:</b>
          <ul className="list-disc ml-5">
            {resp.warnings!.map((w,i)=><li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {resp && (
        <>
          <section className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-4">
              <PreviewTable
                title="Vista previa — T1 Control (normal)"
                rows={resp.preview?.t1_normal || []}
                total={resp.run.counts?.t1_normal}
              />
              <PreviewTable
                title="Vista previa — T1 Control (ajustada)"
                rows={resp.preview?.t1_ajustada || []}
                total={resp.run.counts?.t1_ajustada}
              />
              <PreviewTable
                title="Vista previa — T2 RESULTS (normal)"
                rows={resp.preview?.t2_normal || []}
                total={resp.run.counts?.t2_normal}
              />
              <PreviewTable
                title="Vista previa — T2 RESULTS (ajustada)"
                rows={resp.preview?.t2_ajustada || []}
                total={resp.run.counts?.t2_ajustada}
              />
            </div>
            <ArtifactsIngestPanel
                  artifacts={resp.artifacts as Artifact[]}
                  counts={resp.run.counts}
                  confirmed={confirmed}
                  setConfirmed={setConfirmed}
                  ingesting={ingesting}
                  onIngest={onIngest}
                  ingestResult={ingestResult}
                />
          </section>
        </>
      )}

      <footer className="text-center text-slate-500 text-xs">© Desarrollado por Juan Abello</footer>
    </div>
  )
}
