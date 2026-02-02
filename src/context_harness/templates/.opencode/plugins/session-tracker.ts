/**
 * ContextHarness Session Tracker Plugin for OpenCode
 *
 * This plugin tracks conversation turns and automatically updates SESSION.md
 * files before summarization/compaction occurs, preventing detail loss.
 *
 * Features:
 * - Tracks assistant turns per session
 * - Updates SESSION.md at configurable intervals
 * - Injects SESSION.md content into compaction context
 * - Monitors token usage for preemptive updates
 *
 * @see https://github.com/co-labs-co/context-harness/issues/89
 */

import * as fs from "node:fs/promises";
import * as path from "node:path";
import type { Plugin } from "@opencode-ai/plugin";

// ============================================================================
// Configuration
// ============================================================================

interface PluginConfig {
  /** Update SESSION.md every N assistant turns (default: 2) */
  turnThreshold: number;
  /** Update when context usage exceeds this ratio (default: 0.75) */
  tokenThreshold: number;
  /** Path to sessions directory relative to project root */
  sessionsPath: string;
  /** Enable verbose logging */
  debug: boolean;
}

const DEFAULT_CONFIG: PluginConfig = {
  turnThreshold: 2,
  tokenThreshold: 0.75,
  sessionsPath: ".context-harness/sessions",
  debug: false,
};

// ============================================================================
// Types
// ============================================================================

interface MessageInfo {
  id: string;
  role: "user" | "assistant" | "system";
  sessionID: string;
  providerID?: string;
  modelID?: string;
  tokens?: {
    input: number;
    output: number;
    cache: { read: number; write: number };
  };
  summary?: boolean;
  finish?: boolean;
}

interface SessionState {
  userTurns: number;
  assistantTurns: number;
  lastUpdateTurn: number;
  sessionPath: string | null;
  tokenUsage: number;
}

// Model context limits (conservative estimates)
const MODEL_CONTEXT_LIMITS: Record<string, number> = {
  "claude-3-5-sonnet": 200_000,
  "claude-3-opus": 200_000,
  "claude-3-sonnet": 200_000,
  "claude-3-haiku": 200_000,
  "gpt-4-turbo": 128_000,
  "gpt-4o": 128_000,
  "gpt-4": 32_000,
  default: 128_000,
};

// ============================================================================
// Plugin Implementation
// ============================================================================

