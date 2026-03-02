import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import { GitChangelog } from '@nolebase/vitepress-plugin-git-changelog/vite'
import { groupIconMdPlugin, groupIconVitePlugin } from 'vitepress-plugin-group-icons'
import llmstxt from 'vitepress-plugin-llms'
import { readdirSync, existsSync } from 'node:fs'
import { resolve, join } from 'node:path'

const CONTENT_DIR = resolve(__dirname, '../content')

// Known doc filenames in display order
const DOC_FILES = [
  { file: 'spec',            label: 'Specification' },
  { file: 'plan',            label: 'Implementation Plan' },
  { file: 'tasks',           label: 'Task Breakdown' },
  { file: 'analysis-report', label: 'Analysis Report' },
  { file: 'quickstart',      label: 'Quick Start' },
  { file: 'research',        label: 'Research' },
  { file: 'data-model',      label: 'Data Model' },
]

function buildSidebar() {
  const dirs = readdirSync(CONTENT_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory() && /^\d{3}-/.test(d.name))
    .sort((a, b) => a.name.localeCompare(b.name))

  return [
    { text: 'Overview', link: '/' },
    ...dirs.map(dir => {
      const slug = dir.name
      const num = slug.slice(0, 3)
      const name = slug.slice(4).replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      const items = DOC_FILES
        .filter(({ file }) => existsSync(join(CONTENT_DIR, slug, `${file}.md`)))
        .map(({ file, label }) => ({ text: label, link: `/${slug}/${file}` }))
      return { text: `${num} — ${name}`, items }
    }),
  ]
}

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

    sidebar: buildSidebar(),

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
