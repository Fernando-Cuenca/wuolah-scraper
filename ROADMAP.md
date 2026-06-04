# Roadmap

Planned features and future directions for Wuolah Scraper. Open to community contributions — pick anything below or propose your own.

---

## GUI Improvements

- [ ] **Dark/light theme toggle** — persist preference in config
- [ ] **University browser** — tree view to explore university → center → degree → subject without typing slugs
- [ ] **Drag-and-drop cookie import** — accept cookie files via drag-and-drop
- [ ] **Download queue** — queue multiple documents with pause/resume/cancel
- [ ] **Progress bars** — per-document download progress with speed and ETA
- [ ] **Search history** — dropdown with recent queries
- [ ] **Result sorting** — click column headers to sort by name, downloads, pages
- [ ] **Multi-select filters** — pick multiple categories or courses at once

## Visual Course Hierarchy Navigation

- [ ] **Interactive tree widget** — expandable tree showing the full path:
  ```
  Universidad Carlos III
  └── Escuela Politécnica Superior (Leganés)
      └── Grado en Ingeniería en Tecnologías Industriales
          ├── 1º — Cálculo I, Álgebra, Física I, Química, Expresión Gráfica
          ├── 2º — Cálculo II, Física II, Estadística, Termodinámica
          ├── 3º — Mecánica de Fluidos, Elasticidad, Electrónica
          └── 4º — TFG, optativas
  ```
- [ ] **Lazy loading** — fetch children on expand to keep initial load fast
- [ ] **Breadcrumb bar** — `UC3M > EPS > GITI > 2º > Física II > Exámenes`
- [ ] **Course-year color coding** — visual distinction between 1st/2nd/3rd/4th year materials

## AI-Powered Document Filtering

- [ ] **Relevance scoring** — use embeddings (e.g. `sentence-transformers`) to rank documents by semantic similarity to a user query
- [ ] **Duplicate detection** — flag near-duplicate uploads (same exam scanned by different students)
- [ ] **Quality classifier** — score documents by readability: handwritten vs typed, scan quality, presence of solutions
- [ ] **Content tagging** — auto-tag documents with detected topics (e.g. "electrostatics", "differential equations", "trusses")
- [ ] **Spam filter** — hide placeholder/troll uploads with no real content
- [ ] **Local LLM integration** — optional `ollama` or `llama.cpp` backend for on-device classification (no API costs, full privacy)

## Obsidian Exporter

- [ ] **Vault generator** — export all indexed documents as an Obsidian vault
- [ ] **Document notes** — each document becomes a Markdown note with frontmatter:
  ```yaml
  ---
  id: 12345
  name: "Examen Final Física II — Junio 2024"
  type: exam
  subject: "Física II"
  course: 2
  university: "UC3M"
  downloads: 342
  pages: 6
  tags: [examen, fisica-ii, giti, uc3m]
  ---
  ```
- [ ] **Graph view links** — auto-generate `[[]]` wikilinks between related documents:
  - Same subject + same course
  - Same uploader
  - Documents that share keywords
  - Prerequisite chains (e.g. Cálculo I → Cálculo II)
- [ ] **MOC (Map of Content) generation** — auto-create index notes per subject, per course year, per category
- [ ] **Dataview integration** — generate Dataview-compatible metadata for dynamic tables and queries
- [ ] **Graph styling** — CSS snippet for color-coded nodes by document type (exam=red, notes=blue, exercises=green)
- [ ] **Canvas export** — generate Obsidian Canvas JSON for visual arrangement of related documents

## Export & Interop

- [ ] **CSV export** — one CSV per SQLite table
- [ ] **Parquet export** — for data analysis (Pandas, Polars)
- [ ] **Zotero integration** — export document metadata as Zotero RDF/CSV
- [ ] **Calibre integration** — generate OPDS feed for e-reader access
- [ ] **REST API mode** — `wuolah-scraper serve` to expose search/download as a local HTTP API

## Core Improvements

- [ ] **Email/password login** — authenticate without manual cookie extraction
- [ ] **PDF preview download** — fetch public preview pages for free-tier accounts
- [ ] **Full artifact indexing** — social posts, giveaways, streams, not just documents
- [ ] **Incremental crawl** — only fetch documents changed since last run
- [ ] **Parallel downloads** — concurrent download workers with configurable pool size
- [ ] **CI test suite** — smoke tests against live API with mocked credentials
- [ ] **Docker image** — one-command deployment with pre-configured environment
