interface Props {
  rows: any[]
  title: string
  total?: number
  limit?: number
}

export default function PreviewTable({ rows, title, total, limit = 50 }: Props) {
  const cols = rows?.length ? Object.keys(rows[0]) : []
  const shown = rows?.slice(0, limit) || []
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4 overflow-auto">
      <div className="flex items-center justify-between mb-2">
        <div className="font-semibold text-slate-700">{title}</div>
        <div className="text-xs text-slate-500">
          {shown.length > 0 ? `Mostrando ${shown.length}${total ? ` de ${total}` : ""}` : "Sin datos"}
        </div>
      </div>
      {shown.length > 0 && (
        <div className="min-w-full">
          <table className="table-auto w-full text-sm">
            <thead>
              <tr className="bg-slate-100">
                {cols.map(c => (
                  <th key={c} className="px-2 py-2 text-left text-slate-600 whitespace-nowrap">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={i} className="border-b">
                  {cols.map(c => (
                    <td key={c} className="px-2 py-1 text-slate-700 whitespace-nowrap">{String(r[c] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {shown.length === 0 && <div className="text-slate-500 text-sm">Sin datos en la vista previa.</div>}
    </div>
  )
}
