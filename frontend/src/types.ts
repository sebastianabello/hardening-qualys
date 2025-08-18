export type Artifact = {
  name: string
  size: number
  download_url: string
}

export type Run = {
  run_id: string
  client: string
  source_files: string[]
  counts: Record<string, number>
}

export type PreviewPayload = {
  t1_normal?: any[]
  t1_ajustada?: any[]
  t2_normal?: any[]
  t2_ajustada?: any[]
}

export type ProcessResponse = {
  run: Run
  artifacts: Artifact[]
  preview?: PreviewPayload
  warnings?: string[]
}

export type IngestResult = {
  ok: boolean
  errors: boolean
  indexed: Record<string, number>
  details?: Record<string, any>
}
