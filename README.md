# Matias Haderspock · Personal website

A bilingual, accessible personal website for Matias Haderspock. Plain HTML, CSS and vanilla JavaScript. No package install, build step, framework, analytics, or contact form.

The implementation is reviewed on a feature branch. Production is intended for Cloudflare Pages at **https://matiashaderspock.com**. Cloudflare has not been configured by this project.

## Local preview and checks

```sh
python3 -m http.server 8000 --directory public
# Open http://localhost:8000 (no install or build required).
python3 scripts/check.py
```

The dependency-free check validates HTML nesting, local links and fragments, duplicate IDs, document language, key SEO/Open Graph fields, reciprocal hreflang links, sitemap entries, image alternatives, and a 12 KB total JavaScript budget. It rejects unfinished placeholder text and empty links. It does not fetch external links. The GitHub Actions workflow runs checks on PRs and `main`; it has read-only permissions and does not deploy anything.

## Cloudflare Pages settings

Set this up manually **after reviewing and merging the feature PR**. The initial `main` branch contains only this README until the PR is merged; the site files are in the feature branch. This repository has no GitHub Pages workflow.

1. In the Cloudflare account that owns `matiashaderspock.com`, open **Workers & Pages → Create application → Pages → Import an existing Git repository**.
2. Connect GitHub and select **matiashaderspock-ai/portfolio**. If needed, grant the Cloudflare GitHub app access to this repository only.
3. Use these settings:

| Setting | Exact value |
| --- | --- |
| Project name | `portfolio` (or another available Pages project name) |
| Production branch | `main` |
| Framework preset | `None` |
| Root directory | Repository root (leave empty) |
| Build command | **None — leave empty** |
| Build output directory | `public` |
| Environment variables | None |

There is no build step. If the dashboard requires a command, `exit 0` is a no-op alternative documented by Cloudflare; keep the output directory `public`. Save and deploy, then verify the generated `https://<project-name>.pages.dev` URL. The repository’s top-level `public/404.html` makes unknown routes return a real 404 on Pages rather than falling back to a single-page app.

