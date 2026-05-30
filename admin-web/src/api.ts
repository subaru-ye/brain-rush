import {
  AdminApiError,
  type ApiErrorPayload,
  type RagAdminChunkItem,
  type RagAdminChunkListResponse,
  type RagAdminChunkUpdateRequest,
  type RagAdminCollectionItem,
  type RagAdminCollectionListResponse,
  type RagAdminCollectionUpdateRequest,
  type RagAdminDocumentItem,
  type RagAdminDocumentListResponse,
  type RagAdminDocumentUpdateRequest,
  type RagAdminQuestionItem,
  type RagAdminQuestionListResponse,
  type RagAdminQuestionUpdateRequest,
  type RagAdminReembedResponse,
  type RagDebugResponse,
  type RagImportHealthResponse,
  type RagImportJobItem,
  type RagImportJobListResponse
} from "./types"

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

type QueryValue = string | number | boolean | undefined | null

function queryString(params: Record<string, QueryValue>): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return
    }
    searchParams.set(key, String(value))
  })
  const query = searchParams.toString()
  return query ? `?${query}` : ""
}

async function parseError(response: Response): Promise<AdminApiError> {
  try {
    const data = (await response.json()) as Partial<ApiErrorPayload>
    return new AdminApiError(
      typeof data.code === "string" ? data.code : "unknown_error",
      typeof data.detail === "string" ? data.detail : "请求失败",
      response.status
    )
  } catch {
    return new AdminApiError("unknown_error", "请求失败", response.status)
  }
}

async function requestJson<TResponse>(
  token: string,
  path: string,
  options: RequestInit = {}
): Promise<TResponse> {
  const headers = new Headers(options.headers)
  headers.set("content-type", "application/json")
  headers.set("X-Admin-Token", token)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  })

  if (!response.ok) {
    throw await parseError(response)
  }

  return response.json() as Promise<TResponse>
}

async function requestForm<TResponse>(
  token: string,
  path: string,
  formData: FormData
): Promise<TResponse> {
  const headers = new Headers()
  headers.set("X-Admin-Token", token)

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData
  })

  if (!response.ok) {
    throw await parseError(response)
  }

  return response.json() as Promise<TResponse>
}

export function listCollections(token: string): Promise<RagAdminCollectionListResponse> {
  return requestJson<RagAdminCollectionListResponse>(token, "/api/admin/rag/collections")
}

export function updateCollection(
  token: string,
  id: string,
  payload: RagAdminCollectionUpdateRequest
): Promise<RagAdminCollectionItem> {
  return requestJson<RagAdminCollectionItem>(token, `/api/admin/rag/collections/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  })
}

export function listDocuments(
  token: string,
  params: {
    collectionId?: string
    q?: string
    status?: string
    isActive?: boolean
    limit?: number
    offset?: number
  }
): Promise<RagAdminDocumentListResponse> {
  return requestJson<RagAdminDocumentListResponse>(
    token,
    `/api/admin/rag/documents${queryString(params)}`
  )
}

export function updateDocument(
  token: string,
  id: string,
  payload: RagAdminDocumentUpdateRequest
): Promise<RagAdminDocumentItem> {
  return requestJson<RagAdminDocumentItem>(token, `/api/admin/rag/documents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  })
}

export function listChunks(
  token: string,
  params: {
    collectionId?: string
    documentId?: string
    q?: string
    isActive?: boolean
    limit?: number
    offset?: number
  }
): Promise<RagAdminChunkListResponse> {
  return requestJson<RagAdminChunkListResponse>(
    token,
    `/api/admin/rag/chunks${queryString(params)}`
  )
}

export function updateChunk(
  token: string,
  id: string,
  payload: RagAdminChunkUpdateRequest
): Promise<RagAdminChunkItem> {
  return requestJson<RagAdminChunkItem>(token, `/api/admin/rag/chunks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  })
}

export function reembedChunk(token: string, id: string): Promise<RagAdminReembedResponse> {
  return requestJson<RagAdminReembedResponse>(token, `/api/admin/rag/chunks/${id}/reembed`, {
    method: "POST",
    body: JSON.stringify({})
  })
}

export function listQuestions(
  token: string,
  params: {
    collectionId?: string
    q?: string
    isActive?: boolean
    limit?: number
    offset?: number
  }
): Promise<RagAdminQuestionListResponse> {
  return requestJson<RagAdminQuestionListResponse>(
    token,
    `/api/admin/rag/questions${queryString(params)}`
  )
}

export function updateQuestion(
  token: string,
  id: string,
  payload: RagAdminQuestionUpdateRequest
): Promise<RagAdminQuestionItem> {
  return requestJson<RagAdminQuestionItem>(token, `/api/admin/rag/questions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  })
}

export function reembedQuestion(token: string, id: string): Promise<RagAdminReembedResponse> {
  return requestJson<RagAdminReembedResponse>(token, `/api/admin/rag/questions/${id}/reembed`, {
    method: "POST",
    body: JSON.stringify({})
  })
}

export function debugRag(
  token: string,
  payload: { query: string; limit: number }
): Promise<RagDebugResponse> {
  return requestJson<RagDebugResponse>(token, "/api/debug/rag", {
    method: "POST",
    body: JSON.stringify(payload)
  })
}

export function listImportJobs(
  token: string,
  params: {
    status?: string
    limit?: number
    offset?: number
  }
): Promise<RagImportJobListResponse> {
  return requestJson<RagImportJobListResponse>(
    token,
    `/api/admin/rag/imports${queryString(params)}`
  )
}

export function getImportHealth(token: string): Promise<RagImportHealthResponse> {
  return requestJson<RagImportHealthResponse>(token, "/api/admin/rag/imports/health")
}

export function uploadImportJob(
  token: string,
  payload: {
    file: File
    collectionTitle: string
    title?: string
    chunkSize: number
    chunkOverlap: number
  }
): Promise<RagImportJobItem> {
  const formData = new FormData()
  formData.set("file", payload.file)
  formData.set("collectionTitle", payload.collectionTitle)
  if (payload.title) {
    formData.set("title", payload.title)
  }
  formData.set("chunkSize", String(payload.chunkSize))
  formData.set("chunkOverlap", String(payload.chunkOverlap))
  return requestForm<RagImportJobItem>(token, "/api/admin/rag/imports/upload", formData)
}

export function retryImportJob(token: string, id: string): Promise<RagImportJobItem> {
  return requestJson<RagImportJobItem>(token, `/api/admin/rag/imports/${id}/retry`, {
    method: "POST",
    body: JSON.stringify({})
  })
}
