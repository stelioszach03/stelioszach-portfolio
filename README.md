# Stelios Zacharioudakis — portfolio

Source for [stelioszach.com](https://stelioszach.com): a static portfolio of machine learning research and software engineering work.

The site selects three core projects: the MRI reconstruction thesis, the donated AsklepiosMed platform and MTA-Scan. A compact section describes ongoing, unpublished world-model research. Two selected live demos—MTA-Scan and the secondary DeID review tool—keep their methods, evidence and limitations alongside the interface. Four demo services remain available; selection does not remove their routes or source.

## Selected projects

| Project | Evidence or live interface | Source or case study |
| --- | --- | --- |
| MRI reconstruction | [Thesis and methods](https://stelioszach.com/#mri) | [Public BSc thesis](public/documents/zacharioudakis-bsc-thesis-2026.pdf) |
| AsklepiosMed | [Public association website](https://asklepiosmed.org/) | [Engineering case study](case-studies/asklepiosmed.md) |
| MTA-Scan | [Live subway monitor](https://stelioszach.com/demos/mta-scan/) | [Deployed adapter and UI](demo-services/mta-scan) |
| DeID — secondary tool | [Text review interface](https://stelioszach.com/demos/deid/) | [Review workflow case study](case-studies/deid-review.md) |

The demos expose bounded adapters, not every capability of their upstream repositories. Use synthetic text inputs. MTA's constructed replay is separate from live public-feed observations and does not validate incident prediction. AsklepiosMed application source and member records remain private.

Additional preserved interfaces—[constraint verifier](https://stelioszach.com/demos/smt-verify/) and [synthetic transaction graph](https://stelioszach.com/demos/fraud-graph/)—remain available for existing links and source inspection in [`demo-services/`](demo-services/README.md). They are not selected homepage projects.

## Architecture

- Semantic HTML delivers the complete content before JavaScript runs.
- CSS provides responsive layouts, the navy/teal visual identity, print styles and reduced-motion support.
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

The build checks that both linked documents are actual PDF files, copies `public/` into `dist/`, versions the built CSS/JS URLs with content hashes, and writes a SHA-256 file manifest to `build-manifest.json`. The manifest hashes the final HTML after URL rewriting; preview source paths stay unchanged. Tests cover semantic content, local links/assets, scientific claim boundaries and mobile-menu behavior. CI checks syntax, runs the tests and builds the site; it does not deploy.

## Demo source and regression tests

[`demo-services/`](demo-services/README.md) contains the four standalone runtime adapters, selected vendor modules, public/synthetic data and their original licence notices. The portfolio build does not bundle or launch these services. Their model dependencies are installed separately.

The demo test package has locked **development-only** jsdom and Playwright dependencies. Separate CI jobs exercise synthetic SMT/fraud interfaces, Python worker cancellation and source checks, and offline Chromium DeID/MTA regressions. None of those jobs trains a model, sends user data, contacts live inference services or collects MTA feeds. The original website checks run unchanged in their own job. See the demo README for commands and coverage limits.

## Hosting

Serve `dist/` as the website root. The four `/demos/` routes belong to separate services and are intentionally not bundled here. Preserve their reverse-proxy routes when deploying this site. The historical `/Stelios_Zacharioudakis_CV.pdf` URL is retained, including compatibility with existing query strings.

The CV and thesis are served as PDF documents. The sitemap lists the portfolio and the four demo entry points. No client-side router or fallback to an empty application shell is needed.

## Content and provenance

- The BSc was completed in June 2026; the thesis manuscript is dated September 2026. These are separate dates.
- The MRI figure comes from the accompanying reconstruction experiments. The case study includes the unmodified full figure. Numerical results are reported in the thesis and concern retrospective research, not clinical validation.
- World-model research is explicitly ongoing and unpublished. The portfolio does not claim a peer-reviewed publication or general performance superiority.
- The Paphos Medical Association role was pro bono, June 2022–July 2026. The public case study separates that former role from the platform’s subsequent development and does not expose member data or private application source.
- Demos link their own source repositories and describe their data and evaluation limits. Their backend implementations are maintained separately.

The thesis PDF is a public copy with the student registry identifier redacted; its academic content is unchanged. Public documents and research imagery are not covered by the code licence below.

## Licence

Original website source code is available under the [MIT licence](LICENSE). The thesis, CV, research figure and any other non-code content retain their respective copyright and licensing; see [NOTICE](NOTICE). Publishing them here does not grant an MIT licence to those materials.
