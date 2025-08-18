import type { Artifact } from "../types"

export default function ArtifactsPanel({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4">
      <div className="font-semibold text-slate-700 mb-3">Artefactos generados (4)</div>
      <ul className="space-y-2">
        {artifacts.map(a => (
          <li key={a.name} className="flex items-center justify-between text-sm">
            <span className="text-slate-700">{a.name}</span>
            <a className="text-blue-600 hover:underline" href={a.download_url} download>
              Descargar ({(a.size/1024).toFixed(1)} KB)
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
