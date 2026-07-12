// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// GitHub Pages project site: https://sokolmarek.github.io/researcher
export default defineConfig({
  site: 'https://sokolmarek.github.io',
  base: '/researcher',
  integrations: [
    starlight({
      title: 'Researcher',
      description:
        "A tireless research assistant for the whole academic pipeline: literature search, drafting, peer review, figures, and publication. It does not sleep, so you can.",
      tagline: "It does not sleep, so you can.",
      logo: { src: './src/assets/favicon.svg', replacesTitle: false },
      favicon: '/favicon.svg',
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/sokolmarek/researcher' },
      ],
      customCss: ['./src/styles/custom.css'],
      editLink: {
        baseUrl: 'https://github.com/sokolmarek/researcher/edit/main/docs/',
      },
      lastUpdated: true,
      sidebar: [
        { label: 'Start Here', autogenerate: { directory: 'start' } },
        { label: 'Cookbook', autogenerate: { directory: 'cookbook' } },
        { label: 'Skill Guides', autogenerate: { directory: 'guides' } },
        { label: 'Reference', autogenerate: { directory: 'reference' } },
      ],
    }),
  ],
});
