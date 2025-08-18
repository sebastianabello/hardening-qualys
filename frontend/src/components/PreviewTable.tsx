interface Props {
  rows: any[]
  title: string
}

export default function PreviewTable({ rows, title }: Props) {
  const cols = rows?.length ? Object.keys(rows[0]) : []
  return (
    <div className="bg-white rounded-2xl shadow-sm p-4 overflow-auto">
      <div className="font-semibold text-slate-700 mb-2">{title}</div>
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
            {rows?.slice(0, 20).map((r, i) => (
              <tr key={i} className="border-b">
                {cols.map(c => (
                  <td key={c} className="px-2 py-1 text-slate-700 whitespace-nowrap">{String(r[c] ?? '')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows?.length && <div className="text-slate-500 text-sm">Sin datos en la vista previa.</div>}
    </div>
  )
}
