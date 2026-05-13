import { FormEvent, useEffect, useMemo, useState } from "react"

import {
  API_BASE_URL,
  listChunks,
  listCollections,
  listDocuments,
  listQuestions,
  reembedChunk,
  reembedQuestion,
  updateChunk,
  updateCollection,
  updateDocument,
  updateQuestion
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
  type RagAdminQuestionItem
} from "./types"

const PAGE_LIMIT = 50

const views: Array<{ id: AdminView; label: string; description: string }> = [
  { id: "collections", label: "Collections", description: "知识库集合" },
  { id: "documents", label: "Documents", description: "资料来源" },
  { id: "chunks", label: "Chunks", description: "知识片段" },
  { id: "questions", label: "Questions", description: "精选题" }
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

function textPreview(value: string, length = 120): string {
  if (value.length <= length) return value
  return `${value.slice(0, length)}...`
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
  const [selectedIds, setSelectedIds] = useState<Record<AdminView, string>>({
    collections: "",
    documents: "",
    chunks: "",
    questions: ""
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
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

  useEffect(() => {
    if (!token) return
    void refresh(activeView, 0)
  }, [token, activeView])

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
            {activeView !== "collections" ? (
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
            {!selectedCollection && activeView === "collections" ? <EmptyInspector /> : null}
            {!selectedDocument && activeView === "documents" ? <EmptyInspector /> : null}
            {!selectedChunk && activeView === "chunks" ? <EmptyInspector /> : null}
            {!selectedQuestion && activeView === "questions" ? <EmptyInspector /> : null}
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

function EmptyInspector() {
  return (
    <div className="empty-inspector">
      <h2>未选择项目</h2>
      <p>从左侧列表选择一条记录后，可以查看详情并编辑允许字段。</p>
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
