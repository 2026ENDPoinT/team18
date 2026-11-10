"""Render deterministic synthetic PNGs and freeze references BEFORE inference."""
import argparse, hashlib, json, shutil, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, x): p.write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')
FONTS = ['NanumGothic-Regular.ttf', 'NanumMyeongjo-Regular.ttf']
COLORS = ['#165b70','#3a477c','#755235','#386352','#713b66','#4d5461']

class Canvas:
    def __init__(self, sid, size, font, color, bg='white'):
        self.sid=sid; self.im=Image.new('RGB', size, bg); self.d=ImageDraw.Draw(self.im)
        self.font=font; self.color=color; self.lines=[]; self.boxes=[]; self.regions=[]
        self.cmap=TTFont(BASE/'sources/fonts'/font).getBestCmap()
    def text(self, x,y,s,size=32,fill='#172130'):
        missing=[c for c in s if not c.isspace() and ord(c) not in self.cmap]
        assert not missing,(self.sid,missing)
        f=ImageFont.truetype(str(BASE/'sources/fonts'/self.font),size)
        box=self.d.textbbox((x,y),s,font=f)
        assert 15 <= box[0] < box[2] <= self.im.width-15 and 15 <= box[1] < box[3] <= self.im.height-15,(self.sid,s,box)
        for old in self.boxes:
            a=old['bbox']; overlap=min(a[2],box[2])-max(a[0],box[0])>0 and min(a[3],box[3])-max(a[1],box[1])>0
            assert not overlap, (self.sid,'text overlap',s,old)
        self.d.text((x,y),s,font=f,fill=fill)
        self.lines.append(s); self.boxes.append({'text':s,'bbox':box,'font_size_px':size})
        return y+int(size*1.55)
    def block(self,x,y,s,width,size=32,fill='#172130'):
        f=ImageFont.truetype(str(BASE/'sources/fonts'/self.font),size)
        words=s.split(' '); lines=[]; line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if f.getlength(candidate)<=width: line=candidate
            else:
                assert line,('word too long',word)
                lines.append(line);line=word
        if line:lines.append(line)
        for line in lines:y=self.text(x,y,line,size,fill)
        return y
    def region(self,name,start): self.regions.append({'name':name,'line_start':start+1,'line_end':len(self.lines)})
    def line(self, coords, fill=None, width=2):self.d.line(coords,fill=fill or self.color,width=width)
    def finish(self):
        ip=BASE/'images'/f'{self.sid}.png'; gp=BASE/'ground_truth'/f'{self.sid}.txt'
        self.im.save(ip);gp.write_text(unicodedata.normalize('NFC','\n'.join(self.lines)),encoding='utf-8')
        save(BASE/'ground_truth'/f'{self.sid}.reading_order.json',{'rule':'ordered visible lines; no final LF','regions':self.regions,'lines':self.boxes})
        return {'image':str(ip.relative_to(BASE)),'ground_truth':str(gp.relative_to(BASE)),'reading_order':f'ground_truth/{self.sid}.reading_order.json','width':self.im.width,'height':self.im.height,'font':self.font,'color':self.color}

def metric_text(p):return f"{p['metric']} {p['before']}{p['unit']} → {p['after']}{p['unit']}"
def fact_data(p,layout):
    tech=p['tech'] if layout!='slide_results' else []
    roles=[] if layout=='slide_results' else [
        {'id':'role_team','owner':'team','action':p['team_action'],'statement':'팀은 '+p['team']+'.'},
        {'id':'role_self','owner':'self','action':p['self_action'],'statement':'나는 '+p['self']+'.'}]
    for f in roles:
        f['presentation']='heading_scope' if layout=='slide_compare' else 'explicit_subject'
        f['header']='팀 전체 구현' if f['owner']=='team' else '내가 맡은 역할'
    metrics=[] if layout=='slide_compare' else [{'id':'metric_main','name':p['metric'],'before':p['before'],'after':p['after'],'unit':p['unit'],'direction':p['direction'],'statement':metric_text(p)}]
    return {'project_id':p['id'],'technology':[{'id':f'tech_{i+1}','name':t} for i,t in enumerate(tech)],'roles':roles,'metrics':metrics,'scope':'primary declared contribution facts; not every ancillary narrative activity is a separate item'}

