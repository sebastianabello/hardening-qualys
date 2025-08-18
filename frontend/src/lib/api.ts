import type { ProcessResponse, IngestResult } from "../types"

export async function processFiles(
  files: File[],
  client: string,
  empresas: string[],            // ex. ["ACME","Banconia"]
  nombreDefecto?: string
): Promise<ProcessResponse> {
  const form = new FormData()
  files.forEach(f => form.append("files", f))
  form.append("client", client || "DEFAULT")
  form.append("empresas", JSON.stringify(empresas || []))
  form.append("nombre_defecto", nombreDefecto || client || "DEFAULT")

  const res = await fetch("/api/process", { method: "POST", body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function ingest(runId: string): Promise<IngestResult> {
  const res = await fetch(`/api/runs/${runId}/ingest`, { method: "POST" })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
