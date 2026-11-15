"""Run: python3 scripts/validate_pack.py from the extracted kit. Standard library only."""
from pathlib import Path
import json,csv,hashlib,sys
from collections import Counter
from datetime import datetime
from assessment_reference import threshold,current_result,on_time,rate,readiness
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads((R/p).read_text(encoding='utf-8'))
checks=0
def require(v,msg):
    global checks
    assert v,msg
    checks+=1

lessons=read('data/public/lessons.json');questions=read('data/public/questions.json');keys=read('data/private/theory_answer_key.json')
course=read('data/public/course.json');assets=read('data/asset_manifest.json');bp=read('data/assessment_blueprint.json')
require(len(lessons)==12 and sum(l['minutes'] for l in lessons)==90,'Lessons/time')
require(len(questions)==60 and len(keys)==60,'Question/key count')
require(len({q['id'] for q in questions})==60,'Duplicate questions')
require(len({k['question_id'] for k in keys})==60,'Duplicate answer keys')
qm={q['id']:q for q in questions};km={k['question_id']:k for k in keys};am={a['id']:a for a in assets}
require(qm.keys()==km.keys(),'Question/key mapping')
for q in questions:
    require(len(q['options'])==4 and len({o['id'] for o in q['options']})==4,q['id']+' options')
    require(km[q['id']]['correct_option_id'] in {o['id'] for o in q['options']},q['id']+' key')
    require(not any(k in q for k in ['correct_option_id','explanation_vi','answer']),q['id']+' private leak')
counts=Counter(q['pool'] for q in questions)
require(len(counts)==12,'Pool count')
require(sum(p['draw'] for p in bp['theory']['pools'])==20,'Exam draw')
require(sum(p['draw'] for p in bp['theory']['pools'] if p['critical'])==4,'Critical draw')
for p in bp['theory']['pools']:require(counts[p['pool']] >= p['draw'],p['pool']+' insufficient')
for l in lessons:
    require(len(l['cards'])==4,l['id']+' card count')
    require(all(a in am for a in l['asset_ids']),l['id']+' asset ref')
    require(all(q in qm for q in l['knowledge_check_ids']) and l['knowledge_check_ids'],l['id']+' checks')
for a in assets:require((R/a['path']).is_file(),a['id']+' missing asset')
require(len(assets)==30,'Asset count')
sims=read('data/public/simulations.json');sk=read('data/private/simulation_grading.json')
require(len(sims)==12 and sum(s['assessed'] for s in sims)==10,'Simulation count')
require({s['id'] for s in sims}=={s['case_id'] for s in sk},'Simulation key mapping')
require(len(next(s for s in sims if s['id']=='SIM01')['context']['count_tokens'])==18,'Exact count tokens')
require(next(k for k in sk if k['case_id']=='SIM03')['semantic_rules']['accept_any_valid_batch_partition'],'SIM03 partition')
rub=read('data/hardware_rubrics.json')
require(len(rub['common'])==20 and sum(c['points'] for c in rub['common'])==100,'Hardware rubric')
require(len(rub['special']['A2_PC'])==10 and len(rub['special']['CONTROLLER'])==6,'Special rubrics')
require(set(c['station'] for c in rub['common'])=={'S1','S2','S3','S4','S5'},'Hardware stations')
sch=read('data/schedule.json');sh=read('data/shift_calendar.json');calendar={d['date']:d['crews'] for d in sh['days']}
deadline=datetime.fromisoformat(course['hard_deadline_exclusive'])
require(len(sch['sessions'])==39,'39 sessions')
require(sum(x['minutes'] for x in sch['practice_agenda'])==180,'Practice agenda')
require(len({s['id'] for s in sch['sessions']})==39,'Duplicate sessions')
for s in sch['sessions']:
    start,end=map(datetime.fromisoformat,[s['start_at'],s['end_at']])
    require(start<end<deadline,s['id']+' date/deadline')
    if s['kind']=='main':require(calendar[s['start_at'][:10]][s['crew']]=='DAY',s['id']+' not Day')
    require(s['timezone']=='Asia/Ho_Chi_Minh',s['id']+' timezone')
slots=list(csv.DictReader((R/'templates/planned_slots_132.csv').open(encoding='utf-8-sig')))
require(len(slots)==132,'Slot count')
require(Counter(s['job_title'] for s in slots)=={'LINE_LEADER':72,'GROUP_LEADER':30,'FEEDER':30},'Role counts')
require(all(s['is_placeholder']=='true' and s['active']=='false' and not s['employee_id'] and not s['crew'] for s in slots),'Placeholder cannot be live')
for t in read('tests/golden_cases.json'):
    kind=t['kind']
    if kind=='threshold':got=threshold(t['type'],t['score'],t['critical_failed'],t.get('missing_observations',0))
    elif kind=='current_result':got=current_result(t['attempts'])
    elif kind=='deadline':got=on_time(t['submitted_at'])
    elif kind=='dashboard':got=rate(t['real_required'],t['qualified'])
    elif kind=='readiness':got=readiness(t)
    else:raise AssertionError(kind)
    require(got==t['expected'],t['id']+' golden failure')
manifest=R/'PACKAGE_MANIFEST.json'
if manifest.exists():
    for f in read('PACKAGE_MANIFEST.json')['files']:
        require(hashlib.sha256((R/f['path']).read_bytes()).hexdigest()==f['sha256'],'Hash '+f['path'])
print(f'PASS: {checks} content/policy/manifest checks; 60 questions, 12 lessons, 12 cases, 39 sessions, 132 placeholders.')
print('These checks validate the kit, not a deployed app or real PDA certification.')
