/**
 * Shared constants for MCP integration.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL !== undefined
    ? process.env.NEXT_PUBLIC_API_URL
    : "http://localhost:5055";

/** Base URL for the Arkon MCP server endpoint. */
export const MCP_SERVER_URL = `${API_BASE}/mcp`;
