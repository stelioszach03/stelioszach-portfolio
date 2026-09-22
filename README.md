# Stelios Zacharioudakis — portfolio

Source for [stelioszach.com](https://stelioszach.com): a static portfolio of machine learning research and software engineering work.

The site presents MRI reconstruction research, ongoing unpublished world-model research, a donated medical-association platform, and four separately hosted interactive demos. Each project keeps its methods, evidence and limitations together.

## Architecture

- Semantic HTML delivers the complete content before JavaScript runs.
- CSS provides responsive layouts, light/dark appearance, print styles and reduced-motion support.
- A small JavaScript enhancement controls the mobile menu; native `<details>` elements work without it.
- Assets and fonts are local or system-provided. The portfolio has no analytics, tracking cookies, contact form or model requests.
- There are no runtime or build dependencies to install. Build and test scripts use Node.js standard-library modules.

## Develop and validate

Requirements: Node.js 22 or later. CI uses Node.js 24. Python 3 is optional for the local preview command.

```sh
npm run check
npm test
npm run build
python3 -m http.server 5183 --directory dist --bind 127.0.0.1
```

Open `http://127.0.0.1:5183` after starting the preview. To preview edits before building, serve `public/` instead of `dist/`.

The build checks that both linked documents are actual PDF files, copies `public/` into `dist/`, and writes a SHA-256 file manifest to `build-manifest.json`. Tests cover semantic content, local links/assets, scientific claim boundaries and mobile-menu behavior. CI checks syntax, runs the tests and builds the site; it does not deploy.

## Hosting

Serve `dist/` as the website root. The four `/demos/` routes belong to separate services and are intentionally not bundled here. Preserve their reverse-proxy routes when deploying this site. The historical `/Stelios_Zacharioudakis_CV.pdf` URL is retained, including compatibility with existing query strings.

The CV and thesis are served as PDF documents. The sitemap lists the portfolio and the four demo entry points. No client-side router or fallback to an empty application shell is needed.

## Content and provenance

- The BSc was completed in June 2026; the thesis manuscript is dated September 2026. These are separate dates.
- The MRI figure comes from the accompanying reconstruction experiments. The hero shows its first example and links the unmodified full figure. Numerical results are reported in the thesis and concern retrospective research, not clinical validation.
- World-model research is explicitly ongoing and unpublished. The portfolio does not claim a peer-reviewed publication or general performance superiority.
- The Paphos Medical Association role is current and pro bono. The public case study does not expose member data or private application source.
- Demos link their own source repositories and describe their data and evaluation limits. Their backend implementations are maintained separately.

The thesis PDF is a public copy with the student registry identifier redacted; its academic content is unchanged. Public documents and research imagery are not covered by the code licence below.

## Licence

Original website source code is available under the [MIT licence](LICENSE). The thesis, CV, research figure and any other non-code content retain their respective copyright and licensing; see [NOTICE](NOTICE). Publishing them here does not grant an MIT licence to those materials.
