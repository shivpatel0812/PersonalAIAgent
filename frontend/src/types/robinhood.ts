export type RobinhoodStatus = {
  configured: boolean;
  connected: boolean;
  mcp_url: string;
  connect_url: string | null;
  message: string;
  tools: string[];
};

export type RobinhoodToolInfo = {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
};