def intro(p,i):
    sid=p['id']+'_intro';layout='intro_prose' if i<6 else 'intro_bullets';font=FONTS[(i//2)%2]
    c=Canvas(sid,(1240,1754),font,COLORS[i%6], '#fffefa' if font==FONTS[1] else 'white')
    x=85 if i%2 else 100;w=1240-2*x
    y=c.block(x,75,p['title'],w,50,c.color)
    y=c.text(x,y+10,p['domain']+' 프로젝트 소개서',28,c.color)
    y=c.text(x,y+16,p['student']+' · '+p['period'],26)
    c.line((x,y+10,1240-x,y+10));y+=48
    start=0;c.region('title and author',start)
    start=len(c.lines)
    if layout=='intro_prose':
        paras=[p['problem'], '사용한 기술은 '+', '.join(p['tech'])+'이다.',
               '팀은 '+p['team']+'. 나는 '+p['self']+'.', p['method'],
               '검증 결과, '+metric_text(p)+'로 '+p['direction']+'했다. '+p['scope']+' 조건이다.',p['extra'],p['limit']]
        # Two prose compositions: titled opening vs a continuous essay.
        if i%2:y=c.text(x,y,'개발 배경과 기여',33,c.color)+12
        for para in paras:y=c.block(x,y,para,w,30 if i%2 else 31)+24
    else:
        sections=[('문제와 사용자',[p['problem']]),('구현 기술',[', '.join(p['tech'])]),
                  ('역할과 구현',['팀은 '+p['team']+'.','나는 '+p['self']+'.',p['method']]),
                  ('실험 결과',[metric_text(p)+'로 '+p['direction'],p['scope']]),('다음 단계',[p['limit']])]
        for h,items in sections:
            y=c.text(x,y,h,34,c.color)+9
            for s in items:y=c.block(x+12,y,'• '+s,w-12,29)+9
            y+=18
    assert y<1665,(sid,y)
    c.region('body top to bottom',start);c.text(x,1680,'합성 학생 프로젝트 · '+p['id'].upper(),22,'#59636e')
    return c,layout

def bullet(p,i):
    c=Canvas(p['id']+'_slide_bullets',(1600,900),FONTS[i%2],COLORS[i%6], '#f5f8fb' if i%3==1 else 'white')
    c.text(80,55,p['title'],56,c.color)
    c.text(82,137,p['domain']+' · 구현과 검증',29)
    c.line((80,196,1520,196),width=3);c.region('title',0)
    y=235;start=len(c.lines)
    texts=[('문제',p['problem'].split('. ')[0]+'.'),('기술',', '.join(p['tech'])),
           ('팀 기여','팀은 '+p['team']+'.'),('본인 기여','나는 '+p['self']+'.'),('결과',metric_text(p)+'로 '+p['direction'])]
    for label,txt in texts:
        if i%2:
            c.text(85,y,label,31,c.color);y=c.block(295,y,txt,1210,35)+22
        else:y=c.block(90,y,'• '+txt,1410,36)+24
    c.region('bullets top to bottom',start)
    c.block(85,824,p['student']+' · '+p['scope'],1420,23,'#59636e')
    return c,'slide_bullets'

def compare(p,i):
    c=Canvas(p['id']+'_slide_compare',(1600,900),FONTS[(i+1)%2],COLORS[i%6])
    c.text(75,55,p['title']+' / 역할 분담',53,c.color)
    c.text(78,139,', '.join(p['tech']),30)
    c.line((800,220,800,755),fill='#a5afb7',width=2);c.region('page title and technology',0)
    # Deliberate intended column-major order, fixed independently of OCR row sorting.
    start=len(c.lines);c.text(85,230,'팀 전체 구현',42,c.color)
    c.block(85,332,p['team'],625,37)
    c.block(85,520,p['extra'],625,30)
    c.region('left heading then left content',start)
    start=len(c.lines);c.text(875,230,'내가 맡은 역할',42,c.color)
    c.block(875,332,p['self'],630,37)
    c.block(875,520,'담당자: '+p['student'],630,30)
    c.block(875,600,'구현 범위는 위 항목으로 구분했다.',630,30)
    c.region('right heading then right content',start)
    start=len(c.lines);c.text(80,820,p['period']+' · 역할 분담 기록',24,'#59636e');c.region('footer',start)
    return c,'slide_compare'

def result(p,i):
    c=Canvas(p['id']+'_slide_results',(1600,900),FONTS[i%2],COLORS[i%6], '#fffefa' if i%2 else 'white')
    c.text(75,54,p['title']+' / 결과',54,c.color)
    c.text(78,140,'시험 조건과 관찰 결과',30);c.region('title',0)
    start=len(c.lines)
    # The left evidence area varies between a bar plot and a rendered synthetic UI crop.
    if p['visual']=='screen':
        c.d.rectangle((75,228,820,710),fill='#eef2f5',outline='#9eacb8',width=2)
        c.d.rectangle((75,228,820,285),fill=c.color)
        c.text(100,239,'테스트 기록',28,'white')
        c.text(105,315,p['metric'],32)
        c.text(110,398,'개선 전',30);c.text(440,398,p['before']+p['unit'],42,c.color)
        c.line((105,465,785,465),fill='#c3cbd2')
        c.text(110,505,'개선 후',30);c.text(440,505,p['after']+p['unit'],42,c.color)
        c.text(108,625,'상태: 비교 완료',27)
        c.text(80,735,'합성 앱 화면 · 표시된 시험값만 비교',23,'#59636e')
    elif i%2==0:
        c.text(95,235,p['metric'],32,c.color)
        vmax=max(float(p['before']),float(p['after']))*1.2
        for j,(label,v) in enumerate([('개선 전',p['before']),('개선 후',p['after'])]):
            y=350+j*180;c.text(95,y,label,28)
            length=float(v)/vmax*450
            c.d.rectangle((245,y,245+length,y+65),fill='#a9b6c5' if j==0 else c.color)
            c.text(255+length,y+10,v+p['unit'],29)
        c.text(95,727,'막대 길이는 같은 척도로 표시',23,'#59636e')
    else:
        c.text(95,232,p['metric'],32,c.color)
        c.line((125,695,815,695),fill='#7f8993')
        vmax=max(float(p['before']),float(p['after']))*1.2
        for j,(label,v) in enumerate([('개선 전',p['before']),('개선 후',p['after'])]):
            x=240+j*330;h=float(v)/vmax*310
            c.d.rectangle((x,695-h,x+125,695),fill='#a9b6c5' if j==0 else c.color)
            c.text(x-12,695-h-55,v+p['unit'],31)
            c.text(x+2,718,label,27)
    c.region('left chart or synthetic screen: title then before label/value then after label/value then caption',start)
    start=len(c.lines)
    y=c.block(930,240,metric_text(p),580,38,c.color)+28
    y=c.block(930,y,p['direction']+'한 결과를 확인했다.',580,34)+28
    y=c.block(930,y,'측정 조건: '+p['scope'],580,30)+28
    y=c.block(930,y,p['limit'],580,29)
    assert y<790,(c.sid,y)
    c.region('right explanatory text top to bottom',start)
    start=len(c.lines);c.text(80,830,p['student']+' · 합성 실험 결과',23,'#59636e');c.region('footer',start)
    return c,'slide_results'

def prepare():
    assert not (BASE/'manifest.json').exists(),'Already frozen; do not alter inputs.'
    assert not (BASE/'results').exists(),'Results exist.'
    for name in ['images','ground_truth','key_facts','qa']:(BASE/name).mkdir(exist_ok=True)
    samples=[];checks=[]
    for i,p in enumerate(json.loads((BASE/'sources/projects.json').read_text())):
        pages=[intro(p,i)]
        pages += [bullet(p,i),compare(p,i)] if i<4 else ([bullet(p,i),result(p,i)] if i<8 else [compare(p,i),result(p,i)])
        for c,layout in pages:
            fields=c.finish();facts=fact_data(p,layout);save(BASE/'key_facts'/f'{c.sid}.json',facts)
            sample={'id':c.sid,'project_id':p['id'],'original_id':p['id'],'kind':'synthetic','variant':'base','layout':layout,'format':'introduction' if layout.startswith('intro') else 'slide','facts':f'key_facts/{c.sid}.json',**fields}
            samples.append(sample);checks.append({'id':c.sid,'missing_glyphs':[],'text_clipping':False,'text_overlap':False,'text_boxes':c.boxes})
    save(BASE/'qa/draft_manifest.json',samples);save(BASE/'qa/render_checks.json',checks)
    # Contact sheets are QA only and NEVER OCR inputs; original full-size images remain unchanged.
    for group in range(6):
        subset=samples[group*6:(group+1)*6];montage=Image.new('RGB',(1500,1550),'#d4d9df');d=ImageDraw.Draw(montage)
        for j,s in enumerate(subset):
            im=Image.open(BASE/s['image']);im.thumbnail((735,475))
            x=(j%2)*750+(750-im.width)//2;y=(j//2)*510+30
            montage.paste(im,(x,y));d.text(((j%2)*750+15,(j//2)*510+5),s['id'],fill='black')
        montage.save(BASE/'qa'/f'contact_{group+1}.png')
    print('Prepared 12 independent projects / 36 pages; not frozen')

def freeze():
    assert not (BASE/'manifest.json').exists()
    review=json.loads((BASE/'qa/visual_review.json').read_text());assert review['review_completed_before_ocr']
    samples=json.loads((BASE/'qa/draft_manifest.json').read_text());assert len(samples)==36
    for s in samples:
        for key in ['image','ground_truth','facts','reading_order']:s[key+'_sha256']=sha(BASE/s[key])
    files=['protocol.md','prepare.py','evaluate.py','score_facts.py','verify_metrics.py','sources/projects.json','qa/render_checks.json','qa/visual_review.json']
    files += [str(p.relative_to(BASE)) for p in (BASE/'sources/fonts').glob('*')]
    save(BASE/'manifest.json',{'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'independent_projects':12,'evaluation_pages':36,'tracked_assets':{f:sha(BASE/f) for f in files},'samples':samples})
    print('Frozen image, reference, reading-order, key facts, rubric and evaluator hashes.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');a=p.parse_args()
    freeze() if a.freeze else prepare()