export const SessionTrackerPlugin: Plugin = async (ctx) => {
  const { directory, client } = ctx;

  // Load configuration from environment or defaults
  const config: PluginConfig = {
    ...DEFAULT_CONFIG,
    turnThreshold: parseInt(
      process.env.CH_TURN_THRESHOLD || String(DEFAULT_CONFIG.turnThreshold)
    ),
    tokenThreshold: parseFloat(
      process.env.CH_TOKEN_THRESHOLD || String(DEFAULT_CONFIG.tokenThreshold)
    ),
    debug: process.env.CH_DEBUG === "true",
  };

  // Session state tracking (per OpenCode session)
  const sessions = new Map<string, SessionState>();

  const log = (message: string, ...args: unknown[]) => {
    if (config.debug) {
      client.app.log(`[session-tracker] ${message}`, ...args);
    }
  };

  log("Plugin initialized", { directory, config });

  // ============================================================================
  // Helper Functions
  // ============================================================================

  /**
   * Find the active ContextHarness session directory
   */
  async function findActiveSession(
    projectDir: string
  ): Promise<string | null> {
    const sessionsDir = path.join(projectDir, config.sessionsPath);

    try {
      const entries = await fs.readdir(sessionsDir, { withFileTypes: true });
      const sessionDirs = entries.filter((e) => e.isDirectory());

      // Return the most recently modified session
      let latestSession: { name: string; mtime: Date } | null = null;

      for (const dir of sessionDirs) {
        const sessionMdPath = path.join(
          sessionsDir,
          dir.name,
          "SESSION.md"
        );
        try {
          const stat = await fs.stat(sessionMdPath);
          if (!latestSession || stat.mtime > latestSession.mtime) {
            latestSession = { name: dir.name, mtime: stat.mtime };
          }
        } catch {
          // SESSION.md doesn't exist in this directory
        }
      }

      if (latestSession) {
        return path.join(sessionsDir, latestSession.name);
      }
    } catch {
      // Sessions directory doesn't exist
    }

    return null;
  }

  /**
   * Read current SESSION.md content
   */
  async function readSessionMd(sessionPath: string): Promise<string | null> {
    const sessionMdPath = path.join(sessionPath, "SESSION.md");
    try {
      return await fs.readFile(sessionMdPath, "utf8");
    } catch {
      return null;
    }
  }

  /**
   * Update SESSION.md with turn count metadata
   */
  async function updateSessionMdMetadata(
    sessionPath: string,
    state: SessionState
  ): Promise<void> {
    const sessionMdPath = path.join(sessionPath, "SESSION.md");

    try {
      let content = await fs.readFile(sessionMdPath, "utf8");

      // Update Last Updated timestamp
      const now = new Date().toISOString();
      content = content.replace(
        /\*\*Last Updated\*\*: .*/,
        `**Last Updated**: ${now}`
      );

      // Add or update turn tracking section if not present
      if (!content.includes("## Plugin Metrics")) {
        const metricsSection = `
---

## Plugin Metrics

**User Turns**: ${state.userTurns}
**Assistant Turns**: ${state.assistantTurns}
**Last Auto-Update**: Turn ${state.assistantTurns}
**Token Usage**: ~${Math.round(state.tokenUsage).toLocaleString()}

_Auto-tracked by session-tracker plugin_
`;
        // Insert before Notes section if it exists, otherwise at end
        if (content.includes("## Notes")) {
          content = content.replace("## Notes", `${metricsSection}\n## Notes`);
        } else {
          content += metricsSection;
        }
      } else {
        // Update existing metrics
        content = content.replace(
          /\*\*User Turns\*\*: \d+/,
          `**User Turns**: ${state.userTurns}`
        );
        content = content.replace(
          /\*\*Assistant Turns\*\*: \d+/,
          `**Assistant Turns**: ${state.assistantTurns}`
        );
        content = content.replace(
          /\*\*Last Auto-Update\*\*: Turn \d+/,
          `**Last Auto-Update**: Turn ${state.assistantTurns}`
        );
        content = content.replace(
          /\*\*Token Usage\*\*: ~[\d,]+/,
          `**Token Usage**: ~${Math.round(state.tokenUsage).toLocaleString()}`
        );
      }

      await fs.writeFile(sessionMdPath, content, "utf8");
      log(`Updated SESSION.md at turn ${state.assistantTurns}`);
    } catch (error) {
      log("Failed to update SESSION.md", error);
    }
  }

  /**
   * Get model context limit
   */
  function getContextLimit(modelID?: string): number {
    if (!modelID) return MODEL_CONTEXT_LIMITS.default;

    for (const [key, limit] of Object.entries(MODEL_CONTEXT_LIMITS)) {
      if (modelID.toLowerCase().includes(key.toLowerCase())) {
        return limit;
      }
    }
    return MODEL_CONTEXT_LIMITS.default;
  }

  /**
   * Get or create session state
   */
  function getSessionState(sessionID: string): SessionState {
    if (!sessions.has(sessionID)) {
      sessions.set(sessionID, {
        userTurns: 0,
        assistantTurns: 0,
        lastUpdateTurn: 0,
        sessionPath: null,
        tokenUsage: 0,
      });
    }
    return sessions.get(sessionID)!;
  }

  // ============================================================================
  // Event Handlers
  // ============================================================================

  return {
    /**
     * Handle all plugin events
     */
    event: async ({ event }) => {
      // Track message completion
      if (event.type === "message.updated") {
        const info = event.properties?.info as MessageInfo | undefined;

        if (!info?.sessionID || !info?.finish) return;

        const state = getSessionState(info.sessionID);

        // Find session path if not already set
        if (!state.sessionPath) {
          state.sessionPath = await findActiveSession(directory);
        }

        // Track turns by role
        if (info.role === "user") {
          state.userTurns++;
          log(`User turn ${state.userTurns} in session ${info.sessionID}`);
        } else if (info.role === "assistant") {
          state.assistantTurns++;
          log(
            `Assistant turn ${state.assistantTurns} in session ${info.sessionID}`
          );

          // Update token usage
          if (info.tokens) {
            state.tokenUsage =
              info.tokens.input +
              info.tokens.output +
              (info.tokens.cache?.read || 0);
          }

          // Check if we should update SESSION.md
          const turnsSinceUpdate =
            state.assistantTurns - state.lastUpdateTurn;
          const shouldUpdateByTurns =
            turnsSinceUpdate >= config.turnThreshold;

          // Check token threshold
          const contextLimit = getContextLimit(info.modelID);
          const usageRatio = state.tokenUsage / contextLimit;
          const shouldUpdateByTokens = usageRatio >= config.tokenThreshold;

          if (
            (shouldUpdateByTurns || shouldUpdateByTokens) &&
            state.sessionPath
          ) {
            log(
              `Triggering SESSION.md update: turns=${turnsSinceUpdate}, tokenUsage=${(
                usageRatio * 100
              ).toFixed(1)}%`
            );
            await updateSessionMdMetadata(state.sessionPath, state);
            state.lastUpdateTurn = state.assistantTurns;
          }
        }
      }

      // Track session deletion
      if (event.type === "session.deleted") {
        const sessionID = event.properties?.id as string | undefined;
        if (sessionID) {
          sessions.delete(sessionID);
          log(`Session ${sessionID} deleted, clearing state`);
        }
      }
    },

    /**
     * Pre-compaction hook: Inject SESSION.md content into compaction context
     *
     * This ensures the SESSION.md state is preserved in the summary even if
     * we didn't hit our turn threshold before compaction was triggered.
     */
    "experimental.session.compacting": async (input, output) => {
      const sessionID = input.sessionID;
      const state = sessions.get(sessionID);

      log(`Compaction triggered for session ${sessionID}`);

      // Find session path if not already known
      const sessionPath = state?.sessionPath || (await findActiveSession(directory));

      if (sessionPath) {
        const sessionContent = await readSessionMd(sessionPath);

        if (sessionContent) {
          log("Injecting SESSION.md content into compaction context");

          output.context.push(`
## ContextHarness Session State (PRESERVE THIS)

The following is the current state from SESSION.md that MUST be preserved in the summary:

<session_state>
${sessionContent}
</session_state>

When summarizing, ensure:
1. Active Work task and status are preserved
2. Key Files list is maintained
3. Decisions Made are kept with rationale
4. Next Steps are carried forward
5. Turn counts are updated: User=${state?.userTurns || 0}, Assistant=${state?.assistantTurns || 0}
`);

          // Update SESSION.md before compaction completes
          if (state && sessionPath) {
            await updateSessionMdMetadata(sessionPath, state);
          }
        }
      }
    },
  };
};

// Default export for OpenCode plugin loading
export default SessionTrackerPlugin;
