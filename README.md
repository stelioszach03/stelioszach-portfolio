# Stelios Zacharioudakis — portfolio

Source for [stelioszach.com](https://stelioszach.com): a static portfolio of machine learning research and software engineering work.

The site selects five core projects: the MRI reconstruction thesis and evidence package, ForgeRL, the donated AsklepiosMed platform, MTA-Scan and Inference Systems Lab. A compact section describes ongoing, unpublished world-model research. Three selected live demos—ForgeRL, MTA-Scan and the secondary DeID review tool—keep their methods, evidence and limitations alongside the interface. Five demo services remain available; selection does not remove their routes or source.

## Selected projects

| Project | Evidence or live interface | Source or case study |
| --- | --- | --- |
| MRI reconstruction | [Thesis and methods](https://stelioszach.com/#mri) | [Public BSc thesis](public/documents/zacharioudakis-bsc-thesis-2026.pdf) |
| ForgeRL | [ForgeBench evidence dashboard](https://stelioszach.com/demos/forgerl/) | [Standalone source](https://github.com/stelioszach03/forgerl) · [Engineering case study](case-studies/forgerl.md) |
| AsklepiosMed | [Public association website](https://asklepiosmed.org/) | [Engineering case study](case-studies/asklepiosmed.md) |
| MTA-Scan | [Live subway monitor](https://stelioszach.com/demos/mta-scan/) | [Deployed adapter and UI](demo-services/mta-scan) |
| Inference Systems Lab | [Controlled RTX 4090 study](https://github.com/stelioszach03/colab-speculative-decoding-speed-lab/blob/main/artifacts/controlled-pilot-v1/RESULTS.md) | [Runner, raw traces and GPU telemetry](https://github.com/stelioszach03/colab-speculative-decoding-speed-lab) |
| DeID — secondary tool | [Text review interface](https://stelioszach.com/demos/deid/) | [Review workflow case study](case-studies/deid-review.md) |

The demos expose bounded interfaces. ForgeRL now includes ForgeBench: 50 authored scenarios across 10 miniature Python repository families and five routing policies. Its public dashboard now opens the separately frozen v0.3 pilot (162 episodes, six policies) and preserves v0.2. Browsing/replay makes no inference calls. An optional explicit live trial submits one fixed task to GPT-OSS20B through a private broker, with $0.05/day and $1/month caps plus the unchanged lifetime ledger; it is not a benchmark result. Private operator-run research compares GPT-OSS 20B and 120B through a fixed-provider OpenRouter profile. A finite fitted-Q controller learns routing actions; language-model weights remain unchanged. Recorded prompts, supplied files, patches, tests, retries, model switches and provider accounting remain inspectable. Catalog size and actual evaluation coverage are distinct. Use synthetic text inputs in DeID. MTA's constructed replay is separate from public-feed observations and autonomous temporal evaluation. The latter measures future feed-predicted arrival-spacing proxies with chronological holdouts; current short-window feasibility does not validate incident prediction. AsklepiosMed application source and member records remain private.

The [MRI evidence companion](https://github.com/stelioszach03/mri-reconstruction-evidence) reproduces tables and plots from eight historical aggregate files and offers independent CPU ensemble diagnostics. Its illustrative example is synthetic; it does not rerun or distribute the solver. Inference Systems Lab reports a predeclared single-GPU pilot with 1,536 measured requests. Cache modes matched output text in only 210/768 paired comparisons, so the performance observations are not an output-equivalent or lossless speedup claim. DeID's separate library evaluation measured strict mapped-label F1 of 40.21% on 500 external synthetic records; that result is not a benchmark of the live review adapter or clinical validation.

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

[ForgeRL](https://github.com/stelioszach03/forgerl) is maintained in its own repository with its task catalog, model provider, isolated executor, controller, frontend and experiment protocol. Its paid research commands are distinct from the offline regression checks. The portfolio case study describes the integration; this repository does not duplicate that runtime.

The demo test package has locked **development-only** jsdom and Playwright dependencies. Separate CI jobs exercise synthetic SMT/fraud interfaces, Python worker cancellation and source checks, and offline Chromium DeID/MTA regressions. None of those jobs trains a model, sends user data, contacts live inference services or collects MTA feeds. The original website checks run unchanged in their own job. See the demo README for commands and coverage limits.

## Hosting

Serve `dist/` as the website root. The five `/demos/` routes belong to separate services and are intentionally not bundled here. Preserve their reverse-proxy routes when deploying this site. The historical `/Stelios_Zacharioudakis_CV.pdf` URL is retained, including compatibility with existing query strings.

The CV and thesis are served as PDF documents. The sitemap lists the portfolio and the five demo entry points. No client-side router or fallback to an empty application shell is needed.

Two CV editions share the same factual record: [Research / ML](public/Stelios_Zacharioudakis_CV.pdf) and [ML Systems / Software](public/Stelios_Zacharioudakis_Systems_CV.pdf). To regenerate them with Python and ReportLab, run `python scripts/build_cv.py` and `python scripts/build_cv.py --focus systems`; render and inspect both PDFs before publishing. PDF generation is an authoring step, not a website runtime dependency. The four-item evidence strip links to the relevant study, thesis and case studies. The ForgeBench report is a technical report, not a peer-reviewed publication or submitted preprint.

## Content and provenance

- The BSc was completed in June 2026; the thesis manuscript is dated September 2026. These are separate dates.
- The MRI figure comes from the accompanying reconstruction experiments. The case study includes the unmodified full figure. Numerical results are reported in the thesis and concern retrospective research, not clinical validation.
- World-model research is explicitly ongoing and unpublished. The portfolio does not claim a peer-reviewed publication or general performance superiority.
- ForgeBench uses 50 authored miniature-repository scenarios with reference implementations and hidden grading; it is not SWE-bench or a contamination-resistant private benchmark. Its five-policy protocol separates controller learning from unchanged language-model weights. Outcomes are reported only through recorded artifacts, and reported provider charges are distinguished from conservative reservations. The v0.1 pilot remains separately archived; its results are not pooled with v0.2.
- The Paphos Medical Association role was pro bono, June 2022–July 2026. The public case study separates that former role from the platform’s subsequent development and does not expose member data or private application source.
- Demos link their own source repositories and describe their data and evaluation limits. Their backend implementations are maintained separately.

The thesis PDF is a public copy with the student registry identifier redacted; its academic content is unchanged. Public documents and research imagery are not covered by the code licence below.

## Licence

Original website source code is available under the [MIT licence](LICENSE). The thesis, CV, research figure and any other non-code content retain their respective copyright and licensing; see [NOTICE](NOTICE). Publishing them here does not grant an MIT licence to those materials.

The [TrustQueryNet evidence release](https://github.com/stelioszach03/TrustQueryNet/releases/tag/evidence-2026-09-24) preserves a complete cross-image audit and a new matched two-seed frozen-feature repair pilot. All 36 result rows and negative findings are published; MC repair did not improve HAM balanced accuracy in this pilot. This secondary experiment is not historical full-CNN replication or clinical validation.

See the [evidence index](docs/EVIDENCE_INDEX.md) for the measured results, original artifacts and remaining research limits across the public projects.