See Cloudflare’s [static HTML guide](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/) and [build configuration reference](https://developers.cloudflare.com/pages/configuration/build-configuration/).

### Custom domain: matiashaderspock.com

1. Verify the existing domain’s DNS zone is **Active in this same Cloudflare account**, with the domain using the Cloudflare nameservers assigned to its zone. Registration alone does not establish a Pages domain association.
2. Open **Workers & Pages → portfolio → Custom domains → Set up a domain**.
3. Enter **`matiashaderspock.com`**, continue, and confirm Cloudflare’s suggested DNS record. Review any existing apex website record before replacing it; retain email and other unrelated DNS records.
4. Allow Cloudflare to create the Pages DNS record and provision the HTTPS certificate. Wait until the custom domain shows **Active**.
5. Verify `https://matiashaderspock.com/`, `/es/`, `/resume/`, `/es/resume/`, and an unknown URL. Confirm the last returns the custom 404 with HTTP 404 status.

Add the domain through the Pages **Custom domains** flow; adding a DNS CNAME alone does not associate it with the project. Instructions follow Cloudflare’s [custom domain documentation](https://developers.cloudflare.com/pages/configuration/custom-domains/). No Cloudflare configuration, DNS change or deployment is performed by this repository’s CI.

## Content and routes

| English | Spanish | Content |
| --- | --- | --- |
| `/` | `/es/` | Hero, projects, background, contact links |
| `/resume/` | `/es/resume/` | Full résumé and print layout |
| `/404.html` | `/es/404.html` | Localized error page |

Cloudflare serves the nearest `404.html` for unknown URLs: `/es/404.html` for Spanish paths and the root `404.html` otherwise. Each error page links to its language counterpart. See Cloudflare’s [page serving documentation](https://developers.cloudflare.com/pages/configuration/serving-pages/). The English and Spanish pages are complete static documents, usable without JavaScript and with independent canonical, Open Graph and hreflang metadata. Social preview PNGs are local 1200 × 630 images; there is no third-party image dependency.

- Edit the HTML files in both languages together. Stable section IDs let the language switch retain a home-page section fragment.
- Language and theme choices are remembered locally in `mh-language` and `mh-theme`. A saved Spanish choice redirects future visits to `/` to `/es/`; the language toggle saves before navigation so English remains accessible. Explicit résumé/error routes retain their requested language. With JavaScript or storage disabled, language links still work.
- The theme defaults to dark regardless of device preference, including without JavaScript or storage. The top-of-page button switches between dark and light and remembers the choice in `mh-theme`. A saved choice is applied in the document head before styles load to avoid a theme flash. Print styles stay light.
- Motion is decorative CSS only. `prefers-reduced-motion: reduce` stops all animations, hover movement, smooth scrolling and reveal transitions. Content is visible by default and the reveal effect is added progressively.
- The résumé’s **Print / Save as PDF** button opens the browser print dialog. Use A4, 100% scale, and disable the browser’s own headers/footers for a clean PDF. Print styles use a white background, local system typography, and omit navigation and page controls. The browser’s native Print command also works without JavaScript.
- Typography uses DM Sans and Libre Caslon Display via Google Fonts, with system fallbacks. Font requests disclose the visitor’s network address to Google; no analytics, cookies or tracking scripts are included. The `_headers` file supplies a restrictive content policy on Cloudflare Pages.

## Content sources

Employment, education, certifications, languages and skills follow Matias’s English and Spanish CVs, with the confirmed VFVH award name, project destinations and Yango leadership scope (35+ back-office staff and 1,500+ couriers). Both résumés distinguish the Country Lead and Country Head roles and list Yango as the employer.

GitHub, LinkedIn and X are linked in the hero, contact section and résumé in each language. WhatsApp and email are linked in the contact section and résumé in each language. Gástalo and Cumpafit have live-app and repository links; Monitor Bol has a private repository and Grok Bot fleet has no public destination, so neither card includes a link slot.

## Latest on X

The English and Spanish home pages include five custom glass cards. They read
`public/data/x-latest.json`; no X embeds, browser credentials, or client-side API
calls are used. Static, localized sample cards remain visible with JavaScript
blocked, on a failed fetch, or when the JSON is marked `sample: true`.

After this PR is manually merged, **Update public X feed** runs every six hours
(at minute 17 UTC) and supports `workflow_dispatch` on `main`. Add the repository
Actions secret **X_BEARER_TOKEN** with access to the X API v2 user lookup and
user-post timeline endpoints. The script resolves `@pandasczos`, requests the
latest 100 timeline entries excluding replies (keeping posts, quotes, and
reposts), expands public text/media, and writes up to five eligible entries in
newest-first order. Missing entries stay as individually labeled sample cards.
The credential stays in the runner environment. The workflow commits only the
JSON file to `main`; the existing Cloudflare Pages integration publishes it.

Only `text`, `type` (`post`, `quote`, `repost`), `created_date` (date only), `link`,
and an optional `thumbnail` are published per entry, alongside the envelope's
`sample` flag. Protected profiles, sensitive/withheld posts, financial/account
disclosures, credentials and contact-like text are excluded conservatively;
rejected post contents and raw API bodies are never logged. Thumbnail URLs are
restricted to the public `pbs.twimg.com` image CDN, which is the only additional
image origin allowed by the CSP. Media alt text is screened too. These text
checks are conservative filters, not image inspection; public source images
remain the responsibility of the source account.

If the secret is absent, the updater makes no network requests, writes clearly
marked sample data, and exits successfully. API failures fail the update without
overwriting the previous file. Nothing schedules or publishes until the workflow
is on `main`; it never merges PRs or changes auto-merge settings.

Network-free checks and dry runs:

```sh
python3 -m unittest discover -s scripts -p 'test_x_latest.py' -v
python3 scripts/update_x_latest.py --sample --output /tmp/x-sample.json
python3 scripts/update_x_latest.py --fixture /path/to/public-api-fixture.json --output /tmp/x-shaped.json
python3 scripts/check.py
```

The JSON contract follows X's [data dictionary](https://docs.x.com/x-api/fundamentals/data-dictionary)
and [expansions documentation](https://docs.x.com/x-api/fundamentals/expansions).
