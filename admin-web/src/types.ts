export type AdminView = "collections" | "documents" | "chunks" | "questions" | "imports" | "debug"

export interface ApiErrorPayload {
  code: string
  detail: string
}

export class AdminApiError extends Error {
  code: string
  detail: string
  statusCode: number

  constructor(code: string, detail: string, statusCode: number) {
    super(detail)
    this.name = "AdminApiError"
    this.code = code
    this.detail = detail
    this.statusCode = statusCode
  }
}

export interface RagAdminCollectionItem {
  id: string
  title: string
  description: string
  sourceType: string
  tags: string[]
  isActive: boolean
  documentCount: number
  chunkCount: number
  questionCount: number
  createdAt: string
  updatedAt: string
}

export interface RagAdminCollectionListResponse {
  items: RagAdminCollectionItem[]
}

export interface RagAdminCollectionUpdateRequest {
  description?: string
  tags?: string[]
  isActive?: boolean
}

export interface RagAdminDocumentItem {
  id: string
  collectionId: string
  collectionTitle: string
  title: string
  sourceType: string
  sourceUri: string
  contentHash?: string | null
  metadata: Record<string, unknown>
  status: string
  isActive: boolean
  chunkCount: number
  createdAt: string
  updatedAt: string
}

export interface RagAdminDocumentListResponse {
  items: RagAdminDocumentItem[]
  total: number
  limit: number
  offset: number
}

export interface RagAdminDocumentUpdateRequest {
  title?: string
  sourceUri?: string
  metadata?: Record<string, unknown>
  status?: string
  isActive?: boolean
}

export interface RagAdminChunkItem {
  id: string
  collectionId: string
  collectionTitle: string
  documentId?: string | null
  documentTitle?: string | null
  title: string
  content: string
  sourceRef: string
  tags: string[]
  isActive: boolean
  embeddingModel?: string | null
  embeddingVersion?: string | null
  contentHash?: string | null
  embeddedAt?: string | null
  createdAt: string
}

export interface RagAdminChunkListResponse {
  items: RagAdminChunkItem[]
  total: number
  limit: number
  offset: number
}

export interface RagAdminChunkUpdateRequest {
  title?: string
  content?: string
  sourceRef?: string
  tags?: string[]
  isActive?: boolean
}

export interface RagAdminQuestionItem {
  id: string
  collectionId: string
  collectionTitle: string
  stem: string
  options: string[]
  answerIndex: number
  answerIndexes: number[]
  questionType: string
  explanation: string
  knowledgePoint: string
  difficulty: string
  tags: string[]
  isActive: boolean
  embeddingModel?: string | null
  embeddingVersion?: string | null
  contentHash?: string | null
  embeddedAt?: string | null
  createdAt: string
  updatedAt: string
}

export interface RagAdminQuestionListResponse {
  items: RagAdminQuestionItem[]
  total: number
  limit: number
  offset: number
}

export interface RagAdminQuestionUpdateRequest {
  difficulty?: string
  tags?: string[]
  isActive?: boolean
}

export interface RagAdminReembedResponse {
  id: string
  embeddingModel: string
  embeddingVersion: string
  contentHash: string
  embeddedAt: string
}

export interface RagDebugScoreBreakdown {
  title: number
  tags: number
  body: number
  source: number
  collection: number
}

export interface RagDebugMatch {
  kind: string
  id: string
  collectionId: string
  collectionTitle: string
  title: string
  keywordScore: number
  vectorScore: number
  totalScore: number
  keywordRank?: number | null
  vectorRank?: number | null
  fusionMethod: string
  keywordScoreBreakdown: RagDebugScoreBreakdown
  tags: string[]
  sourceRef: string
}

export interface RagDebugResponse {
  query: string
  retrievalVersion: string
  questions: RagDebugMatch[]
  chunks: RagDebugMatch[]
}

export interface RagImportJobItem {
  id: string
  status: string
  sourceType: string
  sourceUri: string
  fileName: string
  collectionTitle: string
  documentTitle?: string | null
  chunkSize: number
  chunkOverlap: number
  stats: Record<string, unknown>
  errorMessage: string
  queueJobId: string
  createdAt: string
  startedAt?: string | null
  finishedAt?: string | null
}

export interface RagImportJobListResponse {
  items: RagImportJobItem[]
  total: number
  limit: number
  offset: number
}

export interface ListFilters {
  collectionId: string
  documentId: string
  q: string
  status: string
  isActive: "all" | "true" | "false"
}

export interface PageState<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
