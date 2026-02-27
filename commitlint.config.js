module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation only
        'style',    // Code style (formatting, semicolons, etc)
        'refactor', // Code refactoring
        'perf',     // Performance improvement
        'test',     // Adding or updating tests
        'build',    // Build system or dependencies
        'ci',       // CI/CD configuration
        'chore',    // Other changes (maintenance)
        'revert',   // Revert a previous commit
      ],
    ],
    'scope-enum': [
      1, // Warning, not error
      'always',
      [
        'cli',        // CLI commands and interface
        'primitives', // Core domain models
        'services',   // Business logic services
        'storage',    // Storage abstractions
        'agents',     // Agent definitions
        'templates',  // Template files
        'docs',       // Documentation
        'ci',         // CI/CD
        'release',    // Release process
        'baseline',   // Baseline command
        'skill',      // Skill management
        'mcp',        // MCP server integration
        'oauth',      // OAuth authentication
        'config',     // Configuration system
      ],
    ],
    'subject-case': [2, 'always', 'lower-case'],
    'header-max-length': [2, 'always', 100],
  },
};
