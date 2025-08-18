export type Artifact = {
  name: string
  size: number
  download_url: string
}

export type Run = {
  run_id: string
  client: string
  created_at: string
  source_files: string[]
  counts: Record<string, number>
}

export type ProcessResponse = {
  run: Run
  artifacts: Artifact[]
  preview?: {
    control_stats?: any[]
    results?: any[]
  }
}
