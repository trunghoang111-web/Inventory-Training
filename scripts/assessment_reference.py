"""Reference for policy edge cases, NOT a production auth/grading service.
Antigravity must test its own server/API, using these as golden fixtures.
"""
from datetime import datetime

def threshold(kind, score, critical_failed, missing_observations=0):
    limits={'THEORY':90,'SIMULATION':90,'HARDWARE_COMMON':90,'A2_PC':45,'CONTROLLER':25}
    maximums={'THEORY':100,'SIMULATION':100,'HARDWARE_COMMON':100,'A2_PC':50,'CONTROLLER':30}
    return 0 <= score <= maximums[kind] and score >= limits[kind] and not critical_failed and missing_observations == 0

def current_result(attempts):
    # Input chronological, already filtered to same person/type/current version.
    official=[a for a in attempts if a['official'] and a['state']!='VOIDED']
    if any(a['state'] in ('CREATED','IN_PROGRESS','SUBMITTED') for a in official):return 'PENDING'
    graded=[a for a in official if a['state']=='GRADED']
    return ('PASS' if graded[-1]['passed'] else 'FAIL') if graded else 'PENDING'

def on_time(iso):return datetime.fromisoformat(iso) < datetime.fromisoformat('2026-12-01T00:00:00+07:00')
def rate(real_required,qualified):return qualified/real_required if real_required else None
def readiness(d):return all(d[k] for k in ['lessons','attendance','theory','simulation','hardware','special','current_version','signature'])
