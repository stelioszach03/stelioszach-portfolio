from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_BREAK
import argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Create the November 2026 editable career CVs. Render and inspect before publishing PDFs.')
parser.add_argument('--focus', choices=['machine-learning','systems','all'], default='all')
parser.add_argument('--phone', help='Public contact number to include on the CV')
parser.add_argument('--output-dir', type=Path, default=ROOT/'cv-review')
args=parser.parse_args()
OUT=args.output_dir
OUT.mkdir(parents=True,exist_ok=True)

def link(p,text,url,bold=False):
 r=OxmlElement('w:hyperlink');r.set(qn('r:id'),p.part.relate_to(url,'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',is_external=True));run=OxmlElement('w:r');pr=OxmlElement('w:rPr');color=OxmlElement('w:color');color.set(qn('w:val'),'000000');pr.append(color);
 if bold: pr.append(OxmlElement('w:b'))
 run.append(pr);t=OxmlElement('w:t');t.text=text;run.append(t);r.append(run);p._p.append(r)

def build(systems=False):
 d=Document();sec=d.sections[0];sec.page_width=Inches(8.5);sec.page_height=Inches(11);sec.top_margin=Inches(.48);sec.bottom_margin=Inches(.48);sec.left_margin=Inches(.58);sec.right_margin=Inches(.58)
 normal=d.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(10.3);normal.font.color.rgb=RGBColor(0,0,0);pf=normal.paragraph_format;pf.space_after=Pt(3);pf.line_spacing=1.03
 for name in ['Title','Subtitle','Heading 1','Heading 2']:
  st=d.styles[name];st.font.name='Arial';st.font.color.rgb=RGBColor(0,0,0)

 for st in d.styles:
  for border in st.element.xpath('.//w:pBdr'): border.getparent().remove(border)
 d.styles['Title'].font.size=Pt(25);d.styles['Title'].font.bold=True;d.styles['Title'].paragraph_format.space_after=Pt(3)
 d.styles['Heading 1'].font.size=Pt(10);d.styles['Heading 1'].font.bold=True;d.styles['Heading 1'].paragraph_format.space_before=Pt(10);d.styles['Heading 1'].paragraph_format.space_after=Pt(4)
 for name in ['Normal','Title','Heading 1']:
  d.styles[name].paragraph_format.widow_control=True
 d.core_properties.author='Stelios Zacharioudakis';d.core_properties.title='Stelios Zacharioudakis - '+('ML Systems Engineer' if systems else 'Machine Learning Engineer');d.core_properties.subject='Professional resume - November 2026'
 d.add_paragraph('Stelios Zacharioudakis','Title')
 p=d.add_paragraph();r=p.add_run('ML SYSTEMS ENGINEER | INFERENCE & SOFTWARE ENGINEERING' if systems else 'MACHINE LEARNING ENGINEER | APPLIED AI & ML SYSTEMS');r.bold=True;r.font.size=Pt(10.3)
 p=d.add_paragraph('New York City Metropolitan Area | ')
 if args.phone:
  link(p,args.phone,'tel:+'+''.join(c for c in args.phone if c.isdigit()))
  p.add_run(' | ')
 link(p,'stelios@stelioszach.com','mailto:stelios@stelioszach.com')
 p.paragraph_format.space_after=Pt(1)
 p=d.add_paragraph();link(p,'stelioszach.com','https://stelioszach.com');p.add_run(' | ');link(p,'github.com/stelioszach03','https://github.com/stelioszach03');p.add_run(' | ');link(p,'linkedin.com/in/stelios-zach','https://www.linkedin.com/in/stelios-zach')
 for r in p.runs:r.font.size=Pt(9)
 d.add_paragraph('ML systems engineer with end-to-end ownership of a deployed association platform. Build reproducible inference benchmarks and monitored data services, with hands-on work in APIs, access control and Linux deployment.' if systems else 'Machine learning engineer with end-to-end ownership of a deployed association platform. Build multilingual LLM workflows, evaluate coding agents against baselines and benchmark GPU inference.')
 def head(s):d.add_paragraph(s.upper(),'Heading 1')
 def title(s,tail='',url=None):
  p=d.add_paragraph();p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(2);p.paragraph_format.keep_with_next=True
  if url:link(p,s,url,True)
  else:p.add_run(s).bold=True
  if tail:p.add_run(' | '+tail)
  return p
 def bullet(s):
  p=d.add_paragraph();p.paragraph_format.left_indent=Inches(.12);p.paragraph_format.first_line_indent=Inches(-.12);p.add_run('• ');p.add_run(s)
 head('Professional experience')
 title('Paphos Medical Association - Head Engineer (Pro Bono)','Jun 2022 - Jul 2026')
 bullet('Owned architecture, implementation and Linux deployment for AsklepiosMed, a production platform I built and donated to consolidate member services and association administration.')
 bullet('Built the React, Express and PostgreSQL stack, including role-based access, member workflows and administrative publishing.')
 head('Selected engineering projects')
 if systems:
  title('Inference Systems Lab - GPU serving evaluation',url='https://github.com/stelioszach03/colab-speculative-decoding-speed-lab')
  bullet('Benchmarked 16,384 vLLM requests across RTX 4090/A100, two models and four repeats; measured 1.23-1.47x cached/uncached throughput ratios for shared-prefix workloads at concurrency 32, with output mismatches disclosed.')
  title('MTA-Scan - Streaming data and temporal evaluation',url='https://stelioszach.com/demos/mta-scan/')
  bullet('Built a monitored GTFS-Realtime pipeline and FastAPI/Mapbox workspace with freshness checks and forecast expiry. Verified 44 daily exports and evaluated arrival-spacing proxy forecasts over 28 days.')
  title('ForgeRL / ForgeBench - Reinforcement learning and agent evaluation',url='https://stelioszach.com/demos/forgerl/')
  bullet('Built a sandboxed coding-agent benchmark with fitted-Q routing and persistent spend controls. Compared six policies in 162 transfer episodes and ran a separate 1,296-attempt follow-up.')
  bullet('On the follow-up primary slice, strong-only routing succeeded on 131 of 144 attempts at lower accounted model cost than fitted-Q routing, which succeeded on 128 of 144.')
  title('AsklepiosMed - Multilingual NLP workflows',url='https://stelioszach.com/#asklepios')
  bullet('Extended the platform after the pro bono role with LLM-assisted drafting and proofreading for administrative publishing.')
  bullet('Built Greek-to-English, Russian and Simplified Chinese translation with terminology checks, structured output validation, fallback handling and editor review.')
  title('MRI reconstruction - PyTorch and generative models',url='https://stelioszach.com/#mri')
  bullet('Reimplemented a published score-based reconstruction method with Flax-to-PyTorch checkpoint conversion; reproduced reference PSNR within 0.15 dB on 256 BraTS slices at 4x, 8x and 24x undersampling.')
  bullet('Evaluated reconstruction quality, uncertainty and retrospective domain shift; published reproducible evidence and independent CPU ensemble diagnostics.')
 else:
  title('AsklepiosMed - Multilingual NLP workflows',url='https://stelioszach.com/#asklepios')
  bullet('Extended the platform after the pro bono role with LLM-assisted drafting and proofreading for administrative publishing.')
  bullet('Built Greek-to-English, Russian and Simplified Chinese translation with terminology checks, structured output validation, fallback handling and editor review.')
  title('ForgeRL / ForgeBench - Reinforcement learning and agent evaluation',url='https://stelioszach.com/demos/forgerl/')
  bullet('Built a sandboxed coding-agent benchmark with fitted-Q routing and persistent spend controls. Compared six policies in 162 transfer episodes and ran a separate 1,296-attempt follow-up.')
  bullet('On the follow-up primary slice, strong-only routing succeeded on 131 of 144 attempts at lower accounted model cost than fitted-Q routing, which succeeded on 128 of 144.')
  title('Inference Systems Lab - GPU serving evaluation',url='https://github.com/stelioszach03/colab-speculative-decoding-speed-lab')
  bullet('Benchmarked 16,384 vLLM requests across RTX 4090/A100, two models and four repeats; measured 1.23-1.47x cached/uncached throughput ratios for shared-prefix workloads at concurrency 32, with output mismatches disclosed.')
  title('MTA-Scan - Streaming data and temporal evaluation',url='https://stelioszach.com/demos/mta-scan/')
  bullet('Built a monitored GTFS-Realtime pipeline and FastAPI/Mapbox workspace with freshness checks and forecast expiry. Verified 44 daily exports and evaluated arrival-spacing proxy forecasts over 28 days.')
  title('MRI reconstruction - PyTorch and generative models',url='https://stelioszach.com/#mri')
  bullet('Reimplemented a published score-based reconstruction method with Flax-to-PyTorch checkpoint conversion; reproduced reference PSNR within 0.15 dB on 256 BraTS slices at 4x, 8x and 24x undersampling.')
  bullet('Evaluated reconstruction quality, uncertainty and retrospective domain shift; published reproducible evidence and independent CPU ensemble diagnostics.')
 head('Technical skills')
 p=d.add_paragraph();p.add_run('ML & AI: ').bold=True;p.add_run('Python, PyTorch, reinforcement learning, LLM agents, world models, generative models, NLP, vLLM, NumPy, SciPy, scikit-learn and experimental evaluation.')
 p=d.add_paragraph();p.add_run('Engineering: ').bold=True;p.add_run('FastAPI, React, Node.js/Express, JavaScript, PostgreSQL, Redis, Linux, Nginx, Docker, Git and automated testing.')
 head('Education')
 title('BSc in Computer Science','National and Kapodistrian University of Athens, Jun 2026')
 d.add_paragraph('Degree: Very Good | Thesis: Excellent (10/10), deposited September 2026.')
 path=OUT/('Stelios_Zacharioudakis_ML_Systems_CV.docx' if systems else 'Stelios_Zacharioudakis_ML_Engineer_CV.docx');d.save(path);print(path)
for systems in ([False,True] if args.focus=='all' else [args.focus=='systems']):build(systems)
