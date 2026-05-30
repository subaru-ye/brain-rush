import { FormEvent, useEffect, useMemo, useState } from "react"

import {
  API_BASE_URL,
  debugRag,
  getImportHealth,
  listImportJobs,
  listChunks,
  listCollections,
  listDocuments,
  listQuestions,
  reembedChunk,
  reembedQuestion,
  retryImportJob,
  updateChunk,
  updateCollection,
  updateDocument,
  updateQuestion,
  uploadImportJob
} from "./api"
import { activeLabel, embeddingLabel, formatDate, parseTags, tagsText } from "./format"
import { clearAdminToken, getStoredAdminToken, saveAdminToken } from "./storage"
import {
  AdminApiError,
  type AdminView,
  type ListFilters,
  type PageState,
  type RagAdminChunkItem,
  type RagAdminCollectionItem,
  type RagAdminDocumentItem,
  type RagAdminQuestionItem,
  type RagDebugMatch,
  type RagDebugResponse,
  type RagImportHealthResponse,
  type RagImportJobItem
} from "./types"

const PAGE_LIMIT = 50

const views: Array<{ id: AdminView; label: string; description: string }> = [
  { id: "collections", label: "Collections", description: "知识库集合" },
  { id: "documents", label: "Documents", description: "资料来源" },
  { id: "chunks", label: "Chunks", description: "知识片段" },
  { id: "questions", label: "Questions", description: "精选题" },
  { id: "imports", label: "Imports", description: "导入任务" },
  { id: "debug", label: "Debug", description: "检索调试" }
]

const emptyFilters: ListFilters = {
  collectionId: "",
  documentId: "",
  q: "",
  status: "",
  isActive: "all"
}

const emptyPage = <T,>(): PageState<T> => ({
  items: [],
  total: 0,
  limit: PAGE_LIMIT,
  offset: 0
})

function activeFilterValue(value: ListFilters["isActive"]): boolean | undefined {
  if (value === "true") return true
  if (value === "false") return false
  return undefined
}

function friendlyError(error: unknown): string {
  if (error instanceof AdminApiError) {
    if (error.code === "admin_disabled") {
      return "后端未启用管理接口，请先配置 ADMIN_API_TOKEN。"
    }
    if (error.code === "admin_auth_invalid") {
      return "Admin Token 无效，请重新输入。"
    }
    if (error.code === "embedding_disabled") {
      return "Embedding 服务未配置，暂时不能重跑向量。"
    }
    return error.detail || "请求失败"
  }
  return error instanceof Error ? error.message : "请求失败"
}

function statusTone(isActive: boolean): string {
  return isActive ? "pill pill-green" : "pill pill-muted"
}

function jobStatusTone(status: string): string {
  if (status === "succeeded") return "pill pill-green"
  if (status === "failed") return "pill pill-red"
  if (status === "running") return "pill pill-blue"
  return "pill pill-muted"
}

function textPreview(value: string, length = 120): string {
  if (value.length <= length) return value
  return `${value.slice(0, length)}...`
}

function importStatsLabel(item: RagImportJobItem): string {
  const total = item.stats.total_imported
  const generated = item.stats.embeddings_generated
  if (typeof total === "number") {
    return `${total} chunks · ${typeof generated === "number" ? generated : 0} embeddings`
  }
  return item.errorMessage || "waiting"
}

function importStatusHint(item: RagImportJobItem, health: RagImportHealthResponse | null): string {
  const hints: string[] = []
  if (item.status === "queued" && health?.workerCount === 0) {
    hints.push("worker 未在线，任务不会被处理")
  }
  if (item.status === "queued" && item.isStale) {
    hints.push("可能需要 Requeue 或检查 worker")
  }
  if (item.status === "running" && item.isStale) {
    hints.push("任务可能卡住，可 Requeue")
  }
  if (item.status === "failed" && item.errorMessage) {
    hints.push(item.errorMessage)
  }
  if (item.status === "succeeded") {
    hints.push(importStatsLabel(item))
  }
  return hints.join("；")
}

