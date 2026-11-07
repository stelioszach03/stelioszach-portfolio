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
 p=d.add_paragraph();r=p.add_run('ML SYSTEMS ENGINEER | APPLIED AI & MODEL EVALUATION' if systems else 'MACHINE LEARNING ENGINEER | APPLIED AI, NLP & DEEP LEARNING');r.bold=True;r.font.size=Pt(10.3)
 p=d.add_paragraph('New York City Metropolitan Area | ');link(p,'stelios@stelioszach.com','mailto:stelios@stelioszach.com');p.paragraph_format.space_after=Pt(1)
 p=d.add_paragraph();link(p,'stelioszach.com','https://stelioszach.com');p.add_run(' | ');link(p,'github.com/stelioszach03','https://github.com/stelioszach03');p.add_run(' | ');link(p,'linkedin.com/in/stelios-zach','https://www.linkedin.com/in/stelios-zach')
 for r in p.runs:r.font.size=Pt(9)
 d.add_paragraph('Machine learning engineer combining production software ownership with applied AI/NLP, PyTorch research and GPU inference evaluation. Led architecture and delivery of a donated association platform; build reproducible experiments, LLM applications and data pipelines with explicit quality and operational controls.')
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
 bullet('Led architecture, development and delivery of AsklepiosMed, a donated production platform for member services and association administration.')
 bullet('Integrated React interfaces, Node.js/Express APIs and PostgreSQL persistence; maintained access controls, administrative workflows and Linux deployment.')
 head('Selected projects and research')
 title('AsklepiosMed - Multilingual NLP workflows',url='https://stelioszach.com/#asklepios')
 bullet('Engineered multilingual NLP workflows for announcement drafting, email preparation, proofreading and text improvement within the association publishing platform.')
 bullet('Implemented Greek-to-English, Russian and Simplified Chinese translation with terminology checks, structured output validation, fallback behavior and token-usage controls.')
 title('Inference Systems Lab - GPU serving evaluation',url='https://github.com/stelioszach03/colab-speculative-decoding-speed-lab')
 bullet('Designed and ran 16,384 vLLM requests across RTX 4090 and A100 GPUs, two Qwen2.5 model sizes, cache modes and four repeats; measured throughput and latency, audited output parity and published reproducible aggregates.')
 title('MRI reconstruction - PyTorch and generative models','BSc thesis: Excellent, 10/10',url='https://stelioszach.com/#mri')
 bullet('Reimplemented a published score-based reconstruction method with Flax-to-PyTorch checkpoint conversion; reproduced reference PSNR within 0.15 dB on 256 BraTS slices at 4x, 8x and 24x undersampling.')
 bullet('Evaluated uncertainty and retrospective domain shift; released reproducible evidence and independent CPU ensemble diagnostics. Original pretrained prior credited; no clinical validation.')
 title('ForgeRL / ForgeBench - LLM agent evaluation',url='https://stelioszach.com/demos/forgerl/')
 bullet('Built a sandboxed code-repair harness, durable budget ledger and trace explorer; evaluated six routing policies in a 162-episode transfer pilot and 1,296 attempts in a separate four-seed follow-up. Model weights remained unchanged.')
 title('MTA-Scan - Streaming data and temporal evaluation',url='https://stelioszach.com/demos/mta-scan/')
 bullet('Built live feed ingestion, a FastAPI/Mapbox workspace and bounded historical storage; automated chronological 15/30-minute proxy forecasting with baselines and freshness gates. November audit: 44 daily exports and 28 evaluated days.')
 head('Technical skills')
 p=d.add_paragraph();p.add_run('ML & AI: ').bold=True;p.add_run('Python, PyTorch, NumPy, SciPy, scikit-learn, generative models, NLP, LLM integration, vLLM, reinforcement learning, experiment design and model evaluation.')
 p=d.add_paragraph();p.add_run('Engineering: ').bold=True;p.add_run('FastAPI, React, Node.js/Express, JavaScript, PostgreSQL, Redis, Linux, Nginx, Docker, Git and automated testing.')
 head('Education and ongoing research')
 title('BSc in Computer Science','National and Kapodistrian University of Athens, Jun 2026')
 d.add_paragraph('Degree: Very Good | Thesis: Excellent (10/10), deposited September 2026.')
 d.add_paragraph('Independent research: latent world models, imagination horizons and policy evaluation in PyTorch; ongoing and unpublished.')
 path=OUT/('Stelios_Zacharioudakis_ML_Systems_CV.docx' if systems else 'Stelios_Zacharioudakis_ML_Engineer_CV.docx');d.save(path);print(path)
for systems in ([False,True] if args.focus=='all' else [args.focus=='systems']):build(systems)
