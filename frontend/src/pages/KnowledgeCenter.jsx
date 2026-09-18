// [RAG] issue #225 — Knowledge Center (Phase 9, #268-#274). Upload,
// browse, search, and manage the real policy/manual documents
// specialists ground answers in via the search_knowledge tool.
import { useEffect, useRef, useState } from "react";
import {
  deleteKnowledgeDocument,
  fetchKnowledgeDocument,
  fetchKnowledgeDocuments,
  reprocessKnowledgeDocument,
  searchKnowledge,
  uploadKnowledgeDocument,
} from "../api/client";
import Can from "../auth/Can";
import "./KnowledgeCenter.css";

const STATUS_BADGE = {
  uploaded: "badge-info",
  processing: "badge-warning",
  indexed: "badge-success",
  failed: "badge-danger",
};

const STATUS_LABEL = {
  uploaded: "Uploaded",
  processing: "Processing",
  indexed: "Indexed",
  failed: "Failed",
};

function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  const kb = bytes / 1024;
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

function formatTimestamp(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function UploadForm({ onUploaded }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const reset = () => {
    setTitle("");
    setFile(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Choose a PDF, DOCX, or TXT file to upload.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadKnowledgeDocument(file, title.trim());
      onUploaded(doc);
      reset();
      setOpen(false);
    } catch (err) {
      setError(err.message || "Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="app-btn-primary" style={{ alignSelf: "flex-start" }}>
        + Upload Document
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="app-panel" style={{ gap: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontFamily: "'Syne', sans-serif", color: "var(--app-text-primary)" }}>Upload Document</h3>
        <button type="button" onClick={() => { setOpen(false); reset(); }} className="app-btn-secondary">Cancel</button>
      </div>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--app-text-secondary)" }}>
        PDF, DOCX, or TXT — indexed automatically so specialists can search it via the
        Knowledge Center's semantic search tool.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.85rem" }}>
        <input
          placeholder="Title (defaults to the filename)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="app-input"
          style={{ padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }}
        />
        <input
          required
          type="file"
          accept=".pdf,.docx,.txt"
          ref={fileInputRef}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="app-input"
          style={{ padding: "0.5rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }}
        />
      </div>
      {error && <div className="app-error-banner"><span>{error}</span></div>}
      <button type="submit" disabled={uploading} className="app-btn-primary" style={{ alignSelf: "flex-start" }}>
        {uploading ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}

function DocumentDetail({ documentId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchKnowledgeDocument(documentId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) setError(err.message || "Failed to load document"); });
    return () => { cancelled = true; };
  }, [documentId]);

  return (
    <div className="kc-detail-overlay" onClick={onClose}>
      <div className="kc-detail-panel" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <h3 style={{ margin: 0, fontFamily: "'Syne', sans-serif" }}>{detail?.title || "Loading…"}</h3>
          <button onClick={onClose} className="app-btn-secondary">Close</button>
        </div>
        {error && <div className="app-error-banner"><span>{error}</span></div>}
        {detail && (
          <>
            <p style={{ color: "var(--app-text-muted)", fontSize: "0.85rem" }}>
              {detail.filename} · {detail.chunk_count} chunk(s) · {STATUS_LABEL[detail.status]}
            </p>
            {detail.error_message && (
              <div className="app-error-banner"><span>{detail.error_message}</span></div>
            )}
            <div className="kc-chunk-list">
              {(detail.chunks || []).map((chunk) => (
                <div key={chunk.id} className="kc-chunk-card">
                  <div className="kc-chunk-meta">
                    Chunk #{chunk.chunk_index}
                    {chunk.chunk_metadata?.page_number != null && ` · page ${chunk.chunk_metadata.page_number}`}
                    {chunk.chunk_metadata?.section_heading && ` · ${chunk.chunk_metadata.section_heading}`}
                  </div>
                  <p className="kc-chunk-text">{chunk.text}</p>
                </div>
              ))}
              {detail.chunks?.length === 0 && (
                <div className="app-empty-state"><p>No chunks yet.</p></div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const res = await searchKnowledge(query.trim());
      setResults(res);
    } catch (err) {
      setError(err.message || "Search failed");
      setResults(null);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="app-panel" style={{ gap: "1rem" }}>
      <h3 style={{ margin: 0, fontFamily: "'Syne', sans-serif", color: "var(--app-text-primary)" }}>Test Search</h3>
      <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--app-text-secondary)" }}>
        Try the same semantic search a specialist's search_knowledge tool call uses.
      </p>
      <form onSubmit={handleSearch} style={{ display: "flex", gap: "0.5rem" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. how long does shipping take?"
          className="app-input"
          style={{ flex: 1, padding: "0.6rem 0.8rem", borderRadius: "8px", border: "1px solid var(--app-border)" }}
        />
        <button type="submit" disabled={searching} className="app-btn-primary">
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      {error && <div className="app-error-banner"><span>{error}</span></div>}
      {results && (
        results.length === 0 ? (
          <div className="app-empty-state"><p>No matching passages found.</p></div>
        ) : (
          <div className="kc-chunk-list">
            {results.map((r) => (
              <div key={r.chunk_id} className="kc-chunk-card">
                <div className="kc-chunk-meta">{r.document_title} · match {(r.score * 100).toFixed(0)}%</div>
                <p className="kc-chunk-text">{r.text}</p>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

export default function KnowledgeCenter() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const loadDocuments = () => {
    setLoading(true);
    setError(null);
    fetchKnowledgeDocuments()
      .then(setDocuments)
      .catch((err) => setError(err.message || "Failed to load documents"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDocuments();
    // Poll while anything is still uploaded/processing, so a real upload's
    // status genuinely reaches "indexed" (or "failed") on screen without a
    // manual refresh — matches the honest two-step upload contract the
    // backend's own KnowledgeDocumentUploadOut docstring establishes.
    const interval = setInterval(() => {
      setDocuments((curr) => {
        if (curr.some((d) => d.status === "uploaded" || d.status === "processing")) {
          fetchKnowledgeDocuments().then(setDocuments).catch(() => {});
        }
        return curr;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleDelete = (id) => {
    if (!window.confirm("Delete this document? This removes it from search permanently.")) return;
    setBusyId(id);
    deleteKnowledgeDocument(id)
      .then(() => setDocuments((curr) => curr.filter((d) => d.id !== id)))
      .catch((err) => alert(err.message || "Failed to delete document"))
      .finally(() => setBusyId(null));
  };

  const handleReprocess = (id) => {
    setBusyId(id);
    reprocessKnowledgeDocument(id)
      .then((updated) => setDocuments((curr) => curr.map((d) => (d.id === id ? updated : d))))
      .catch((err) => alert(err.message || "Failed to reprocess document"))
      .finally(() => setBusyId(null));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", flex: 1, overflowY: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ fontFamily: "'Syne', sans-serif", fontSize: "1.75rem", margin: "0 0 0.5rem 0", color: "var(--app-text-primary)" }}>Knowledge Center</h2>
          <p style={{ margin: 0, color: "var(--app-text-secondary)" }}>
            Real policy/manual documents specialists ground answers in via semantic search.
          </p>
        </div>
        <button onClick={loadDocuments} className="app-btn-secondary">Refresh</button>
      </div>

      <Can permission="manage_knowledge_base">
        <UploadForm onUploaded={(doc) => setDocuments((curr) => [{ ...doc, file_size_bytes: 0, chunk_count: 0, uploaded_at: new Date().toISOString() }, ...curr])} />
      </Can>

      {error && <div className="app-error-banner"><span>{error}</span></div>}

      {loading ? (
        <div className="app-panel">
          <div className="skeleton-row" style={{ height: "40px", marginBottom: "1rem" }}></div>
          <div className="skeleton-row" style={{ height: "40px", marginBottom: "1rem" }}></div>
          <div className="skeleton-row" style={{ height: "40px" }}></div>
        </div>
      ) : documents.length === 0 ? (
        <div className="app-empty-state">
          <h3>No documents yet</h3>
          <p>Upload a PDF, DOCX, or TXT policy document to get started.</p>
        </div>
      ) : (
        <div className="app-table-container">
          <table className="app-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Chunks</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>
                    <button className="kc-title-link" onClick={() => setSelectedId(doc.id)}>{doc.title}</button>
                  </td>
                  <td style={{ textTransform: "uppercase" }}>{doc.file_type}</td>
                  <td>{formatBytes(doc.file_size_bytes)}</td>
                  <td>
                    <span className={`app-badge ${STATUS_BADGE[doc.status] || "badge-neutral"}`}>
                      {STATUS_LABEL[doc.status] || doc.status}
                    </span>
                  </td>
                  <td>{doc.chunk_count}</td>
                  <td>{formatTimestamp(doc.uploaded_at)}</td>
                  <td>
                    <Can permission="manage_knowledge_base">
                      <div style={{ display: "flex", gap: "0.4rem" }}>
                        <button
                          className="app-btn-secondary"
                          disabled={busyId === doc.id}
                          onClick={() => handleReprocess(doc.id)}
                        >
                          {busyId === doc.id ? "…" : "Reprocess"}
                        </button>
                        <button
                          className="app-btn-secondary kc-delete-btn"
                          disabled={busyId === doc.id}
                          onClick={() => handleDelete(doc.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </Can>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SearchPanel />

      {selectedId != null && (
        <DocumentDetail documentId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
