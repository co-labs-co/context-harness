# RLM Workspace Template

This directory contains RLM (Recursive Language Model) workspaces for processing large contexts.

## Directory Structure

```
.context-harness/rlm-workspace/
├── README.md                    # This file
├── .gitkeep                     # Keep directory in git
└── {workspace-id}/              # Individual workspace directories
    ├── context.txt              # Full original context
    ├── metadata.json            # Context metadata
    ├── chunks/                  # Partitioned context
    │   ├── chunk_001.txt
    │   ├── chunk_002.txt
    │   └── ...
    ├── results/                 # Worker results
    │   ├── worker_001.json
    │   ├── worker_002.json
    │   └── ...
    └── final_answer.md          # Aggregated final answer
```

## Workspace Lifecycle

1. **Created** when RLM Orchestrator receives new context
2. **Active** during query processing
3. **Archived** after query completion (optional)
4. **Cleaned** after configurable retention period

## Metadata Schema

```json
{
  "workspace_id": "rlm-{timestamp}-{hash}",
  "created_at": "ISO-8601 timestamp",
  "context": {
    "source": "file path or 'inline'",
    "size_bytes": 12345,
    "line_count": 1000,
    "estimated_tokens": 50000,
    "structure": "structured|unstructured|mixed"
  },
  "processing": {
    "status": "pending|active|complete|error",
    "strategy": "direct|search|partition_map|hybrid",
    "chunks_created": 10,
    "workers_spawned": 10,
    "start_time": "ISO-8601 timestamp",
    "end_time": "ISO-8601 timestamp"
  },
  "results": {
    "final_answer_file": "final_answer.md",
    "confidence": 0.95,
    "token_usage": 25000
  }
}
```

## Worker Result Schema

```json
{
  "worker_id": "worker_{timestamp}_{hash}",
  "chunk_path": "chunks/chunk_001.txt",
  "depth": 1,
  "query": "sub-query text",
  "results": {
    "findings": [],
    "answer": "partial answer",
    "count": null,
    "summary": "brief summary"
  },
  "metadata": {
    "confidence": 0.95,
    "processing_time_ms": 1200
  }
}
```

## Usage

RLM workspaces are managed automatically by the RLM Orchestrator agent. Users typically interact via:

```
@rlm-orchestrator Query: [question] Context: [file path]
```

The orchestrator handles workspace creation, partitioning, worker coordination, and cleanup.
