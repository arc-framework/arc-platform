import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import { GitChangelog } from '@nolebase/vitepress-plugin-git-changelog/vite'
import { groupIconMdPlugin, groupIconVitePlugin } from 'vitepress-plugin-group-icons'
import llmstxt from 'vitepress-plugin-llms'
import { readdirSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'

// CONTENT_DIR points to the symlinked specs/ directory (docs/specs → ../specs)
const CONTENT_DIR = resolve(__dirname, '../specs')


function buildSidebar() {
  const dirs = readdirSync(CONTENT_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory() && /^\d{3}-/.test(d.name))
    .sort((a, b) => a.name.localeCompare(b.name))

  return [
    ...dirs
      .filter(dir => existsSync(join(CONTENT_DIR, dir.name, 'plan.md')))
      .map(dir => {
        const slug = dir.name
        const num = slug.slice(0, 3)
        const name = slug.slice(4).replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        return { text: `${num} — ${name}`, link: `/specs/${slug}/plan` }
      }),
  ]
}

function ardSidebar() {
  const ardDir = resolve(__dirname, '../ard')
  const files = readdirSync(ardDir)
    .filter(f => f.endsWith('.md'))
    .sort()

  return files.map(f => ({
    text: f.replace(/\.md$/, '').toLowerCase().replace(/[-_]/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
    link: `/ard/${f.replace(/\.md$/, '')}`,
  }))
}

export default withMermaid(defineConfig({
  title: 'ARC Docs',
  description: 'Documentation for the A.R.C. Platform — Agentic Reasoning Core',
  srcDir: '.',
  base: '/arc-platform/docs/',
  lastUpdated: true,
  ignoreDeadLinks: [
    /^https?:\/\/localhost/,
    // ARD files contain relative links to repo root files (SERVICE.MD, Makefile, etc.)
    // that are valid on GitHub but not resolvable as VitePress routes
    /\.\.\//,
  ],
  srcExclude: [
    '**/pr-description.md',
    '**/spec.md',          // requirements brief — plan.md has the richer technical content
    '**/tasks.md',         // implementation checklist — internal only
    '**/analysis-report.md', // QA gap analysis — internal only
    '**/.work-docs/**',
    'node_modules/**',
    '.vitepress/**',
    'superpowers/**',      // internal planning docs — not published
  ],

  themeConfig: {
    nav: [
      { text: 'Guide',        link: '/guide/getting-started' },
      { text: 'Services',     link: '/services/' },
      { text: 'Contributing', link: '/contributing/architecture' },
      { text: 'Roadmap',      link: '/specs/' },
      { text: 'GitHub',       link: 'https://github.com/arc-framework/arc-platform' }
    ],

    sidebar: [
      {
        text: 'Guide',
        items: [
          { text: 'Getting Started',    link: '/guide/getting-started' },
          { text: 'Why A.R.C.?',        link: '/guide/why-arc' },
          { text: 'CLI Reference',      link: '/guide/cli-reference' },
          { text: 'LLM Testing',        link: '/guide/llm-testing' },
          { text: 'arc.yaml Reference', link: '/guide/arc-yaml-reference' },
        ],
      },
      {
        text: 'Services',
        items: [
          { text: 'Service Map',  link: '/services/' },
          { text: 'Reasoner',     link: '/services/reasoner' },
          { text: 'Voice',        link: '/services/voice' },
          { text: 'Gateway',      link: '/services/gateway' },
          { text: 'Vault',        link: '/services/vault' },
          { text: 'Flags',        link: '/services/flags' },
          { text: 'SQL DB',       link: '/services/sql-db' },
          { text: 'Vector DB',   link: '/services/vector-db' },
          { text: 'Storage',      link: '/services/storage' },
          { text: 'Messaging',    link: '/services/messaging' },
          { text: 'Streaming',    link: '/services/streaming' },
          { text: 'Cache',        link: '/services/cache' },
          { text: 'Realtime',     link: '/services/realtime' },
          { text: 'Friday (OTEL)', link: '/services/friday' },
        ],
      },
      {
        text: 'Contributing',
        items: [
          { text: 'Architecture',    link: '/contributing/architecture' },
          { text: 'New Service',     link: '/contributing/new-service' },
          { text: 'New Capability',  link: '/contributing/new-capability' },
          { text: 'Conventions',     link: '/contributing/conventions' },
        ],
      },
      {
        text: 'Architecture',
        items: ardSidebar(),
      },
      {
        text: 'Roadmap',
        items: buildSidebar(),
      },
    ],

    editLink: {
      pattern: ({ filePath }) => {
        // specs/ symlinks back to ../specs in git — edit from the canonical path
        if (filePath.startsWith('specs/')) {
          return `https://github.com/arc-framework/arc-platform/edit/main/${filePath}`
        }
        return `https://github.com/arc-framework/arc-platform/edit/main/docs/${filePath}`
      },
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
