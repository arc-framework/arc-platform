import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import type { Theme as ThemeConfig } from 'vitepress'

// Git changelog — use layout slot instead of GitChangelogMarkdownSection()
// to avoid conflict with markdown: { html: false } which escapes injected tags
import {
  NolebaseGitChangelogPlugin,
  NolebaseGitChangelog,
  NolebaseGitContributors,
} from '@nolebase/vitepress-plugin-git-changelog/client'
import '@nolebase/vitepress-plugin-git-changelog/client/style.css'

import { NolebaseHighlightTargetedHeading } from '@nolebase/vitepress-plugin-highlight-targeted-heading/client'
import '@nolebase/vitepress-plugin-highlight-targeted-heading/client/style.css'

import {
  NolebaseEnhancedReadabilitiesMenu,
  NolebaseEnhancedReadabilitiesScreenMenu,
} from '@nolebase/vitepress-plugin-enhanced-readabilities/client'
import '@nolebase/vitepress-plugin-enhanced-readabilities/client/style.css'

import 'virtual:group-icons.css'
import './style.css'

export const Theme: ThemeConfig = {
  extends: DefaultTheme,
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'layout-top': () => h(NolebaseHighlightTargetedHeading),
      'nav-bar-content-after': () => h(NolebaseEnhancedReadabilitiesMenu),
      'nav-screen-content-after': () => h(NolebaseEnhancedReadabilitiesScreenMenu),
      'doc-after': () =>
        h('div', null, [
          h('div', { class: 'doc-git-section' }, h(NolebaseGitContributors)),
          h('div', { class: 'doc-git-section' }, h(NolebaseGitChangelog)),
        ]),
    }),
  enhanceApp({ app }) {
    app.use(NolebaseGitChangelogPlugin)
  },
}

export default Theme
