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

  // Timeout de 30 minutos para procesamiento de muchos archivos
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 1800000) // 30 minutos

  try {
    const res = await fetch("/api/process", { 
      method: "POST", 
      body: form,
      signal: controller.signal
    })
    clearTimeout(timeoutId)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  } catch (error) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError') {
      throw new Error('El procesamiento tardó demasiado tiempo (más de 30 minutos)')
    }
    throw error
  }
}

// Nueva función asíncrona que no tiene timeout
export async function processFilesAsync(
  files: File[],
  client: string,
  empresas: string[],
  nombreDefecto?: string
): Promise<{ job_id: string; status: string; message: string }> {
  const form = new FormData()
  files.forEach(f => form.append("files", f))
  form.append("client", client || "DEFAULT")
  form.append("empresas", empresas.join(","))
  form.append("nombre_defecto", nombreDefecto || client || "DEFAULT")

  const res = await fetch("/api/process-async", { 
    method: "POST", 
    body: form
  })
  
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// Función para consultar estado del job
export async function getJobStatus(jobId: string): Promise<{
  job_id: string
  status: string
  progress: string
  files_processed: number
  total_files: number
  current_file: string
  created_at: string
  start_time?: string
  end_time?: string
  result?: ProcessResponse
  error?: string
}> {
  const res = await fetch(`/api/jobs/${jobId}/status`)
  if (!res.ok) {
    const errorText = await res.text()
    // Si el job no existe, probablemente el backend se reinició
    if (res.status === 404 && errorText.includes("Job no encontrado")) {
      throw new Error("Job perdido: El servidor se reinició y perdió el estado del job")
    }
    throw new Error(errorText)
  }
  return res.json()
}

// Función de polling que espera hasta que el job termine
export async function waitForJobCompletion(
  jobId: string,
  onProgress?: (status: any) => void,
  pollInterval: number = 1000,  // 1 segundo por defecto (más responsivo)
  maxAttempts: number = 3600     // 1 hora máximo para archivos muy grandes
): Promise<ProcessResponse> {
  return new Promise((resolve, reject) => {
    let attempts = 0
    let consecutiveErrors = 0
    const maxConsecutiveErrors = 5
    
    const poll = async () => {
      try {
        attempts++
        
        // Log menos verboso para no saturar la consola
        if (attempts % 10 === 1) { // Solo cada 10 intentos
          console.log(`[Job ${jobId}] Intento ${attempts}/${maxAttempts} - Consultando estado...`)
        }
        
        const status = await getJobStatus(jobId)
        
        // Resetear contador de errores en caso de éxito
        consecutiveErrors = 0
        
        if (onProgress) {
          onProgress(status)
        }
        
        if (status.status === 'completed') {
          console.log(`[Job ${jobId}] ✅ Completado exitosamente`)
          if (status.result) {
            resolve(status.result)
          } else {
            reject(new Error('Job completado pero sin resultado'))
          }
        } else if (status.status === 'failed') {
          console.log(`[Job ${jobId}] ❌ Falló:`, status.error)
          reject(new Error(status.error || 'Job falló'))
        } else if (attempts >= maxAttempts) {
          console.log(`[Job ${jobId}] ⏰ Timeout después de ${attempts} intentos`)
          reject(new Error(`Timeout: Job no completó en ${Math.round(maxAttempts * pollInterval / 60000)} minutos`))
        } else {
          // Job aún en progreso, continuar polling
          setTimeout(poll, pollInterval)
        }
      } catch (error) {
        consecutiveErrors++
        
        console.error(`[Job ${jobId}] ❌ Error en polling (${consecutiveErrors}/${maxConsecutiveErrors}):`, error)
        
        // Si el job se perdió por reinicio del servidor
        if (error.message.includes("Job perdido")) {
          console.log(`[Job ${jobId}] 🔄 Job perdido por reinicio del servidor`)
          reject(new Error("El servidor se reinició y perdió el estado del procesamiento. Intenta procesar de nuevo."))
        }
        // Si hay demasiados errores consecutivos, fallar
        else if (consecutiveErrors >= maxConsecutiveErrors) {
          console.log(`[Job ${jobId}] ❌ Demasiados errores consecutivos (${consecutiveErrors})`)
          reject(new Error(`Error de red persistente después de ${consecutiveErrors} intentos: ${error.message}`))
        }
        // Si es un error de red y no hemos alcanzado el límite, intentar de nuevo
        else if (attempts < maxAttempts && (error instanceof TypeError || error.message.includes('fetch'))) {
          console.log(`[Job ${jobId}] 🔄 Reintentando por error de red... (intento ${consecutiveErrors})`)
          setTimeout(poll, pollInterval * 2) // Doblar el intervalo en caso de error
        } else {
          reject(error)
        }
      }
    }
    
    poll()
  })
}

export async function ingest(runId: string): Promise<IngestResult> {
  // Timeout de 5 minutos para ingesta
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 300000) // 5 minutos

  try {
    const res = await fetch(`/api/runs/${runId}/ingest`, { 
      method: "POST",
      signal: controller.signal
    })
    clearTimeout(timeoutId)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  } catch (error) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError') {
      throw new Error('La ingesta tardó demasiado tiempo (más de 5 minutos)')
    }
    throw error
  }
}

export async function checkElasticsearchStatus(): Promise<{
  ok: boolean
  error?: string
  elasticsearch?: {
    version: string
    cluster_name: string
    url: string
  }
}> {
  const res = await fetch("/api/elasticsearch/status")
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
