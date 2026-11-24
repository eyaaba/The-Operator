"""Build the four-page CS496 'The Operator' report.

Run from the project root after copying this file to scripts/build_report.py:
    uv sync --extra report
    uv run python scripts/build_report.py

Only verified offline evidence is prefilled. Live results are loaded only when
all 32 scenario rows are present, have completed without API errors, and carry
real measurement fields. Otherwise the report reports live metrics as pending.
"""
from __future__ import annotations

import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == 'scripts' else HERE
OUT = ROOT / 'report.pdf'
RESULTS = ROOT / 'eval' / 'results' / 'latest.json'
SUMMARY = ROOT / 'eval' / 'results' / 'summary.json'
W, H = A4
NAVY=HexColor('#12243A'); DEEP=HexColor('#0B1829'); BLUE=HexColor('#315AA9')
TEAL=HexColor('#008E94'); PALE=HexColor('#EDF6F6'); MIST=HexColor('#F4F7FA')
SLATE=HexColor('#536477'); SOFT=HexColor('#DCE5EB'); WHITE=HexColor('#FFFFFF')
AMBER=HexColor('#B87721'); LIGHT_AMBER=HexColor('#FFF5E5'); GREEN=HexColor('#198268')
FONTDIR=Path('/usr/share/fonts/truetype/lato')
if FONTDIR.exists():
    pdfmetrics.registerFont(TTFont('Lato',str(FONTDIR/'Lato-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Lato-Bold',str(FONTDIR/'Lato-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('Lato-Heavy',str(FONTDIR/'Lato-Heavy.ttf')))
    pdfmetrics.registerFontFamily('Lato',normal='Lato',bold='Lato-Bold',italic='Lato',boldItalic='Lato-Bold')
    F='Lato'; FB='Lato-Bold'; FH='Lato-Heavy'
else:
    F='Helvetica'; FB='Helvetica-Bold'; FH=FB

BODY=ParagraphStyle('body',fontName=F,fontSize=9.1,leading=13.65,textColor=NAVY)
BODYSM=ParagraphStyle('small',parent=BODY,fontSize=8.4,leading=12.3)
TINY=ParagraphStyle('tiny',parent=BODY,fontSize=7.8,leading=11.1)


def text(c,s,x,y,size=10,color=NAVY,font=None):
    c.setFillColor(color); c.setFont(font or F,size); c.drawString(x,y,s)

def para(c,txt,x,top,width,style=BODY):
    p=Paragraph(txt,style); _,h=p.wrap(width,2000);p.drawOn(c,x,top-h)
    return top-h

def rect(c,x,y,w,h,fill,r=12,stroke=None):
    c.setFillColor(fill)
    if stroke:c.setStrokeColor(stroke)
    c.roundRect(x,y,w,h,r,fill=1,stroke=1 if stroke else 0)

def rule(c,y,x=43,w=W-86):
    c.setStrokeColor(SOFT); c.setLineWidth(.7);c.line(x,y,x+w,y)

def section(c,num,title,y):
    text(c,f'{num:02d}',44,y,9,TEAL,FB)
    text(c,title,73,y-1,13,NAVY,FB)
    return y-19

def bullets(c,items,x,y,w=465,style=BODY,spacing=9):
    for item in items:
        c.setFillColor(TEAL);c.circle(x+3,y-6,2,fill=1,stroke=0)
        y=para(c,item,x+13,y,w-13,style)-spacing
    return y

def footer(c,n,topic):
    rule(c,47)
    text(c,'THE OPERATOR  /  CS496 AI ENGINEERING',44,29,8,SLATE,FB)
    text(c,topic,310,29,8,SLATE)
    c.setFont(FB,9);c.drawRightString(W-44,29,f'{n} / 4')

def header(c,n,kicker,title,subtitle):
    c.setFillColor(DEEP);c.rect(0,H-166,W,166,fill=1,stroke=0)
    c.setFillColor(TEAL);c.rect(43,H-49,28,3,fill=1,stroke=0)
    text(c,kicker.upper(),80,H-53,8.5,HexColor('#94D5D5'),FB)
    text(c,title,43,H-97,25.5,WHITE,FH)
    text(c,subtitle,44,H-121,10.1,HexColor('#BED0DF'))
    c.setStrokeColor(HexColor('#30475C'));c.line(43,H-145,W-43,H-145)
    text(c,'CS496  /  PROJECT 03',43,H-157,7.8,HexColor('#9BB6C8'),FB)
    c.setFont(F,7.8);c.drawRightString(W-43,H-157,'FALL 2026  •  MEDTECH')
    return H-192

def card_text(c,x,y,w,h,title,body,fill=MIST,accent=TEAL):
    rect(c,x,y-h,w,h,fill,10)
    c.setFillColor(accent);c.roundRect(x+14,y-29,4,15,2,fill=1,stroke=0)
    text(c,title,x+27,y-23,10.2,NAVY,FB)
    para(c,body,x+16,y-38,w-32,BODYSM)