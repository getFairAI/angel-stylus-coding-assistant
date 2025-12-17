# Stylus Documentation Retrieval Service

A **retrieval-only**, **LLM-agnostic** service that provides **semantic search** over official **Arbitrum Stylus** documentation, blog posts, and curated community resources.

This project is designed to be consumed by **MCP servers**, **IDE integrations**, or **external LLMs** (Claude, GPT, etc.) as a **documentation context backend** — not an answer generator.

---

## ✨ Key Features

* 🔎 **Semantic retrieval** over Stylus documentation
* 🧠 **Vector search** powered by ChromaDB
* 🏠 **Fully local** (no hosted LLM APIs)
* 🧩 **LLM-agnostic** and stateless
* ⚡ Simple HTTP API returning raw documentation context

---

## 📚 Indexed Content

The vector index includes:

* **Official Stylus documentation**

  * Stylus by Example
  * Rust SDK & CLI
  * Concepts & reference docs
* **Arbitrum Stylus blog posts**
* **Curated community resources** (e.g. *Awesome Stylus*)
* **Selected GitHub READMEs** from Stylus-related repositories

All content is normalized and indexed as **topic-based chunks** with clear section headers to preserve semantic context.

---

## 🚫 What This Service Does *Not* Do

* ❌ Does **not** generate natural language answers
* ❌ Does **not** select or call any LLM
* ❌ Does **not** manage conversation history
* ❌ Does **not** perform prompt engineering

This service only **retrieves relevant documentation text**.

---

## 🏗 Architecture Overview

* **Vector Store**: ChromaDB (persistent)
* **Embeddings**: Generated locally via **Ollama** (`nomic-embed-text`)
* **Ingestion**: Automated scrapers → normalized JSON
* **Indexing Strategy**: Full rebuild (delete + reindex) during development

In production, this can be replaced with incremental or versioned indexing.

---

## 🔌 API

### Endpoint

```
POST /retrieve
```

### Request

```json
{
  "prompt": "How do I deploy a Stylus contract?"
}
```

### Response — Results Found

```json
{
  "found": true,
  "context": "Documentation - Quickstart - Deploying your contract\n\n...",
  "chunks_used": 4
}
```

### Response — No Results

```json
{
  "found": false,
  "context": "",
  "reason": "No relevant Stylus documentation was found for this query."
}
```

---

## 🧪 Testing the API

You can test the retrieval endpoint locally using `curl` once the API is running.

### Example request (local)

```bash
curl -X POST http://localhost:8001/stylus-chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "How do I deploy a Stylus contract?"
  }'
```

### Example request (public deployment)

```bash
curl -X POST https://stylus-demo.duckdns.org/api/stylus-chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "How do I deploy a Stylus contract?"
  }'
```

bash
curl -X POST [http://localhost:8001/stylus-chat](http://localhost:8001/stylus-chat) 
-H "Content-Type: application/json" 
-d '{
"prompt": "How do I deploy a Stylus contract?"
}'

```

The response will contain raw documentation context (or a reason if nothing is found), which can then be consumed by an external LLM, IDE, or MCP server.
json
{
  "found": false,
  "context": "",
  "reason": "No relevant Stylus documentation was found for this query."
}
```

---

## ⚙️ Local Setup

### Activate virtual environment

```bash
source .venv/bin/activate
```

---

### Populate ChromaDB (without systemd)

If you just want to test the project **locally without running any systemd services**, you can manually populate the vector database:

```bash
python run_all_data_ingestions.py
```

This will scrape, normalize, and index all Stylus documentation into ChromaDB.

---

### Run the API locally (without systemd)

After ingestion is complete, start the API manually:

```bash
uvicorn main:app --app-dir src --host 0.0.0.0 --port 8001
```

The API will then be available at:

```
http://localhost:8001/stylus-chat
```

---

## 🗃 Indexing & Ingestion

* Documentation is scraped and normalized into JSON
* During development, the ChromaDB collection is:

  1. Deleted
  2. Fully re-ingested

This guarantees the index always reflects the latest documentation state.

---

## 🛠 Running as a Service

Example **systemd service and timer files** are provided in the `systemd/` directory.

The folder contains **three example units** covering:

* The Stylus retrieval API (`stylus-api.service`)
* The ingestion job (`stylus-ingestion.service`)
* The scheduled timer (`stylus-ingestion.timer`)

These files are **examples only** and must be adapted to your local environment (user, paths, virtualenv location).


ini
[Unit]
Description=Stylus Documentation Retrieval API
After=network.target

[Service]
Type=simple
User=stylus
WorkingDirectory=/opt/stylus-retrieval
ExecStart=/opt/stylus-retrieval/.venv/bin/python api.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target

````

---

### Ingestion services

Example commands once service and timer files are adapted:

```bash
sudo systemctl daemon-reload

systemctl enable stylus-ingestion.timer
systemctl start stylus-ingestion.timer

systemctl enable stylus-api.service
systemctl start stylus-api.service
````

---

## 🧩 Intended Consumers

* MCP servers
* IDE plugins
* RAG pipelines
* External LLMs (Claude, GPT, etc.)

All reasoning, prompting, and response generation is handled **outside** this service.

---

