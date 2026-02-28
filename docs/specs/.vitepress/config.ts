import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import { GitChangelog } from '@nolebase/vitepress-plugin-git-changelog/vite'
import { groupIconMdPlugin, groupIconVitePlugin } from 'vitepress-plugin-group-icons'
import llmstxt from 'vitepress-plugin-llms'

export default withMermaid(defineConfig({
  title: 'A.R.C. Platform — Specs',
  description: 'Feature specifications for the A.R.C. Platform',
  srcDir: './content',
  base: '/arc-platform/specs-site/',
  lastUpdated: true,
  ignoreDeadLinks: [/^https?:\/\/localhost/],
  srcExclude: ['**/pr-description.md', '**/.work-docs/**'],

  themeConfig: {
    nav: [
      { text: 'GitHub', link: 'https://github.com/arc-framework/arc-platform' }
    ],

    sidebar: [
      { text: 'Overview', link: '/' },
      {
        text: '001 — OTEL Setup',
        items: [
          { text: 'Specification', link: '/001-otel-setup/spec' },
          { text: 'Implementation Plan', link: '/001-otel-setup/plan' },
          { text: 'Task Breakdown', link: '/001-otel-setup/tasks' },
        ]
      },
      {
        text: '002 — Cortex Setup',
        items: [
          { text: 'Specification', link: '/002-cortex-setup/spec' },
          { text: 'Implementation Plan', link: '/002-cortex-setup/plan' },
          { text: 'Task Breakdown', link: '/002-cortex-setup/tasks' },
        ]
      },
      {
        text: '003 — Messaging Setup',
        items: [
          { text: 'Specification', link: '/003-messaging-setup/spec' },
          { text: 'Implementation Plan', link: '/003-messaging-setup/plan' },
          { text: 'Task Breakdown', link: '/003-messaging-setup/tasks' },
        ]
      },
      {
        text: '004 — Dev Setup',
        items: [
          { text: 'Specification', link: '/004-dev-setup/spec' },
          { text: 'Implementation Plan', link: '/004-dev-setup/plan' },
          { text: 'Task Breakdown', link: '/004-dev-setup/tasks' },
          { text: 'Analysis Report', link: '/004-dev-setup/analysis-report' },
        ]
      },
      {
        text: '005 — Data Layer',
        items: [
          { text: 'Specification', link: '/005-data-layer/spec' },
          { text: 'Implementation Plan', link: '/005-data-layer/plan' },
          { text: 'Task Breakdown', link: '/005-data-layer/tasks' },
          { text: 'Analysis Report', link: '/005-data-layer/analysis-report' },
        ]
      },
      {
        text: '006 — Platform Control',
        items: [
          { text: 'Specification', link: '/006-platform-control/spec' },
          { text: 'Implementation Plan', link: '/006-platform-control/plan' },
          { text: 'Task Breakdown', link: '/006-platform-control/tasks' },
          { text: 'Analysis Report', link: '/006-platform-control/analysis-report' },
        ]
      },
      {
        text: '007 — Voice Stack',
        items: [
          { text: 'Specification', link: '/007-voice-stack/spec' },
          { text: 'Implementation Plan', link: '/007-voice-stack/plan' },
          { text: 'Task Breakdown', link: '/007-voice-stack/tasks' },
          { text: 'Analysis Report', link: '/007-voice-stack/analysis-report' },
        ]
      },
      {
        text: '008 — Specs Site',
        items: [
          { text: 'Specification', link: '/008-specs-site/spec' },
          { text: 'Implementation Plan', link: '/008-specs-site/plan' },
          { text: 'Task Breakdown', link: '/008-specs-site/tasks' },
          { text: 'Analysis Report', link: '/008-specs-site/analysis-report' },
        ]
      },
    ],

    editLink: {
      pattern: 'https://github.com/arc-framework/arc-platform/edit/main/specs/:path',
      text: 'Edit this page on GitHub'
    },

    search: { provider: 'local' },

    lastUpdated: {
      text: 'Last updated',
      formatOptions: { dateStyle: 'short' }
    }
  },

  mermaid: {},

  vite: {
    plugins: [
      GitChangelog({ repoURL: () => 'https://github.com/arc-framework/arc-platform' }),
      groupIconVitePlugin(),
      llmstxt({ injectLLMHint: false }),
    ],
    resolve: { preserveSymlinks: true },
    optimizeDeps: {
      exclude: [
        '@nolebase/vitepress-plugin-enhanced-readabilities/client',
        'vitepress',
        '@nolebase/ui',
      ],
    },
    ssr: {
      noExternal: [
        '@nolebase/vitepress-plugin-git-changelog',
        '@nolebase/vitepress-plugin-highlight-targeted-heading',
        '@nolebase/vitepress-plugin-enhanced-readabilities',
        '@nolebase/ui',
      ],
    },
  },

  markdown: {
    html: false,
    config(md) {
      md.use(groupIconMdPlugin)
      // Inline code can contain {{ }} (Go templates, GitHub Actions) which Vue
      // interprets as template interpolation. Escape the opening delimiter.
      const codeInlineRule = md.renderer.rules.code_inline!
      md.renderer.rules.code_inline = (tokens, idx, options, env, self) =>
        codeInlineRule(tokens, idx, options, env, self).replace(/\{\{/g, '&#123;&#123;')
    },
  },
}))
