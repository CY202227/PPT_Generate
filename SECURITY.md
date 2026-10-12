# Security and data handling

This is a trusted local tool, not an authenticated multi-user network service. MCP uses stdio and runs with the caller's filesystem privileges. Only connect agents you trust; `read_document` may access local files the process can read.

LLM generation sends supplied source material to the configured provider. Rendering agent-authored JSON performs no model calls. Do not enable model generation for documents that the provider is not authorized to receive.

Credentials are read from environment variables or an explicitly selected dotenv file. They are omitted from configuration repr and excluded from distribution artifacts. Remote provider errors are mapped to generic codes instead of returning response bodies. Generated decks and job history can contain sensitive source material; choose an appropriate local output directory and retention policy.

Document extraction is bounded to 10 MiB inputs, 100 PDF pages and 100,000 output characters. These limits reduce accidental resource exhaustion; they are not a sandbox for hostile documents. DOCX archive expansion is checked before parsing. Keep parser dependencies updated.

For a suspected vulnerability, use the repository's GitHub private vulnerability reporting feature if enabled. Otherwise contact the maintainer through the repository profile; do not disclose credentials or exploitable private data in public issues. No response-time guarantee is currently offered.
