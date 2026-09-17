"""Run in Fusion's execute_code. Checks topology, clearances and editability.
Parameter edits are always restored. Does not assert physical print fit.
"""
import adsk.core
import adsk.fusion
import json
import math
import os

ROOT = '/Users/kato-mahiro/Projects/personal/iphone-robot'
parts = [o for o in design.rootComponent.occurrences if o.component.name.startswith('Robot V1 - ')]
if len(parts) != 2:
    raise RuntimeError('Expected the two Robot V1 components')

def health():
    issues=[]
    for o in parts:
        c=o.component
        if c.bRepBodies.count != 1 or not c.bRepBodies.item(0).isSolid:
            issues.append({'component':c.name,'error':'Not one solid'})
        for f in c.features:
            if f.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
                issues.append({'component':c.name,'feature':f.name,'error':f.errorOrWarningMessage})
        for s in c.sketches:
            if not s.isFullyConstrained:
                issues.append({'component':c.name,'sketch':s.name,'error':'Underconstrained'})
    return issues

report={'baseline_issues':health(),'edit_checks':[],'interferences':[],'parts':[]}
for name,value in [('RB_EyeWidth','22 mm'),('RB_EyeY','33 mm'),('RB_BellyWidth','46 mm'),('RB_BellyY','-2 mm'),('RB_TalkDiameter','26 mm'),('RB_TalkY','-34 mm'),('RB_Clearance','0.5 mm'),('RB_Tilt','15 deg'),('RB_BaseDepth','95 mm'),('RB_BodyWidth','84 mm')]:
    p=design.userParameters.itemByName(name)
    previous=p.expression
    try:
        p.expression=value
        ok=design.computeAll()
        report['edit_checks'].append({'parameter':name,'test_value':value,'compute_ok':ok,'issues':health()})
    except Exception as e:
        report['edit_checks'].append({'parameter':name,'error':str(e)})
    finally:
        p.expression=previous
        design.computeAll()

entities=adsk.core.ObjectCollection.create()
for o in design.rootComponent.occurrences:
    if o.component.name.startswith(('Robot V1 - ','iPhone SE 3')):
        entities.add(o)
inp=design.createInterferenceInput(entities)
inp.areCoincidentFacesIncluded=False
results=design.analyzeInterference(inp)
for i in range(results.count):
    r=results.item(i)
    report['interferences'].append({'one':r.entityOne.name,'two':r.entityTwo.name,'volume_mm3':r.interferenceBody.volume*1000})

for o in parts:
    c=o.component
    b=c.bRepBodies.item(0)
    bb=b.preciseBoundingBox
    report['parts'].append({'component':c.name,'solid':b.isSolid,'volume_cm3':b.volume,'bounds_mm':{'min':[v*10 for v in (bb.minPoint.x,bb.minPoint.y,bb.minPoint.z)],'max':[v*10 for v in (bb.maxPoint.x,bb.maxPoint.y,bb.maxPoint.z)]},'sketches':c.sketches.count,'features':c.features.count})
report['limitations']=['Model-based collision check only; actual SE2 fit unverified','Cable, screws, nuts and pads are not modeled','STL support, stability, audio, thermal and screen alignment need physical testing','CAD material density is not calibrated to PLA or printer infill']
os.makedirs(ROOT+'/cad',exist_ok=True)
with open(ROOT+'/cad/robot-v1-validation.json','w') as f:
    json.dump(report,f,ensure_ascii=False,indent=2)
result=report