export default function App() {
  const [token, setToken] = useState(getStoredAdminToken)
  const [tokenInput, setTokenInput] = useState("")
  const [activeView, setActiveView] = useState<AdminView>("collections")
  const [filters, setFilters] = useState<ListFilters>(emptyFilters)
  const [collections, setCollections] = useState<RagAdminCollectionItem[]>([])
  const [documents, setDocuments] = useState<PageState<RagAdminDocumentItem>>(emptyPage)
  const [chunks, setChunks] = useState<PageState<RagAdminChunkItem>>(emptyPage)
  const [questions, setQuestions] = useState<PageState<RagAdminQuestionItem>>(emptyPage)
  const [imports, setImports] = useState<PageState<RagImportJobItem>>(emptyPage)
  const [importHealth, setImportHealth] = useState<RagImportHealthResponse | null>(null)
  const [selectedIds, setSelectedIds] = useState<Record<AdminView, string>>({
    collections: "",
    documents: "",
    chunks: "",
    questions: "",
    imports: "",
    debug: ""
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [reembedding, setReembedding] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  const selectedCollection = useMemo(
    () => collections.find((item) => item.id === selectedIds.collections) || collections[0],
    [collections, selectedIds.collections]
  )
  const selectedDocument = useMemo(
    () => documents.items.find((item) => item.id === selectedIds.documents) || documents.items[0],
    [documents.items, selectedIds.documents]
  )
  const selectedChunk = useMemo(
    () => chunks.items.find((item) => item.id === selectedIds.chunks) || chunks.items[0],
    [chunks.items, selectedIds.chunks]
  )
  const selectedQuestion = useMemo(
    () => questions.items.find((item) => item.id === selectedIds.questions) || questions.items[0],
    [questions.items, selectedIds.questions]
  )
  const selectedImport = useMemo(
    () => imports.items.find((item) => item.id === selectedIds.imports) || imports.items[0],
    [imports.items, selectedIds.imports]
  )

  useEffect(() => {
    if (!token) return
    void refresh(activeView, 0)
  }, [token, activeView])

  useEffect(() => {
    if (!token || activeView !== "imports") return
    const intervalId = window.setInterval(() => {
      void refresh("imports")
    }, 5000)
    return () => window.clearInterval(intervalId)
  }, [token, activeView, filters.status, imports.offset])

  function handleAuthError(errorValue: unknown) {
    if (errorValue instanceof AdminApiError && errorValue.code === "admin_auth_invalid") {
      clearAdminToken()
      setToken("")
    }
    setError(friendlyError(errorValue))
  }

  async function refresh(view: AdminView = activeView, offset?: number) {
    if (!token) return
    setLoading(true)
    setError("")
    setNotice("")
    try {
      const collectionResponse = await listCollections(token)
      setCollections(collectionResponse.items)
      if (view === "collections") {
        if (!selectedIds.collections && collectionResponse.items[0]) {
          setSelectedIds((current) => ({ ...current, collections: collectionResponse.items[0].id }))
        }
      }
      if (view === "documents") {
        const response = await listDocuments(token, {
          collectionId: filters.collectionId,
          q: filters.q,
          status: filters.status,
          isActive: activeFilterValue(filters.isActive),
          limit: PAGE_LIMIT,
          offset: offset ?? documents.offset
        })
        setDocuments(response)
        if (response.items[0]) {
          setSelectedIds((current) => ({ ...current, documents: response.items[0].id }))
        }
      }
      if (view === "chunks") {
        const [documentResponse, chunkResponse] = await Promise.all([
          listDocuments(token, {
            collectionId: filters.collectionId,
            limit: 100,
            offset: 0
          }),
          listChunks(token, {
            collectionId: filters.collectionId,
            documentId: filters.documentId,
            q: filters.q,
            isActive: activeFilterValue(filters.isActive),
            limit: PAGE_LIMIT,
            offset: offset ?? chunks.offset
          })
        ])
        setDocuments(documentResponse)
        setChunks(chunkResponse)
        if (chunkResponse.items[0]) {
          setSelectedIds((current) => ({ ...current, chunks: chunkResponse.items[0].id }))
        }
      }
      if (view === "questions") {
        const response = await listQuestions(token, {
          collectionId: filters.collectionId,
          q: filters.q,
          isActive: activeFilterValue(filters.isActive),
          limit: PAGE_LIMIT,
          offset: offset ?? questions.offset
        })
        setQuestions(response)
        if (response.items[0]) {
          setSelectedIds((current) => ({ ...current, questions: response.items[0].id }))
        }
      }
      if (view === "imports") {
        const [response, health] = await Promise.all([
          listImportJobs(token, {
            status: filters.status,
            limit: PAGE_LIMIT,
            offset: offset ?? imports.offset
          }),
          getImportHealth(token)
        ])
        setImports(response)
        setImportHealth(health)
        if (response.items[0]) {
          setSelectedIds((current) => ({ ...current, imports: response.items[0].id }))
        }
      }
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setLoading(false)
    }
  }

  function submitToken(event: FormEvent) {
    event.preventDefault()
    const nextToken = tokenInput.trim()
    if (!nextToken) {
      setError("请输入 Admin Token。")
      return
    }
    saveAdminToken(nextToken)
    setToken(nextToken)
    setTokenInput("")
  }

  function logout() {
    clearAdminToken()
    setToken("")
    setError("")
    setNotice("")
  }

  function updateFilter<K extends keyof ListFilters>(key: K, value: ListFilters[K]) {
    setFilters((current) => ({
      ...current,
      [key]: value,
      ...(key === "collectionId" ? { documentId: "" } : {})
    }))
  }

  function selectView(view: AdminView) {
    setActiveView(view)
    setError("")
    setNotice("")
  }

  async function saveCollection(item: RagAdminCollectionItem, draft: CollectionDraft) {
    setSaving(true)
    setError("")
    try {
      const updated = await updateCollection(token, item.id, {
        description: draft.description,
        tags: parseTags(draft.tags),
        isActive: draft.isActive
      })
      setCollections((items) => items.map((entry) => (entry.id === updated.id ? updated : entry)))
      setNotice("Collection 已保存。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setSaving(false)
    }
  }

  async function saveDocument(item: RagAdminDocumentItem, draft: DocumentDraft) {
    setSaving(true)
    setError("")
    try {
      let metadata: Record<string, unknown>
      try {
        metadata = JSON.parse(draft.metadata) as Record<string, unknown>
      } catch {
        setError("Metadata 不是合法 JSON。")
        return
      }
      const updated = await updateDocument(token, item.id, {
        title: draft.title,
        sourceUri: draft.sourceUri,
        metadata,
        status: draft.status,
        isActive: draft.isActive
      })
      setDocuments((page) => ({
        ...page,
        items: page.items.map((entry) => (entry.id === updated.id ? updated : entry))
      }))
      setNotice("Document 已保存。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setSaving(false)
    }
  }

  async function saveChunk(item: RagAdminChunkItem, draft: ChunkDraft) {
    setSaving(true)
    setError("")
    try {
      const updated = await updateChunk(token, item.id, {
        title: draft.title,
        content: draft.content,
        sourceRef: draft.sourceRef,
        tags: parseTags(draft.tags),
        isActive: draft.isActive
      })
      setChunks((page) => ({
        ...page,
        items: page.items.map((entry) => (entry.id === updated.id ? updated : entry))
      }))
      setNotice("Chunk 已保存，embedding 元数据已按后端规则处理。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setSaving(false)
    }
  }

  async function saveQuestion(item: RagAdminQuestionItem, draft: QuestionDraft) {
    setSaving(true)
    setError("")
    try {
      const updated = await updateQuestion(token, item.id, {
        difficulty: draft.difficulty,
        tags: parseTags(draft.tags),
        isActive: draft.isActive
      })
      setQuestions((page) => ({
        ...page,
        items: page.items.map((entry) => (entry.id === updated.id ? updated : entry))
      }))
      setNotice("Question 已保存，embedding 元数据已按后端规则处理。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setSaving(false)
    }
  }

  async function handleReembedChunk(item: RagAdminChunkItem) {
    setReembedding(true)
    setError("")
    try {
      const result = await reembedChunk(token, item.id)
      setChunks((page) => ({
        ...page,
        items: page.items.map((entry) => entry.id === item.id ? {
          ...entry,
          embeddingModel: result.embeddingModel,
          embeddingVersion: result.embeddingVersion,
          contentHash: result.contentHash,
          embeddedAt: result.embeddedAt
        } : entry)
      }))
      setNotice("Chunk embedding 已重跑。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setReembedding(false)
    }
  }

  async function handleReembedQuestion(item: RagAdminQuestionItem) {
    setReembedding(true)
    setError("")
    try {
      const result = await reembedQuestion(token, item.id)
      setQuestions((page) => ({
        ...page,
        items: page.items.map((entry) => entry.id === item.id ? {
          ...entry,
          embeddingModel: result.embeddingModel,
          embeddingVersion: result.embeddingVersion,
          contentHash: result.contentHash,
          embeddedAt: result.embeddedAt
        } : entry)
      }))
      setNotice("Question embedding 已重跑。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setReembedding(false)
    }
  }

  async function handleUploadImport(payload: {
    file: File
    collectionTitle: string
    title: string
    chunkSize: number
    chunkOverlap: number
  }) {
    setUploading(true)
    setError("")
    setNotice("")
    try {
      const created = await uploadImportJob(token, payload)
      setImports((page) => ({ ...page, items: [created, ...page.items], total: page.total + 1 }))
      setSelectedIds((current) => ({ ...current, imports: created.id }))
      setImportHealth(await getImportHealth(token))
      setNotice("导入任务已入队，Imports 顶部会显示队列和 worker 状态。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setUploading(false)
    }
  }

  async function handleRetryImport(item: RagImportJobItem) {
    setSaving(true)
    setError("")
    setNotice("")
    try {
      const updated = await retryImportJob(token, item.id)
      setImports((page) => ({
        ...page,
        items: page.items.map((entry) => (entry.id === updated.id ? updated : entry))
      }))
      setImportHealth(await getImportHealth(token))
      setNotice("导入任务已重新入队。")
    } catch (errorValue) {
      handleAuthError(errorValue)
    } finally {
      setSaving(false)
    }
  }

  if (!token) {
    return (
      <main className="token-screen">
        <form className="token-panel" onSubmit={submitToken}>
          <div>
            <p className="eyebrow">Brain Rush Admin</p>
            <h1>RAG 知识库管理</h1>
            <p className="muted">输入后端配置的 ADMIN_API_TOKEN，进入内部管理工作台。</p>
          </div>
          <label className="field">
            <span>Admin Token</span>
            <input
              type="password"
              value={tokenInput}
              autoFocus
              placeholder="X-Admin-Token"
              onChange={(event) => setTokenInput(event.target.value)}
            />
          </label>
          {error ? <div className="alert error">{error}</div> : null}
          <button type="submit" className="primary-button">进入管理端</button>
          <p className="small-muted">API: {API_BASE_URL}</p>
        </form>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <span className="brand-mark">BR</span>
          <div>
            <strong>RAG Admin</strong>
            <span>Knowledge Ops</span>
          </div>
        </div>
        <nav className="nav-list">
          {views.map((view) => (
            <button
              key={view.id}
              className={activeView === view.id ? "nav-item active" : "nav-item"}
              type="button"
              onClick={() => selectView(view.id)}
            >
              <span>{view.label}</span>
              <small>{view.description}</small>
            </button>
          ))}
        </nav>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <p className="eyebrow">API</p>
            <strong>{API_BASE_URL}</strong>
          </div>
          <div className="toolbar-actions">
            <button type="button" className="ghost-button" onClick={() => void refresh(activeView)}>
              {loading ? "刷新中..." : "刷新"}
            </button>
            <button type="button" className="ghost-button danger" onClick={logout}>退出管理</button>
          </div>
        </header>

        <div className="content-grid">
          <section className="list-pane">
            <ViewHeader view={activeView} collections={collections} documents={documents.items} />
            {activeView !== "collections" && activeView !== "imports" && activeView !== "debug" ? (
              <FilterBar
                view={activeView}
                filters={filters}
                collections={collections}
                documents={documents.items}
                onChange={updateFilter}
                onApply={() => void refresh(activeView, 0)}
              />
            ) : null}
            {error ? <div className="alert error">{error}</div> : null}
            {notice ? <div className="alert success">{notice}</div> : null}
            {activeView === "collections" ? (
              <CollectionList
                items={collections}
                selectedId={selectedCollection?.id}
                onSelect={(id) => setSelectedIds((current) => ({ ...current, collections: id }))}
              />
            ) : null}
            {activeView === "documents" ? (
              <DocumentList
                page={documents}
                selectedId={selectedDocument?.id}
                loading={loading}
                onSelect={(id) => setSelectedIds((current) => ({ ...current, documents: id }))}
                onPage={(offset) => void refresh("documents", offset)}
              />
            ) : null}
            {activeView === "chunks" ? (
              <ChunkList
                page={chunks}
                selectedId={selectedChunk?.id}
                loading={loading}
                onSelect={(id) => setSelectedIds((current) => ({ ...current, chunks: id }))}
                onPage={(offset) => void refresh("chunks", offset)}
              />
            ) : null}
            {activeView === "questions" ? (
              <QuestionList
                page={questions}
                selectedId={selectedQuestion?.id}
                loading={loading}
                onSelect={(id) => setSelectedIds((current) => ({ ...current, questions: id }))}
                onPage={(offset) => void refresh("questions", offset)}
              />
            ) : null}
            {activeView === "imports" ? (
              <ImportWorkspace
                page={imports}
                collections={collections}
                selectedId={selectedImport?.id}
                loading={loading}
                uploading={uploading}
                saving={saving}
                health={importHealth}
                status={filters.status}
                onStatusChange={(status) => updateFilter("status", status)}
                onApply={() => void refresh("imports", 0)}
                onUpload={handleUploadImport}
                onRetry={handleRetryImport}
                onSelect={(id) => setSelectedIds((current) => ({ ...current, imports: id }))}
                onPage={(offset) => void refresh("imports", offset)}
              />
            ) : null}
            {activeView === "debug" ? (
              <DebugPanel token={token} onError={handleAuthError} />
            ) : null}
          </section>

          <aside className="inspector">
            {activeView === "collections" && selectedCollection ? (
              <CollectionInspector item={selectedCollection} saving={saving} onSave={saveCollection} />
            ) : null}
            {activeView === "documents" && selectedDocument ? (
              <DocumentInspector item={selectedDocument} saving={saving} onSave={saveDocument} />
            ) : null}
            {activeView === "chunks" && selectedChunk ? (
              <ChunkInspector
                item={selectedChunk}
                saving={saving}
                reembedding={reembedding}
                onSave={saveChunk}
                onReembed={handleReembedChunk}
              />
            ) : null}
            {activeView === "questions" && selectedQuestion ? (
              <QuestionInspector
                item={selectedQuestion}
                saving={saving}
                reembedding={reembedding}
                onSave={saveQuestion}
                onReembed={handleReembedQuestion}
              />
            ) : null}
            {activeView === "imports" && selectedImport ? (
              <ImportInspector
                item={selectedImport}
                saving={saving}
                health={importHealth}
                onRetry={handleRetryImport}
              />
            ) : null}
            {activeView === "debug" ? (
              <DebugInspector />
            ) : null}
            {!selectedCollection && activeView === "collections" ? <EmptyInspector /> : null}
            {!selectedDocument && activeView === "documents" ? <EmptyInspector /> : null}
            {!selectedChunk && activeView === "chunks" ? <EmptyInspector /> : null}
            {!selectedQuestion && activeView === "questions" ? <EmptyInspector /> : null}
            {!selectedImport && activeView === "imports" ? <EmptyInspector /> : null}
          </aside>
        </div>
      </section>
    </main>
  )
}

function ViewHeader({
  view,
  collections,
  documents
}: {
  view: AdminView
  collections: RagAdminCollectionItem[]
  documents: RagAdminDocumentItem[]
}) {
  const config = views.find((item) => item.id === view)!
  const totals = collections.reduce(
    (result, item) => ({
      documents: result.documents + item.documentCount,
      chunks: result.chunks + item.chunkCount,
      questions: result.questions + item.questionCount
    }),
    { documents: 0, chunks: 0, questions: 0 }
  )

  return (
    <div className="view-header">
      <div>
        <h1>{config.label}</h1>
        <p>{config.description}</p>
      </div>
      <div className="summary-strip">
        <span>{collections.length} collections</span>
        <span>{view === "chunks" ? documents.length : totals.documents} documents</span>
        <span>{totals.chunks} chunks</span>
        <span>{totals.questions} questions</span>
      </div>
    </div>
  )
}

function FilterBar({
  view,
  filters,
  collections,
  documents,
  onChange,
  onApply
}: {
  view: AdminView
  filters: ListFilters
  collections: RagAdminCollectionItem[]
  documents: RagAdminDocumentItem[]
  onChange: <K extends keyof ListFilters>(key: K, value: ListFilters[K]) => void
  onApply: () => void
}) {
  return (
    <div className="filter-bar">
      <select value={filters.collectionId} onChange={(event) => onChange("collectionId", event.target.value)}>
        <option value="">All collections</option>
        {collections.map((item) => (
          <option key={item.id} value={item.id}>{item.title}</option>
        ))}
      </select>
      {view === "chunks" ? (
        <select value={filters.documentId} onChange={(event) => onChange("documentId", event.target.value)}>
          <option value="">All documents</option>
          {documents.map((item) => (
            <option key={item.id} value={item.id}>{item.title}</option>
          ))}
        </select>
      ) : null}
      {view === "documents" ? (
        <input
          value={filters.status}
          placeholder="status"
          onChange={(event) => onChange("status", event.target.value)}
        />
      ) : null}
      <select value={filters.isActive} onChange={(event) => onChange("isActive", event.target.value as ListFilters["isActive"])}>
        <option value="all">All active states</option>
        <option value="true">Active</option>
        <option value="false">Inactive</option>
      </select>
      <input
        className="search-input"
        value={filters.q}
        placeholder="Search title, content, source..."
        onChange={(event) => onChange("q", event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") onApply()
        }}
      />
      <button type="button" className="primary-button compact" onClick={onApply}>应用筛选</button>
    </div>
  )
}

function CollectionList({
  items,
  selectedId,
  onSelect
}: {
  items: RagAdminCollectionItem[]
  selectedId?: string
  onSelect: (id: string) => void
}) {
  if (!items.length) return <EmptyList label="暂无 collections" />
  return (
    <div className="row-list">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={selectedId === item.id ? "data-row selected" : "data-row"}
          onClick={() => onSelect(item.id)}
        >
          <div>
            <strong>{item.title}</strong>
            <span>{item.description || "No description"}</span>
          </div>
          <div className="row-meta">
            <span className={statusTone(item.isActive)}>{activeLabel(item.isActive)}</span>
            <span>{item.documentCount} docs</span>
            <span>{item.chunkCount} chunks</span>
            <span>{item.questionCount} questions</span>
          </div>
        </button>
      ))}
    </div>
  )
}

function DocumentList({
  page,
  selectedId,
  loading,
  onSelect,
  onPage
}: {
  page: PageState<RagAdminDocumentItem>
  selectedId?: string
  loading: boolean
  onSelect: (id: string) => void
  onPage: (offset: number) => void
}) {
  return (
    <>
      <PagedHeader page={page} loading={loading} onPage={onPage} />
      {!page.items.length ? <EmptyList label="暂无 documents" /> : (
        <div className="row-list">
          {page.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={selectedId === item.id ? "data-row selected" : "data-row"}
              onClick={() => onSelect(item.id)}
            >
              <div>
                <strong>{item.title}</strong>
                <span>{item.sourceType} · {item.sourceUri || "No source URI"}</span>
              </div>
              <div className="row-meta">
                <span className={statusTone(item.isActive)}>{activeLabel(item.isActive)}</span>
                <span>{item.status}</span>
                <span>{item.chunkCount} chunks</span>
                <span>{formatDate(item.updatedAt)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  )
}

function ChunkList({
  page,
  selectedId,
  loading,
  onSelect,
  onPage
}: {
  page: PageState<RagAdminChunkItem>
  selectedId?: string
  loading: boolean
  onSelect: (id: string) => void
  onPage: (offset: number) => void
}) {
  return (
    <>
      <PagedHeader page={page} loading={loading} onPage={onPage} />
      {!page.items.length ? <EmptyList label="暂无 chunks" /> : (
        <div className="row-list">
          {page.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={selectedId === item.id ? "data-row selected" : "data-row"}
              onClick={() => onSelect(item.id)}
            >
              <div>
                <strong>{item.title}</strong>
                <span>{textPreview(item.content)}</span>
              </div>
              <div className="row-meta">
                <span className={statusTone(item.isActive)}>{activeLabel(item.isActive)}</span>
                <span>{item.documentTitle || "Legacy chunk"}</span>
                <span>{embeddingLabel(item.embeddedAt)}</span>
                <span>{formatDate(item.createdAt)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  )
}

function QuestionList({
  page,
  selectedId,
  loading,
  onSelect,
  onPage
}: {
  page: PageState<RagAdminQuestionItem>
  selectedId?: string
  loading: boolean
  onSelect: (id: string) => void
  onPage: (offset: number) => void
}) {
  return (
    <>
      <PagedHeader page={page} loading={loading} onPage={onPage} />
      {!page.items.length ? <EmptyList label="暂无 questions" /> : (
        <div className="row-list">
          {page.items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={selectedId === item.id ? "data-row selected" : "data-row"}
              onClick={() => onSelect(item.id)}
            >
              <div>
                <strong>{item.knowledgePoint}</strong>
                <span>{textPreview(item.stem)}</span>
              </div>
              <div className="row-meta">
                <span className={statusTone(item.isActive)}>{activeLabel(item.isActive)}</span>
                <span>{item.questionType}</span>
                <span>{item.difficulty}</span>
                <span>{embeddingLabel(item.embeddedAt)}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  )
}

function ImportWorkspace({
  page,
  collections,
  selectedId,
  loading,
  uploading,
  saving,
  health,
  status,
  onStatusChange,
  onApply,
  onUpload,
  onRetry,
  onSelect,
  onPage
}: {
  page: PageState<RagImportJobItem>
  collections: RagAdminCollectionItem[]
  selectedId?: string
  loading: boolean
  uploading: boolean
  saving: boolean
  health: RagImportHealthResponse | null
  status: string
  onStatusChange: (status: string) => void
  onApply: () => void
  onUpload: (payload: {
    file: File
    collectionTitle: string
    title: string
    chunkSize: number
    chunkOverlap: number
  }) => Promise<void>
  onRetry: (item: RagImportJobItem) => Promise<void>
  onSelect: (id: string) => void
  onPage: (offset: number) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [collectionTitle, setCollectionTitle] = useState(collections[0]?.title || "")
  const [title, setTitle] = useState("")
  const [chunkSize, setChunkSize] = useState(1200)
  const [chunkOverlap, setChunkOverlap] = useState(150)
  const [localError, setLocalError] = useState("")

  useEffect(() => {
    if (!collectionTitle && collections[0]) {
      setCollectionTitle(collections[0].title)
    }
  }, [collectionTitle, collections])

  async function submitUpload(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setLocalError("请选择要上传的 .txt、.md 或 .pdf 文件。")
      return
    }
    if (!collectionTitle.trim()) {
      setLocalError("请选择或填写 collection。")
      return
    }
    if (chunkOverlap >= chunkSize) {
      setLocalError("Chunk overlap 必须小于 chunk size。")
      return
    }
    setLocalError("")
    await onUpload({
      file,
      collectionTitle: collectionTitle.trim(),
      title: title.trim(),
      chunkSize,
      chunkOverlap
    })
    setFile(null)
    setTitle("")
  }

  return (
    <div className="imports-workspace">
      <ImportHealthPanel health={health} />
      <form className="import-upload" onSubmit={(event) => void submitUpload(event)}>
        <label className="field">
          <span>File</span>
          <input
            type="file"
            accept=".txt,.md,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <label className="field">
          <span>Collection</span>
          <input
            list="collection-title-options"
            value={collectionTitle}
            onChange={(event) => setCollectionTitle(event.target.value)}
          />
          <datalist id="collection-title-options">
            {collections.map((item) => <option key={item.id} value={item.title} />)}
          </datalist>
        </label>
        <label className="field">
          <span>Title</span>
          <input
            value={title}
            placeholder="默认使用文件名"
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="field compact-field">
          <span>Size</span>
          <input
            type="number"
            min={200}
            max={5000}
            value={chunkSize}
            onChange={(event) => setChunkSize(Number(event.target.value))}
          />
        </label>
        <label className="field compact-field">
          <span>Overlap</span>
          <input
            type="number"
            min={0}
            max={1000}
            value={chunkOverlap}
            onChange={(event) => setChunkOverlap(Number(event.target.value))}
          />
        </label>
        <button className="primary-button" type="submit" disabled={uploading}>
          {uploading ? "上传中..." : "上传并入队"}
        </button>
      </form>
      {localError ? <div className="alert error">{localError}</div> : null}
      <div className="import-filter">
        <select value={status} onChange={(event) => onStatusChange(event.target.value)}>
          <option value="">All statuses</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="succeeded">succeeded</option>
          <option value="failed">failed</option>
        </select>
        <button type="button" className="primary-button compact" onClick={onApply}>应用筛选</button>
      </div>
      <ImportList
        page={page}
        selectedId={selectedId}
        loading={loading}
        saving={saving}
        health={health}
        onSelect={onSelect}
        onRetry={onRetry}
        onPage={onPage}
      />
    </div>
  )
}

function ImportHealthPanel({ health }: { health: RagImportHealthResponse | null }) {
  if (!health) {
    return (
      <div className="import-health">
        <div>
          <p className="eyebrow">Import health</p>
          <strong>等待健康检查</strong>
        </div>
        <div className="summary-strip">
          <span>Redis -</span>
          <span>waiting -</span>
          <span>workers -</span>
        </div>
      </div>
    )
  }

  return (
    <div className={health.redisOk ? "import-health" : "import-health unhealthy"}>
      <div>
        <p className="eyebrow">Import health</p>
        <strong>{health.redisOk ? "导入队列正常" : "导入队列异常"}</strong>
      </div>
      <div className="summary-strip">
        <span className={health.redisOk ? "pill pill-green" : "pill pill-red"}>
          Redis {health.redisOk ? "正常" : "异常"}
        </span>
        <span>waiting {health.queuedCount}</span>
        <span>workers {health.workerCount}</span>
        <span className={health.staleQueuedCount ? "pill pill-red" : "pill pill-muted"}>
          stale queued {health.staleQueuedCount}
        </span>
        <span className={health.staleRunningCount ? "pill pill-red" : "pill pill-muted"}>
          stale running {health.staleRunningCount}
        </span>
      </div>
      {!health.redisOk && health.errorMessage ? (
        <div className="alert error import-health-error">{health.errorMessage}</div>
      ) : null}
    </div>
  )
}

function ImportList({
  page,
  selectedId,
  loading,
  saving,
  health,
  onSelect,
  onRetry,
  onPage
}: {
  page: PageState<RagImportJobItem>
  selectedId?: string
  loading: boolean
  saving: boolean
  health: RagImportHealthResponse | null
  onSelect: (id: string) => void
  onRetry: (item: RagImportJobItem) => Promise<void>
  onPage: (offset: number) => void
}) {
  return (
    <>
      <PagedHeader page={page} loading={loading} onPage={onPage} />
      {!page.items.length ? <EmptyList label="暂无 import jobs" /> : (
        <div className="row-list">
          {page.items.map((item) => (
            <div key={item.id} className={selectedId === item.id ? "data-row import-row selected" : "data-row import-row"}>
              <button type="button" className="row-main-button" onClick={() => onSelect(item.id)}>
                <div>
                  <strong>{item.fileName}</strong>
                  <span>{item.collectionTitle} · {item.documentTitle || "默认标题"}</span>
                  {importStatusHint(item, health) ? (
                    <p className="row-hint">{importStatusHint(item, health)}</p>
                  ) : null}
                </div>
                <div className="row-meta">
                  <span className={jobStatusTone(item.status)}>{item.status}</span>
                  <span>{importStatsLabel(item)}</span>
                  {item.isStale ? <span className="pill pill-red">stale</span> : null}
                  <span>{formatDate(item.createdAt)}</span>
                </div>
              </button>
              {item.status !== "succeeded" ? (
                <button
                  type="button"
                  className="ghost-button compact"
                  disabled={saving}
                  onClick={() => void onRetry(item)}
                >
                  {item.status === "failed" ? "Retry" : "Requeue"}
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </>
  )
}

function DebugPanel({
  token,
  onError
}: {
  token: string
  onError: (error: unknown) => void
}) {
  const [query, setQuery] = useState("RAG 检索效果怎么优化")
  const [limit, setLimit] = useState(5)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [result, setResult] = useState<RagDebugResponse | null>(null)

  async function runDebug(event?: FormEvent) {
    event?.preventDefault()
    const normalized = query.trim()
    if (!normalized) {
      setError("请输入要调试的查询。")
      return
    }
    const normalizedLimit = Number.isFinite(limit) ? Math.min(20, Math.max(1, limit)) : 5
    setLimit(normalizedLimit)
    setLoading(true)
    setError("")
    try {
      setResult(await debugRag(token, { query: normalized, limit: normalizedLimit }))
    } catch (errorValue) {
      setError(friendlyError(errorValue))
      onError(errorValue)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="debug-workspace">
      <form className="debug-query" onSubmit={(event) => void runDebug(event)}>
        <label className="field">
          <span>Query</span>
          <textarea
            rows={3}
            value={query}
            placeholder="输入一次学习主题或检索问题"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="field compact-field">
          <span>Limit</span>
          <input
            type="number"
            min={1}
            max={20}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
        </label>
        <button className="primary-button" type="submit" disabled={loading}>
          {loading ? "检索中..." : "运行 Debug"}
        </button>
      </form>

      {error ? <div className="alert error">{error}</div> : null}

      {result ? (
        <div className="debug-results">
          <div className="debug-result-head">
            <div>
              <p className="eyebrow">Retrieval</p>
              <h2>{result.retrievalVersion}</h2>
            </div>
            <div className="summary-strip">
              <span>{result.questions.length} questions</span>
              <span>{result.chunks.length} chunks</span>
            </div>
          </div>
          <DebugMatchSection title="Questions" items={result.questions} />
          <DebugMatchSection title="Chunks" items={result.chunks} />
        </div>
      ) : (
        <div className="empty-list">输入 query 后运行 Debug，查看 RAG 命中详情。</div>
      )}
    </div>
  )
}

function DebugMatchSection({ title, items }: { title: string; items: RagDebugMatch[] }) {
  return (
    <section className="debug-section">
      <div className="debug-section-title">
        <h3>{title}</h3>
        <span>{items.length} matches</span>
      </div>
      {!items.length ? <div className="empty-list compact-empty">暂无命中</div> : null}
      <div className="debug-match-list">
        {items.map((item) => (
          <article key={`${item.kind}_${item.id}`} className="debug-match">
            <div className="debug-match-main">
              <div>
                <p className="eyebrow">{item.kind} · {item.collectionTitle}</p>
                <h4>{item.title}</h4>
              </div>
              <div className="score-grid">
                <Metric label="Keyword" value={item.keywordScore} />
                <Metric label="Vector" value={item.vectorScore} />
                <Metric label="Total" value={item.totalScore} />
              </div>
            </div>
            <div className="row-meta debug-meta">
              <span>keywordRank {item.keywordRank ?? "-"}</span>
              <span>vectorRank {item.vectorRank ?? "-"}</span>
              <span>{item.fusionMethod}</span>
              {item.sourceRef ? <span>{item.sourceRef}</span> : null}
            </div>
            {item.tags.length ? (
              <div className="tag-row">
                {item.tags.map((tag) => <span key={tag}>{tag}</span>)}
              </div>
            ) : null}
            <BreakdownBars breakdown={item.keywordScoreBreakdown} />
          </article>
        ))}
      </div>
    </section>
  )
}

function BreakdownBars({ breakdown }: { breakdown: RagDebugMatch["keywordScoreBreakdown"] }) {
  const entries = Object.entries(breakdown)
  const max = Math.max(...entries.map(([, value]) => value), 0.0001)
  return (
    <div className="breakdown-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="breakdown-row">
          <span>{key}</span>
          <div>
            <i style={{ width: `${Math.max(3, (value / max) * 100)}%` }} />
          </div>
          <strong>{value.toFixed(4)}</strong>
        </div>
      ))}
    </div>
  )
}

function PagedHeader<T>({
  page,
  loading,
  onPage
}: {
  page: PageState<T>
  loading: boolean
  onPage: (offset: number) => void
}) {
  const start = page.total ? page.offset + 1 : 0
  const end = Math.min(page.offset + page.items.length, page.total)
  return (
    <div className="page-row">
      <span>{loading ? "Loading..." : `${start}-${end} / ${page.total}`}</span>
      <div>
        <button
          type="button"
          className="ghost-button small"
          disabled={page.offset <= 0 || loading}
          onClick={() => onPage(Math.max(0, page.offset - page.limit))}
        >
          上一页
        </button>
        <button
          type="button"
          className="ghost-button small"
          disabled={page.offset + page.limit >= page.total || loading}
          onClick={() => onPage(page.offset + page.limit)}
        >
          下一页
        </button>
      </div>
    </div>
  )
}

type CollectionDraft = {
  description: string
  tags: string
  isActive: boolean
}

function CollectionInspector({
  item,
  saving,
  onSave
}: {
  item: RagAdminCollectionItem
  saving: boolean
  onSave: (item: RagAdminCollectionItem, draft: CollectionDraft) => Promise<void>
}) {
  const [draft, setDraft] = useState<CollectionDraft>({
    description: item.description,
    tags: tagsText(item.tags),
    isActive: item.isActive
  })

  useEffect(() => {
    setDraft({ description: item.description, tags: tagsText(item.tags), isActive: item.isActive })
  }, [item])

  return (
    <InspectorFrame title={item.title} eyebrow="Collection">
      <Readonly label="ID" value={item.id} />
      <Readonly label="Source type" value={item.sourceType} />
      <div className="metric-grid">
        <Metric label="Documents" value={item.documentCount} />
        <Metric label="Chunks" value={item.chunkCount} />
        <Metric label="Questions" value={item.questionCount} />
      </div>
      <TextareaField label="Description" value={draft.description} onChange={(value) => setDraft({ ...draft, description: value })} />
      <TextField label="Tags" value={draft.tags} onChange={(value) => setDraft({ ...draft, tags: value })} />
      <ToggleField label="Active" checked={draft.isActive} onChange={(value) => setDraft({ ...draft, isActive: value })} />
      <button className="primary-button" type="button" disabled={saving} onClick={() => void onSave(item, draft)}>
        {saving ? "保存中..." : "保存 Collection"}
      </button>
    </InspectorFrame>
  )
}

type DocumentDraft = {
  title: string
  sourceUri: string
  metadata: string
  status: string
  isActive: boolean
}

function DocumentInspector({
  item,
  saving,
  onSave
}: {
  item: RagAdminDocumentItem
  saving: boolean
  onSave: (item: RagAdminDocumentItem, draft: DocumentDraft) => Promise<void>
}) {
  const [draft, setDraft] = useState<DocumentDraft>({
    title: item.title,
    sourceUri: item.sourceUri,
    metadata: JSON.stringify(item.metadata, null, 2),
    status: item.status,
    isActive: item.isActive
  })

  useEffect(() => {
    setDraft({
      title: item.title,
      sourceUri: item.sourceUri,
      metadata: JSON.stringify(item.metadata, null, 2),
      status: item.status,
      isActive: item.isActive
    })
  }, [item])

  return (
    <InspectorFrame title={item.title} eyebrow="Document">
      <Readonly label="Collection" value={item.collectionTitle} />
      <Readonly label="Source type" value={item.sourceType} />
      <Readonly label="Content hash" value={item.contentHash || "-"} />
      <TextField label="Title" value={draft.title} onChange={(value) => setDraft({ ...draft, title: value })} />
      <TextField label="Source URI" value={draft.sourceUri} onChange={(value) => setDraft({ ...draft, sourceUri: value })} />
      <TextField label="Status" value={draft.status} onChange={(value) => setDraft({ ...draft, status: value })} />
      <TextareaField label="Metadata JSON" rows={10} value={draft.metadata} onChange={(value) => setDraft({ ...draft, metadata: value })} />
      <ToggleField label="Active" checked={draft.isActive} onChange={(value) => setDraft({ ...draft, isActive: value })} />
      <button className="primary-button" type="button" disabled={saving} onClick={() => void onSave(item, draft)}>
        {saving ? "保存中..." : "保存 Document"}
      </button>
    </InspectorFrame>
  )
}

type ChunkDraft = {
  title: string
  content: string
  sourceRef: string
  tags: string
  isActive: boolean
}

function ChunkInspector({
  item,
  saving,
  reembedding,
  onSave,
  onReembed
}: {
  item: RagAdminChunkItem
  saving: boolean
  reembedding: boolean
  onSave: (item: RagAdminChunkItem, draft: ChunkDraft) => Promise<void>
  onReembed: (item: RagAdminChunkItem) => Promise<void>
}) {
  const [draft, setDraft] = useState<ChunkDraft>({
    title: item.title,
    content: item.content,
    sourceRef: item.sourceRef,
    tags: tagsText(item.tags),
    isActive: item.isActive
  })

  useEffect(() => {
    setDraft({
      title: item.title,
      content: item.content,
      sourceRef: item.sourceRef,
      tags: tagsText(item.tags),
      isActive: item.isActive
    })
  }, [item])

  return (
    <InspectorFrame title={item.title} eyebrow="Chunk">
      <Readonly label="Collection" value={item.collectionTitle} />
      <Readonly label="Document" value={item.documentTitle || "Legacy chunk"} />
      <EmbeddingBlock model={item.embeddingModel} version={item.embeddingVersion} hash={item.contentHash} embeddedAt={item.embeddedAt} />
      <TextField label="Title" value={draft.title} onChange={(value) => setDraft({ ...draft, title: value })} />
      <TextField label="Source ref" value={draft.sourceRef} onChange={(value) => setDraft({ ...draft, sourceRef: value })} />
      <TextField label="Tags" value={draft.tags} onChange={(value) => setDraft({ ...draft, tags: value })} />
      <TextareaField label="Content" rows={14} value={draft.content} onChange={(value) => setDraft({ ...draft, content: value })} />
      <ToggleField label="Active" checked={draft.isActive} onChange={(value) => setDraft({ ...draft, isActive: value })} />
      <div className="action-row">
        <button className="primary-button" type="button" disabled={saving} onClick={() => void onSave(item, draft)}>
          {saving ? "保存中..." : "保存 Chunk"}
        </button>
        <button className="ghost-button" type="button" disabled={reembedding} onClick={() => void onReembed(item)}>
          {reembedding ? "重跑中..." : "Reembed"}
        </button>
      </div>
    </InspectorFrame>
  )
}

type QuestionDraft = {
  difficulty: string
  tags: string
  isActive: boolean
}

function QuestionInspector({
  item,
  saving,
  reembedding,
  onSave,
  onReembed
}: {
  item: RagAdminQuestionItem
  saving: boolean
  reembedding: boolean
  onSave: (item: RagAdminQuestionItem, draft: QuestionDraft) => Promise<void>
  onReembed: (item: RagAdminQuestionItem) => Promise<void>
}) {
  const [draft, setDraft] = useState<QuestionDraft>({
    difficulty: item.difficulty,
    tags: tagsText(item.tags),
    isActive: item.isActive
  })

  useEffect(() => {
    setDraft({ difficulty: item.difficulty, tags: tagsText(item.tags), isActive: item.isActive })
  }, [item])

  return (
    <InspectorFrame title={item.knowledgePoint} eyebrow="Question">
      <Readonly label="Collection" value={item.collectionTitle} />
      <Readonly label="Question type" value={item.questionType} />
      <Readonly label="Stem" value={item.stem} multiline />
      <Readonly label="Options" value={item.options.map((option, index) => `${index}. ${option}`).join("\n")} multiline />
      <Readonly label="Answers" value={item.answerIndexes.join(", ")} />
      <Readonly label="Explanation" value={item.explanation} multiline />
      <EmbeddingBlock model={item.embeddingModel} version={item.embeddingVersion} hash={item.contentHash} embeddedAt={item.embeddedAt} />
      <TextField label="Difficulty" value={draft.difficulty} onChange={(value) => setDraft({ ...draft, difficulty: value })} />
      <TextField label="Tags" value={draft.tags} onChange={(value) => setDraft({ ...draft, tags: value })} />
      <ToggleField label="Active" checked={draft.isActive} onChange={(value) => setDraft({ ...draft, isActive: value })} />
      <div className="action-row">
        <button className="primary-button" type="button" disabled={saving} onClick={() => void onSave(item, draft)}>
          {saving ? "保存中..." : "保存 Question"}
        </button>
        <button className="ghost-button" type="button" disabled={reembedding} onClick={() => void onReembed(item)}>
          {reembedding ? "重跑中..." : "Reembed"}
        </button>
      </div>
    </InspectorFrame>
  )
}

function InspectorFrame({
  title,
  eyebrow,
  children
}: {
  title: string
  eyebrow: string
  children: React.ReactNode
}) {
  return (
    <div className="inspector-frame">
      <div className="inspector-title">
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  )
}

function ImportInspector({
  item,
  saving,
  health,
  onRetry
}: {
  item: RagImportJobItem
  saving: boolean
  health: RagImportHealthResponse | null
  onRetry: (item: RagImportJobItem) => Promise<void>
}) {
  const hint = importStatusHint(item, health)
  return (
    <InspectorFrame title={item.fileName} eyebrow="Import job">
      <div className="summary-strip inspector-status">
        <span className={jobStatusTone(item.status)}>{item.status}</span>
        {item.isStale ? <span className="pill pill-red">stale</span> : null}
      </div>
      {hint ? <div className="alert import-hint">{hint}</div> : null}
      <Readonly label="ID" value={item.id} />
      <Readonly label="Queue job" value={item.queueJobId || "-"} />
      <Readonly label="Collection" value={item.collectionTitle} />
      <Readonly label="Document title" value={item.documentTitle || "-"} />
      <Readonly label="Source URI" value={item.sourceUri || "-"} multiline />
      <div className="metric-grid">
        <Metric label="Chunk size" value={item.chunkSize} />
        <Metric label="Overlap" value={item.chunkOverlap} />
      </div>
      <Readonly label="Stats" value={JSON.stringify(item.stats, null, 2)} multiline />
      {item.errorMessage ? <Readonly label="Error" value={item.errorMessage} multiline /> : null}
      <Readonly label="Created" value={formatDate(item.createdAt)} />
      <Readonly label="Started" value={formatDate(item.startedAt)} />
      <Readonly label="Finished" value={formatDate(item.finishedAt)} />
      {item.status !== "succeeded" ? (
        <button className="primary-button" type="button" disabled={saving} onClick={() => void onRetry(item)}>
          {saving ? "入队中..." : item.status === "failed" ? "Retry Import" : "Requeue Import"}
        </button>
      ) : null}
    </InspectorFrame>
  )
}

function EmptyInspector() {
  return (
    <div className="empty-inspector">
      <h2>未选择项目</h2>
      <p>从左侧列表选择一条记录后，可以查看详情并编辑允许字段。</p>
    </div>
  )
}

function DebugInspector() {
  return (
    <div className="empty-inspector">
      <h2>检索调试</h2>
      <p>用真实 query 查看关键词、向量和 RRF 融合后的命中结果，判断知识库是否需要补充或调整。</p>
    </div>
  )
}

function EmptyList({ label }: { label: string }) {
  return <div className="empty-list">{label}</div>
}

function TextField({
  label,
  value,
  onChange
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function TextareaField({
  label,
  value,
  rows = 5,
  onChange
}: {
  label: string
  value: string
  rows?: number
  onChange: (value: string) => void
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea rows={rows} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function ToggleField({
  label,
  checked,
  onChange
}: {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="toggle-field">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  )
}

function Readonly({
  label,
  value,
  multiline = false
}: {
  label: string
  value: string
  multiline?: boolean
}) {
  return (
    <div className={multiline ? "readonly multiline" : "readonly"}>
      <span>{label}</span>
      <p>{value}</p>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  )
}

function EmbeddingBlock({
  model,
  version,
  hash,
  embeddedAt
}: {
  model?: string | null
  version?: string | null
  hash?: string | null
  embeddedAt?: string | null
}) {
  return (
    <div className="embedding-block">
      <div className="embedding-head">
        <span className={embeddedAt ? "pill pill-green" : "pill pill-muted"}>{embeddingLabel(embeddedAt)}</span>
        <span>{formatDate(embeddedAt)}</span>
      </div>
      <Readonly label="Model" value={model || "-"} />
      <Readonly label="Version" value={version || "-"} />
      <Readonly label="Content hash" value={hash || "-"} />
    </div>
  )
}
