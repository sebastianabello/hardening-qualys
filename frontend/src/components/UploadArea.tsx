import { Upload, FileArchive, FileText } from 'lucide-react'
import React from 'react'

interface Props {
  onFiles: (files: File[]) => void
}

export default function UploadArea({ onFiles }: Props) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [isOver, setIsOver] = React.useState(false)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsOver(false)
    const files = Array.from(e.dataTransfer.files).filter(f => /\.(csv|zip)$/i.test(f.name))
    onFiles(files)
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setIsOver(true) }}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
      className={`border-2 border-dashed rounded-2xl p-8 text-center bg-white shadow-sm ${isOver ? 'border-blue-400 bg-blue-50' : 'border-slate-300'}`}
    >
      <Upload className="mx-auto mb-4" />
      <p className="text-slate-700 font-medium">Arrastra aquí tus archivos CSV o ZIP</p>
      <p className="text-slate-500 text-sm mb-4">Se aceptan múltiples archivos</p>
      <button
        className="px-4 py-2 rounded-xl bg-slate-900 text-white hover:bg-slate-700"
        onClick={() => inputRef.current?.click()}
      >Seleccionar archivos</button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".csv,.zip"
        className="hidden"
        onChange={e => onFiles(e.target.files ? Array.from(e.target.files) : [])}
      />
      <div className="flex items-center justify-center gap-6 mt-6 text-slate-600">
        <span className="inline-flex items-center gap-2 text-sm"><FileText size={16}/> CSV</span>
        <span className="inline-flex items-center gap-2 text-sm"><FileArchive size={16}/> ZIP</span>
      </div>
    </div>
  )
}
