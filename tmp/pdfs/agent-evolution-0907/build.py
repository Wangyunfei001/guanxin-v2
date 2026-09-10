from pathlib import Path
import re,html,json
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader,PdfWriter
R=Path('/Users/wyf/workspace/aicoding/guanxin-v2'); D=R/'docs/research/2026-09-07-agent-evolution'; T=R/'tmp/pdfs/agent-evolution-0907'
s=(D/'report-source.md').read_text().split('---APPENDIX---')[0]
pdfmetrics.registerFont(TTFont('CN','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('CNB','/System/Library/Fonts/STHeiti Medium.ttc',subfontIndex=0))
styles={k:ParagraphStyle(k,fontName='CNB' if k in ['h','sub','th'] else 'CN',fontSize=z,leading=l,spaceAfter=6,spaceBefore=5 if k=='sub' else 0,wordWrap='CJK',textColor=colors.HexColor('#087B83' if k=='sub' else '#183340'),keepWithNext=k in ['h','sub']) for k,z,l in [('h',20,27),('sub',11.5,17),('p',9.5,14.6),('td',8.8,13),('th',9,13)]}
styles['th'].textColor=colors.white

def p(t,k='p'):
 t=html.escape(t);t=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<link href="\2" color="#087B83"><u>\1</u></link>',t)
 return Paragraph(t,styles[k])
story=[]
for j,sec in enumerate(s.split('---PAGE---')):
 if j:story.append(PageBreak())
 lines=sec.strip().splitlines();i=0
 while i<len(lines):
  x=lines[i].strip();i+=1
  if not x:continue
  if x.startswith('|'):
   rows=[x]
   while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1
   data=[]
   for row in rows:
    c=[a.strip() for a in row.strip('|').split('|')]
    if all(re.fullmatch(r'[-: ]+',a) for a in c):continue
    data.append([p(a,'th' if not data else 'td') for a in c])
   tab=Table(data,colWidths=[85,216,198],repeatRows=1)
   tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#183340')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#EFF5F6'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
   story.extend([tab,Spacer(1,8)]);continue
  story.append(p(x[3:] if x.startswith('## ') else x[2:] if x.startswith('# ') else x,'sub' if x.startswith('## ') else 'h' if x.startswith('# ') else 'p'))

def page(c,d):
 c.setFillColor(colors.HexColor('#526776'));c.setFont('CN',7)
 c.drawString(48,817,'观心 v2 · 演进研究复核版');c.drawRightString(547,817,'2026-09-07')
 c.drawString(48,25,'研究建议，尚未实施 · 后附 2026-09-04 历史研究');c.drawRightString(547,25,str(d.page))
 c.setStrokeColor(colors.HexColor('#D7E3E8'));c.line(48,807,547,807)
cover=T/'update.pdf'
SimpleDocTemplate(str(cover),pagesize=A4,topMargin=50,bottomMargin=45,leftMargin=48,rightMargin=48,title='观心 v2 演进研究：2026-09-07 复核',author='Codex').build(story,onFirstPage=page,onLaterPages=page)
w=PdfWriter();w.append(str(cover));w.append(str(R/'output/pdf/guanxin-v2-evolution-research-2026-09-04.pdf'))
w.add_metadata({'/Title':'观心 v2 演进路线、迭代计划与最终目标：2026-09-07 复核版','/Author':'Codex'})
out=R/'output/pdf/guanxin-v2-evolution-research-2026-09-07.pdf'
with out.open('wb') as f:w.write(f)
print('new pages',len(PdfReader(cover).pages),'total',len(PdfReader(out).pages),'bytes',out.stat().st_size)
ledger=json.loads((R/'docs/research/2026-09-04-agent-evolution/claim-source-ledger.json').read_text())
for e in ledger:e['evidence_scope']='2026-09-04历史附录，非全部当日刷新'
for title,url in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',s):
 ledger.append({'title':title,'url':url,'access_date':'2026-09-07','publication_date':'未核实页面更新时间','evidence_scope':'本轮复核正文','claim':next(line for line in s.splitlines() if f']({url})' in line)})
(D/'claim-source-ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2))
