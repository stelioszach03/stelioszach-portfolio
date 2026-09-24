from pathlib import Path
import argparse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Build an evidence-grounded one-page CV.')
parser.add_argument('--focus',choices=['research','systems'],default='research')
args=parser.parse_args()
systems=args.focus=='systems'
OUT=ROOT/'public'/('Stelios_Zacharioudakis_Systems_CV.pdf' if systems else 'Stelios_Zacharioudakis_CV.pdf')
OUT.parent.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(OUT),pagesize=letter)
c.setTitle('Stelios Zacharioudakis - '+('ML Systems and Software Engineering' if systems else 'Machine Learning Research and Engineering'))
c.setAuthor('Stelios Zacharioudakis')
c.setSubject('Professional resume - September 2026')
W,H=letter;left=43;right=43;width=W-left-right;y=H-43
INK=HexColor('#152537');MUTED=HexColor('#425466');ACCENT=HexColor('#164E79')
normal=ParagraphStyle('body',fontName='Helvetica',fontSize=9.7,leading=13.2,textColor=INK,spaceAfter=0)
small=ParagraphStyle('small',parent=normal,fontSize=8.7,leading=11.8,textColor=MUTED)

def para(text,style=normal,gap=4,indent=0):
 global y
 p=Paragraph(text,style);_,height=p.wrap(width-indent,1000)
 y-=height;p.drawOn(c,left+indent,y);y-=gap

def section(title):
 global y
 y-=11;c.setFillColor(ACCENT);c.setFont('Helvetica-Bold',10);c.drawString(left,y,title.upper());y-=7
 c.setStrokeColor(HexColor('#CBD5DF'));c.setLineWidth(.45);c.line(left,y,W-right,y);y-=11

def bullet(text):para('&#8226; '+text,normal,4,0)

c.setFillColor(INK);c.setFont('Helvetica-Bold',25);c.drawString(left,y,'Stelios Zacharioudakis');y-=21
c.setFont('Helvetica',11.7);c.setFillColor(ACCENT);c.drawString(left,y,'ML SYSTEMS & SOFTWARE ENGINEERING' if systems else 'MACHINE LEARNING RESEARCH & ENGINEERING');y-=18
para('<link href="mailto:stelios@stelioszach.com">stelios@stelioszach.com</link>  |  <link href="https://stelioszach.com">stelioszach.com</link>  |  <link href="https://github.com/stelioszach03">github.com/stelioszach03</link>',small,3)
para('<link href="https://www.linkedin.com/in/stelios-zach">linkedin.com/in/stelios-zach</link>',small,5)
para('Software engineering for ML evaluation and deployed applications: bounded execution, APIs, data pipelines, reproducible artifacts and operational safeguards.' if systems else 'Machine learning research and software engineering, focused on generative models, model-based reinforcement learning, reliable evaluation and deployed systems.',normal,2)

section('Engineering experience')
para('<b>Former Head Engineer - Paphos Medical Association</b>  |  Pro bono',normal,2)
para('Jun 2022 - Jul 2026',small,4)
bullet('Led pro bono engineering for <link href="https://asklepiosmed.org">AsklepiosMed</link>, a donated member-services platform for the association.')
bullet('Developed full-stack web applications and administrative workflows using React, Node.js/Express and PostgreSQL.')
bullet('Maintained the platform and supported its deployment and operation on a Linux VPS.')

section('Research')
para('<b>World-model learning and evaluation</b>  |  Independent research, ongoing and unpublished',normal,4)
bullet('Investigate imagination horizons, critic stability and policy selection with PyTorch latent world models and imagined actor-critic learning.')
bullet('Design controlled ablations, paired simulator evaluations and traceable analyses to study task-dependent outcomes and failed hypotheses.')
para('<b>Score-based generative models for undersampled MRI reconstruction</b>  |  BSc thesis',normal,4)
bullet('Reimplemented a published reconstruction method in PyTorch using the authors\' pretrained prior; developed MRI measurement operators and a Flax-to-PyTorch checkpoint conversion.')
bullet('The thesis reports reproduction within 0.15 dB PSNR on 256 BraTS slices at 4x, 8x and 24x sampling factors; evaluates Monte Carlo uncertainty and retrospective domain shift.')
para('<link href="https://stelioszach.com/documents/zacharioudakis-bsc-thesis-2026.pdf">Thesis document: September 2026</link>. Reproduction and experimental analysis; no claim of clinical validation.',small,1)

section('Selected software projects')
para('<b><link href="https://forge.stelioszach.com/">ForgeRL / ForgeBench</link></b> - 50 authored scenarios, 10 miniature repository families and five routing policies. Completed 300 evaluation episodes plus 180 controller-training episodes; isolated execution, bounded provider spending and inspectable trajectories. Two held-out test families limit generalization.',normal,6)
para('<b><link href="https://stelioszach.com/demos/mta-scan/">MTA Scan</link></b> - Built a public-transit workspace with Mapbox GL, station inspection, source freshness and snapshot export. Live arrival estimates are separated from the constructed replay evaluation; no validated incident-prediction claim.',normal,6)
para('<b><link href="https://stelioszach.com/demos/deid/">DeID Review Workspace</link></b> - Developed a human-review workflow for English text using pretrained NER and patterns: inspect spans, apply or keep suggestions, manually redact missed spans and export explicit decisions.',normal,1)

section('Education')
para('<b>BSc in Computer Science</b> - National and Kapodistrian University of Athens',normal,2)
para('Department of Informatics and Telecommunications  |  June 2026',small,1)

section('Technical focus')
para('<b>ML:</b> Python, PyTorch, NumPy, SciPy, scikit-learn; generative models, model-based RL, uncertainty analysis and experimental evaluation.',normal,4)
para('<b>Systems:</b> FastAPI, Node.js/Express, React, JavaScript, SQL/PostgreSQL, Redis, Linux, Nginx, Docker, Git and automated testing.',normal,0)
assert y>32,f'CV overflow: bottom {y}'
c.showPage();c.save();print({'path':str(OUT),'pages':1,'bottomMarginPoints':round(y,1)})
