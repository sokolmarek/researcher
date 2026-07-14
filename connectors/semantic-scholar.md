# Semantic Scholar Connector

**What it provides**
Paper search, citation graph traversal, author lookup, and paper recommendations, drawn from the Semantic Scholar corpus.

**Mechanism**
Direct public REST API (api.semanticscholar.org) called from skills at runtime. No MCP server bundled. Works keyless at low volume; S2_API_KEY raises rate limits.

**Install and environment variables**
Nothing to install. Optionally set S2_API_KEY in your environment to raise rate limits above the keyless tier.

**Used by**
fact-checking, literature-search, writing-style-analysis, sota-finder

**Fallback when absent**
Without S2_API_KEY, skills still call the API keyless but may hit rate limits sooner, so searches fall back to smaller batches or slower retries.
