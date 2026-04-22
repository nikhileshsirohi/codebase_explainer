"use client";

import { useEffect, useMemo, useState } from "react";

const API_ROOT = "/backend/api/v1";

const initialAskState = {
  loading: false,
  answer: "",
  sessionId: "",
  sources: [],
  error: "",
};

const initialAnalysisState = {
  overview: null,
  entrypoints: null,
  architecture: null,
  loading: "",
  error: "",
};

function statusTone(status) {
  if (status === "done") return "good";
  if (status === "running" || status === "queued") return "warn";
  if (status === "failed") return "bad";
  return "muted";
}

async function request(path, options) {
  const response = await fetch(`${API_ROOT}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  const raw = await response.text();
  let parsed = null;
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const message =
      parsed?.detail ||
      parsed?.message ||
      raw ||
      `Request failed (${response.status})`;
    throw new Error(message || `Request failed (${response.status})`);
  }

  return parsed;
}

function formatDate(value) {
  if (!value) return "Not available";
  try {
    return new Intl.DateTimeFormat("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function StatCard({ label, value, tone = "default" }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SourceCard({ source }) {
  return (
    <article className="source-card">
      <div className="source-card__top">
        <span>{source.path}</span>
        <span className="mini-pill">#{source.n}</span>
      </div>
      <div className="source-card__meta">
        <span>
          Lines {source.start_line}-{source.end_line}
        </span>
        <span>Score {Number(source.score || 0).toFixed(3)}</span>
      </div>
    </article>
  );
}

function RepoListItem({ repo, active, onSelect }) {
  return (
    <button
      className={`repo-list-item ${active ? "active" : ""}`}
      onClick={() => onSelect(repo.repo_id)}
      type="button"
    >
      <div className="repo-list-item__header">
        <strong>{repo.repo_url?.replace("https://github.com/", "") || repo.repo_id}</strong>
        <span className={`status-pill ${statusTone(repo.latest_job_status)}`}>
          {repo.latest_job_status || "idle"}
        </span>
      </div>
      <div className="repo-list-item__meta">
        <span>{repo.provider || "unknown"}</span>
        <span>{formatDate(repo.created_at)}</span>
      </div>
    </button>
  );
}

export default function HomePage() {
  const [health, setHealth] = useState(null);
  const [repos, setRepos] = useState([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [selectedRepoId, setSelectedRepoId] = useState("");
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repoFilter, setRepoFilter] = useState("");
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [topK, setTopK] = useState(8);
  const [question, setQuestion] = useState("");
  const [askState, setAskState] = useState(initialAskState);
  const [analysisState, setAnalysisState] = useState(initialAnalysisState);
  const [activeAnalysisTab, setActiveAnalysisTab] = useState("overview");
  const [banner, setBanner] = useState("");

  const filteredRepos = useMemo(() => {
    const q = repoFilter.trim().toLowerCase();
    if (!q) return repos;
    return repos.filter((repo) => {
      const haystack = [
        repo.repo_url,
        repo.canonical_repo_url,
        repo.provider,
        repo.latest_job_status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [repoFilter, repos]);

  async function loadHealth() {
    try {
      const data = await request("/health", { method: "GET" });
      setHealth(data);
    } catch {
      setHealth({ status: "offline", mongo: false, ollama: false });
    }
  }

  async function loadRepos(preferredRepoId) {
    setReposLoading(true);
    try {
      const data = await request("/repos", { method: "GET" });
      setRepos(data);
      const nextRepoId =
        preferredRepoId ||
        (selectedRepoId && data.some((repo) => repo.repo_id === selectedRepoId) ? selectedRepoId : "") ||
        data[0]?.repo_id ||
        "";
      setSelectedRepoId(nextRepoId);
    } catch (error) {
      setBanner(error.message);
    } finally {
      setReposLoading(false);
    }
  }

  async function loadRepoDetails(repoId) {
    if (!repoId) {
      setSelectedRepo(null);
      return;
    }

    try {
      const data = await request(`/repos/${repoId}`, { method: "GET" });
      setSelectedRepo(data);
    } catch (error) {
      setBanner(error.message);
      setSelectedRepo(null);
    }
  }

  useEffect(() => {
    loadHealth();
    loadRepos();
  }, []);

  useEffect(() => {
    loadRepoDetails(selectedRepoId);
  }, [selectedRepoId]);

  useEffect(() => {
    if (!selectedRepo?.latest_job_id) return undefined;
    if (!["queued", "running"].includes(selectedRepo.latest_job_status)) return undefined;

    const timer = setInterval(async () => {
      try {
        const job = await request(`/jobs/${selectedRepo.latest_job_id}`, { method: "GET" });
        setSelectedRepo((current) =>
          current
            ? {
                ...current,
                latest_job_status: job.status,
                latest_job_updated_at: job.updated_at,
                latest_job_error: job.error,
                latest_job_stats: job.stats,
              }
            : current
        );
        setRepos((current) =>
          current.map((repo) =>
            repo.repo_id === selectedRepo.repo_id
              ? {
                  ...repo,
                  latest_job_status: job.status,
                }
              : repo
          )
        );
      } catch {
        return;
      }
    }, 5000);

    return () => clearInterval(timer);
  }, [selectedRepo]);

  async function handleIngest(event) {
    event.preventDefault();
    if (!newRepoUrl.trim()) return;

    setBanner("Starting repository ingestion...");
    try {
      const data = await request("/ingest", {
        method: "POST",
        body: JSON.stringify({ repo_url: newRepoUrl.trim() }),
      });
      setNewRepoUrl("");
      setBanner(`Ingestion queued. Repo ${data.repo_id}, job ${data.job_id}.`);
      await loadRepos(data.repo_id);
      await loadRepoDetails(data.repo_id);
    } catch (error) {
      setBanner(error.message);
    }
  }

  async function handleReingest() {
    if (!selectedRepo?.canonical_repo_url && !selectedRepo?.repo_url) return;

    setBanner("Re-ingesting selected repository...");
    try {
      const data = await request("/ingest", {
        method: "POST",
        body: JSON.stringify({
          repo_url: selectedRepo.canonical_repo_url || selectedRepo.repo_url,
        }),
      });
      setBanner(`Re-ingestion queued. Job ${data.job_id}.`);
      await loadRepos(selectedRepo.repo_id);
      await loadRepoDetails(selectedRepo.repo_id);
    } catch (error) {
      setBanner(error.message);
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    if (!selectedRepoId || !question.trim()) return;

    setAskState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const data = await request(`/repos/${selectedRepoId}/ask`, {
        method: "POST",
        body: JSON.stringify({
          question: question.trim(),
          session_id: askState.sessionId || undefined,
          top_k: topK,
        }),
      });

      setAskState({
        loading: false,
        answer: data.answer,
        sessionId: data.session_id || "",
        sources: data.sources || [],
        error: "",
      });
    } catch (error) {
      setAskState((current) => ({
        ...current,
        loading: false,
        error: error.message,
      }));
    }
  }

  async function handleAnalysis(tab) {
    if (!selectedRepoId) return;

    setActiveAnalysisTab(tab);
    setAnalysisState((current) => ({ ...current, loading: tab, error: "" }));
    try {
      const data = await request(`/repos/${selectedRepoId}/${tab}`, { method: "GET" });
      setAnalysisState((current) => ({
        ...current,
        [tab]: data,
        loading: "",
        error: "",
      }));
    } catch (error) {
      setAnalysisState((current) => ({
        ...current,
        loading: "",
        error: error.message,
      }));
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Repository intelligence cockpit</p>
          <h1>Codebase Explainer</h1>
          <p className="hero-text">
            Ingest a GitHub repository, monitor indexing, ask grounded questions, and inspect the
            detected architecture without leaving a single workspace.
          </p>
        </div>
        <div className="hero-stats">
          <StatCard label="Repositories" value={repos.length} />
          <StatCard label="API status" value={health?.status || "checking"} tone={health?.status === "ok" ? "good" : "warn"} />
          <StatCard label="Mongo" value={health?.mongo ? "connected" : "offline"} tone={health?.mongo ? "good" : "bad"} />
          <StatCard label="Ollama" value={health?.ollama ? "reachable" : "offline"} tone={health?.ollama ? "good" : "bad"} />
        </div>
      </section>

      {banner ? <div className="banner">{banner}</div> : null}

      <section className="workspace-grid">
        <aside className="panel panel-left">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Ingest</p>
              <h2>Add a repository</h2>
            </div>
          </div>

          <form className="stack-form" onSubmit={handleIngest}>
            <label className="field">
              <span>GitHub URL</span>
              <input
                placeholder="https://github.com/user/repo"
                value={newRepoUrl}
                onChange={(event) => setNewRepoUrl(event.target.value)}
              />
            </label>
            <button className="primary-button" type="submit">
              Start ingestion
            </button>
          </form>

          <div className="divider" />

          <div className="panel-header">
            <div>
              <p className="section-kicker">Repositories</p>
              <h2>Workspace inventory</h2>
            </div>
            <button className="ghost-button" type="button" onClick={() => loadRepos()}>
              {reposLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>

          <label className="field">
            <span>Filter list</span>
            <input
              placeholder="Search by URL, provider, or status"
              value={repoFilter}
              onChange={(event) => setRepoFilter(event.target.value)}
            />
          </label>

          <div className="repo-list">
            {filteredRepos.length ? (
              filteredRepos.map((repo) => (
                <RepoListItem
                  key={repo.repo_id}
                  repo={repo}
                  active={repo.repo_id === selectedRepoId}
                  onSelect={setSelectedRepoId}
                />
              ))
            ) : (
              <div className="empty-state">No repositories yet. Ingest one to get started.</div>
            )}
          </div>

          <div className="repo-detail">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Selection</p>
                <h2>Repository details</h2>
              </div>
              <button className="ghost-button" type="button" onClick={handleReingest} disabled={!selectedRepo}>
                Re-ingest
              </button>
            </div>

            {selectedRepo ? (
              <div className="repo-detail__content">
                <div className="detail-row">
                  <span>URL</span>
                  <strong>{selectedRepo.repo_url}</strong>
                </div>
                <div className="detail-row">
                  <span>Branch</span>
                  <strong>{selectedRepo.default_branch || "unknown"}</strong>
                </div>
                <div className="detail-row">
                  <span>Latest job</span>
                  <strong className={`status-text ${statusTone(selectedRepo.latest_job_status)}`}>
                    {selectedRepo.latest_job_status || "idle"}
                  </strong>
                </div>
                <div className="detail-row">
                  <span>Updated</span>
                  <strong>{formatDate(selectedRepo.latest_job_updated_at)}</strong>
                </div>
                {selectedRepo.latest_job_error ? (
                  <div className="error-box">{selectedRepo.latest_job_error}</div>
                ) : null}
                {selectedRepo.latest_job_stats ? (
                  <pre className="code-block">{prettyJson(selectedRepo.latest_job_stats)}</pre>
                ) : null}
              </div>
            ) : (
              <div className="empty-state">Choose a repository to inspect its latest indexing state.</div>
            )}
          </div>
        </aside>

        <section className="panel panel-main">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Ask</p>
              <h2>Grounded chat workspace</h2>
            </div>
            {askState.sessionId ? <span className="mini-pill">Session {askState.sessionId}</span> : null}
          </div>

          <form className="stack-form" onSubmit={handleAsk}>
            <label className="field">
              <span>Question</span>
              <textarea
                placeholder="Where is ingestion implemented, and what calls it?"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
              />
            </label>

            <div className="form-row">
              <label className="field">
                <span>Retrieval depth</span>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value) || 8)}
                />
              </label>
              <label className="field">
                <span>Repository</span>
                <input value={selectedRepo?.repo_url || "Select a repository from the left panel"} disabled />
              </label>
            </div>

            <button className="primary-button" type="submit" disabled={!selectedRepoId || askState.loading}>
              {askState.loading ? "Generating answer..." : "Ask codebase"}
            </button>
          </form>

          {askState.error ? <div className="error-box">{askState.error}</div> : null}

          <div className="answer-panel">
            <div className="answer-panel__header">
              <h3>Answer</h3>
              <span>{askState.sources.length} sources</span>
            </div>
            <div className="answer-copy">
              {askState.answer || "Your grounded answer will appear here once you query an indexed repository."}
            </div>
            {askState.sources.length ? (
              <div className="sources-grid">
                {askState.sources.map((source) => (
                  <SourceCard key={`${source.path}-${source.n}`} source={source} />
                ))}
              </div>
            ) : null}
          </div>

          <div className="analysis-panel">
            <div className="panel-header">
              <div>
                <p className="section-kicker">Analysis</p>
                <h2>Repository diagnostics</h2>
              </div>
            </div>

            <div className="tab-row">
              {["overview", "entrypoints", "architecture"].map((tab) => (
                <button
                  key={tab}
                  className={`tab-button ${activeAnalysisTab === tab ? "active" : ""}`}
                  type="button"
                  onClick={() => handleAnalysis(tab)}
                  disabled={!selectedRepoId}
                >
                  {analysisState.loading === tab ? `Loading ${tab}...` : tab}
                </button>
              ))}
            </div>

            {analysisState.error ? <div className="error-box">{analysisState.error}</div> : null}

            <pre className="code-block">
              {prettyJson(
                analysisState[activeAnalysisTab] || {
                  hint: "Select a repository, then open overview, entrypoints, or architecture.",
                }
              )}
            </pre>
          </div>
        </section>
      </section>
    </main>
  );
}
