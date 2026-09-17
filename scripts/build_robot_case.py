"""Editable Fusion 360 robot enclosure, two printed parts (white PLA).
Run inside fusion360_execute_code with app, design and adsk available.
Only components prefixed 'Robot V1 - ' are rebuilt. The phone is untouched.
All dimensions are mm; Fusion geometry is cm. See docs/robot-case-v1.md.
"""
import adsk.core
import adsk.fusion
import math
import json
import os

ROOT = '/Users/kato-mahiro/Projects/personal/iphone-robot'
root = design.rootComponent
um = design.unitsManager
V = adsk.core.ValueInput.createByString
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation
JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
HORIZ = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
VERT = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation

if not design.userParameters.itemByName('SE3_OverallWidth'):
    raise RuntimeError('Open the existing parametric iPhone reference first.')
os.makedirs(ROOT + '/cad', exist_ok=True)
backup = ROOT + '/cad/phone-robot-before-case.f3d'
if not os.path.exists(backup):
    design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(backup))

for i in range(root.occurrences.count - 1, -1, -1):
    o = root.occurrences.item(i)
    if o.component.name.startswith('Robot V1 - '):
        o.deleteMe()

# User-facing parameters. Negative window positions use signed expressions;
# keep their sign when editing dimensions, or move the sketch across the origin.
PARAMS = [
    ('RB_Clearance', '0.4 mm', 'Phone clearance PER SIDE; test-print before final use'),
    ('RB_BackGap', '0.5 mm', 'Allowance for thin pads between rear glass and tray'),
    ('RB_FrontGap', '0.4 mm', 'Clearance above front glass, excluding screen protector'),
    ('RB_Wall', '2.4 mm', 'Tray side walls'),
    ('RB_BackThickness', '2.4 mm', 'Tray back plate'),
    ('RB_CoverThickness', '2.4 mm', 'Front cover plate'),
    ('RB_HeadWidth', '92 mm', 'Head width, excluding no separate ears'),
    ('RB_BodyWidth', '82 mm', 'Body widened from concept to fit lower M3 screws'),
    ('RB_CaseHeight', '148 mm', 'Cover total height in phone coordinates'),
    ('RB_HeadHeight', '60 mm', 'Top rounded box height'),
    ('RB_BodyHeight', '96 mm', 'Bottom rounded box height; overlaps head'),
    ('RB_OuterRadius', '6 mm', 'Rounded external corners'),
    ('RB_EyeWidth', '20 mm', 'Each eye aperture width'),
    ('RB_EyeHeight', '22 mm', 'Each eye aperture height'),
    ('RB_EyeRadius', '8 mm', 'Eye corner radius, <= half the smaller dimension'),
    ('RB_EyeX', '14 mm', 'Half of eye center spacing'),
    ('RB_EyeY', '31 mm', 'Eye centers above phone center'),
    ('RB_BellyWidth', '48 mm', 'Message window width'),
    ('RB_BellyHeight', '28 mm', 'Message window height'),
    ('RB_BellyRadius', '3 mm', 'Message window corner radius'),
    ('RB_BellyY', '-3 mm', 'Message window center Y'),
    ('RB_TalkDiameter', '24 mm', 'Touch aperture at the screen side'),
    ('RB_TalkY', '-35 mm', 'Touch aperture center Y'),
    ('RB_TouchBevel', '1 mm', '45 degree entry bevel; remaining lip is 1.4 mm'),
    ('RB_HomeDiameter', '14 mm', 'Maintenance access, NOT the conversation button'),
    ('RB_ForeheadWidth', '26 mm', 'Camera, receiver, sensors shared forehead opening'),
    ('RB_ForeheadHeight', '12 mm', 'Forehead opening; validate camera field of view'),
    ('RB_ForeheadX', '-3.5 mm', 'Forehead opening center X'),
    ('RB_ForeheadY', '62 mm', 'Forehead opening center Y'),
    ('RB_MouthWidth', '24 mm', 'Decorative mouth groove width'),
    ('RB_MouthHeight', '1.2 mm', 'Decorative mouth groove height'),
    ('RB_MouthY', '15.5 mm', 'Decorative mouth center Y'),
    ('RB_MouthDepth', '0.6 mm', 'Blind groove only, no display opening'),
    ('RB_ScrewDiameter', '3.4 mm', 'Through clearance for four M3 bolts and loose nuts'),
    ('RB_TopScrewX', '40 mm', 'Top screw centers +/- X'),
    ('RB_TopScrewY', '62 mm', 'Top screw centers Y'),
    ('RB_BottomScrewX', '37 mm', 'Bottom screw centers +/- X'),
    ('RB_BottomScrewY', '-62 mm', 'Bottom screw centers Y'),
    ('RB_Tilt', '12 deg', 'Phone tilt back from vertical on its base'),
    ('RB_Lift', '35 mm', 'Desk to phone lower rear edge; check actual cable'),
    ('RB_BaseWidth', '100 mm', 'Base left-right width'),
    ('RB_BaseDepth', '90 mm', 'Base front-back distance along desk'),
    ('RB_BaseFront', '20 mm', 'Base reach along desk from its phone-Z=0 intercept'),
    ('RB_BaseThickness', '4 mm', 'Base thickness normal to desk'),
    ('RB_RibThickness', '4 mm', 'Two rear triangular stand ribs'),
    ('RB_RibX', '29 mm', 'Stand rib center X +/-'),
    ('RB_CableWidth', '16 mm', 'Open-ended cable channel in base'),
    ('RB_BottomOpening', '54 mm', 'Bottom opening clears Lightning and both acoustic rows'),
    ('RB_VentWidth', '40 mm', 'Rear ventilation / finger access width'),
    ('RB_VentHeight', '62 mm', 'Rear ventilation / finger access height'),
    ('RB_RearCameraWidth', '26 mm', 'Rear camera, microphone and flash opening'),
    ('RB_RearCameraHeight', '18 mm', 'Rear camera opening height'),
    ('RB_PocketWidth', 'SE3_OverallWidth+2*RB_Clearance', 'Derived phone pocket width'),
    ('RB_PocketHeight', 'SE3_OverallHeight+2*RB_Clearance', 'Derived phone pocket height'),
    ('RB_PocketRadius', 'SE3_CornerRadius+RB_Clearance', 'Derived approximate pocket corner radius'),
    ('RB_TrayWidth', 'RB_PocketWidth+2*RB_Wall', 'Derived outer tray width'),
    ('RB_TrayHeight', 'RB_PocketHeight+2*RB_Wall', 'Derived outer tray height'),
    ('RB_BackZ', '-RB_BackGap-RB_BackThickness', 'Rear-most tray plane'),
    ('RB_CoverZ', 'SE3_ProductThickness+RB_FrontGap', 'Cover rear face / tray mating plane'),
    ('RB_CoverTopZ', 'RB_CoverZ+RB_CoverThickness', 'Cover front face'),
    ('RB_DeskY', '-SE3_OverallHeight/2-RB_Lift/cos(RB_Tilt)', 'Desk-plane Y intercept at phone Z=0'),
]
for name, expr, comment in PARAMS:
    p = design.userParameters.itemByName(name)
    if p:
        # Rebuild preserves edited user parameters rather than resetting them.
        continue
    design.userParameters.add(name, V(expr), 'deg' if name == 'RB_Tilt' else 'mm', comment)
# The rib top is deliberately aligned to the phone center, not an editable offset.
legacy_rib_top = design.userParameters.itemByName('RB_RibTopY')
if legacy_rib_top:
    legacy_rib_top.deleteMe()


def ev(expr):
    return um.evaluateExpression(str(expr), 'mm')  # cm


def pt(x, y):
    return adsk.core.Point3D.create(x, y, 0)


def distance(s, a, b, orientation, expr, x, y):
    d = s.sketchDimensions.addDistanceDimension(a, b, orientation, pt(x, y))
    d.parameter.expression = expr
    return d


def locate(s, p, xe, ye):
    x, y = ev(xe), ev(ye)
    if abs(x) < 1e-8:
        s.geometricConstraints.addVerticalPoints(s.originPoint, p)
    else:
        distance(s, s.originPoint, p, HORIZ, f'abs({xe})', x/2, y+0.4)
    if abs(y) < 1e-8:
        s.geometricConstraints.addHorizontalPoints(s.originPoint, p)
    else:
        distance(s, s.originPoint, p, VERT, f'abs({ye})', x+0.4, y/2)


def plane(c, base, expr, name):
    inp = c.constructionPlanes.createInput()
    inp.setByOffset(base, V(expr))
    p = c.constructionPlanes.add(inp)
    p.name = name
    p.isLightBulbOn = False
    return p


def rounded(c, pl, wexpr, hexpr, rexpr, xexpr, yexpr, name):
    s = c.sketches.add(pl)
    s.name = name
    w,h,r,x,y = [ev(e) for e in (wexpr,hexpr,rexpr,xexpr,yexpr)]
    if r <= 0 or r*2 >= min(w,h):
        raise ValueError('Rounded rectangle radius must be positive and < half size: '+name)
    arcs, lines, gc = s.sketchCurves.sketchArcs, s.sketchCurves.sketchLines, s.geometricConstraints
    tr = arcs.addByCenterStartSweep(pt(x+w/2-r,y+h/2-r),pt(x+w/2,y+h/2-r),math.pi/2)
    br = arcs.addByCenterStartSweep(pt(x+w/2-r,y-h/2+r),pt(x+w/2-r,y-h/2),math.pi/2)
    bl = arcs.addByCenterStartSweep(pt(x-w/2+r,y-h/2+r),pt(x-w/2,y-h/2+r),math.pi/2)
    tl = arcs.addByCenterStartSweep(pt(x-w/2+r,y+h/2-r),pt(x-w/2+r,y+h/2),math.pi/2)
    top = lines.addByTwoPoints(tl.startSketchPoint,tr.endSketchPoint)
    right = lines.addByTwoPoints(tr.startSketchPoint,br.endSketchPoint)
    bottom = lines.addByTwoPoints(br.startSketchPoint,bl.endSketchPoint)
    left = lines.addByTwoPoints(bl.startSketchPoint,tl.endSketchPoint)
    gc.addHorizontal(top); gc.addHorizontal(bottom)
    gc.addVertical(left); gc.addVertical(right)
    for ln, arc in ((top,tr),(right,tr),(right,br),(bottom,br),(bottom,bl),(left,bl),(left,tl),(top,tl)):
        gc.addTangent(ln,arc)
    for arc in (br,bl,tl):
        gc.addEqual(tr,arc)
    distance(s, top.startSketchPoint,top.endSketchPoint,HORIZ,f'({wexpr})-2*({rexpr})',x,y+h/2+0.3)
    distance(s,right.startSketchPoint,right.endSketchPoint,VERT,f'({hexpr})-2*({rexpr})',x+w/2+0.3,y)
    rd = s.sketchDimensions.addRadialDimension(tr,pt(x+w/2+0.3,y+h/2))
    rd.parameter.expression = rexpr
    diagonal = lines.addByTwoPoints(tr.centerSketchPoint,bl.centerSketchPoint)
    diagonal.isConstruction = True
    center = s.sketchPoints.add(pt(x,y))
    gc.addMidPoint(center,diagonal)
    locate(s,center,xexpr,yexpr)
    s.isLightBulbOn = False
    return s


def rectangle(c, pl, we, he, xe, ye, name):
    s = c.sketches.add(pl); s.name = name
    w,h,x,y = [ev(e) for e in (we,he,xe,ye)]
    ls = s.sketchCurves.sketchLines.addCenterPointRectangle(pt(x,y),pt(x+w/2,y+h/2))
    # The API creates rectangle geometry without horizontal/vertical constraints.
    for ln in ls:
        if abs(ln.startSketchPoint.geometry.y-ln.endSketchPoint.geometry.y)<1e-7:
            s.geometricConstraints.addHorizontal(ln)
        else:
            s.geometricConstraints.addVertical(ln)
    # Locate the center using a construction diagonal and its midpoint.
    diag=s.sketchCurves.sketchLines.addByTwoPoints(ls.item(0).startSketchPoint,ls.item(2).startSketchPoint)
    diag.isConstruction=True
    cp=s.sketchPoints.add(pt(x,y))
    s.geometricConstraints.addMidPoint(cp,diag)
    locate(s,cp,xe,ye)
    horizontal = next(ln for ln in ls if abs(ln.startSketchPoint.geometry.y-ln.endSketchPoint.geometry.y)<1e-7)
    vertical = next(ln for ln in ls if abs(ln.startSketchPoint.geometry.x-ln.endSketchPoint.geometry.x)<1e-7)
    distance(s,horizontal.startSketchPoint,horizontal.endSketchPoint,HORIZ,we,x,y+h/2+0.3)
    distance(s,vertical.startSketchPoint,vertical.endSketchPoint,VERT,he,x+w/2+0.3,y)
    s.isLightBulbOn=False
    return s


def circle(c, pl, de, xe, ye, name):
    s=c.sketches.add(pl); s.name=name
    x,y=ev(xe),ev(ye)
    ci=s.sketchCurves.sketchCircles.addByCenterRadius(pt(x,y),ev(de)/2)
    locate(s,ci.centerSketchPoint,xe,ye)
    d=s.sketchDimensions.addDiameterDimension(ci,pt(x+ev(de),y))
    d.parameter.expression=de
    s.isLightBulbOn=False
    return s


def polygon(c, pl, coords, name):
    s=c.sketches.add(pl); s.name=name
    points=[pt(ev(x),ev(y)) for x,y in coords]
    ls=s.sketchCurves.sketchLines
    first=ls.addByTwoPoints(points[0],points[1]); vertices=[first.startSketchPoint,first.endSketchPoint]
    previous=first
    for p in points[2:]:
        previous=ls.addByTwoPoints(previous.endSketchPoint,p)
        vertices.append(previous.endSketchPoint)
    ls.addByTwoPoints(previous.endSketchPoint,first.startSketchPoint)
    # Fusion can infer vertical/horizontal constraints while adding the edges.
    # Each vertex is explicitly dimensioned below, so remove inferred directions.
    for i in range(s.geometricConstraints.count-1,-1,-1):
        constraint=s.geometricConstraints.item(i)
        if constraint.objectType != adsk.fusion.CoincidentConstraint.classType():
            constraint.deleteMe()
    x_refs, y_refs = {}, {}
    for vertex,(xe,ye) in zip(vertices,coords):
        x,y=ev(xe),ev(ye)
        if xe in x_refs:
            s.geometricConstraints.addVerticalPoints(x_refs[xe],vertex)
        elif abs(x)<1e-8:
            s.geometricConstraints.addVerticalPoints(s.originPoint,vertex)
        else:
            distance(s,s.originPoint,vertex,HORIZ,f'abs({xe})',x/2,y+0.4)
        x_refs[xe]=vertex
        if ye in y_refs:
            s.geometricConstraints.addHorizontalPoints(y_refs[ye],vertex)
        elif abs(y)<1e-8:
            s.geometricConstraints.addHorizontalPoints(s.originPoint,vertex)
        else:
            distance(s,s.originPoint,vertex,VERT,f'abs({ye})',x+0.4,y/2)
        y_refs[ye]=vertex
    s.isLightBulbOn=False
    return s


def extrude(c,s,expr,name,op=NEW):
    if s.profiles.count != 1:
        raise RuntimeError(f'{s.name}: expected one profile, got {s.profiles.count}')
    inp=c.features.extrudeFeatures.createInput(s.profiles.item(0),op)
    inp.setDistanceExtent(False,V(expr))
    if op == CUT:
        inp.participantBodies = [c.bRepBodies.item(i) for i in range(c.bRepBodies.count)]
    f=c.features.extrudeFeatures.add(inp); f.name=name
    return f


def silhouette(c,pl,depth,prefix):
    s=rounded(c,pl,'RB_HeadWidth','RB_HeadHeight','RB_OuterRadius','0 mm','RB_CaseHeight/2-RB_HeadHeight/2',prefix+'01 Head outline')
    extrude(c,s,depth,prefix+'01 Head plate')
    s=rounded(c,pl,'RB_BodyWidth','RB_BodyHeight','RB_OuterRadius','0 mm','-RB_CaseHeight/2+RB_BodyHeight/2',prefix+'02 Body outline')
    extrude(c,s,depth,prefix+'02 Body plate',JOIN)


def new_component(name):
    occ=root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name=name
    return occ,occ.component

holder_occ,holder=new_component('Robot V1 - A Holder and Stand')
back=plane(holder,holder.xYConstructionPlane,'RB_BackZ','A PL01 Back of tray')
floor=plane(holder,holder.xYConstructionPlane,'-RB_BackGap','A PL02 Pocket floor')
mate=plane(holder,holder.xYConstructionPlane,'RB_CoverZ','A PL03 Cover mating surface')
silhouette(holder,back,'RB_BackThickness','A ')
s=rounded(holder,floor,'RB_TrayWidth','RB_TrayHeight','RB_PocketRadius+RB_Wall','0 mm','0 mm','A03 Tray outer perimeter')
extrude(holder,s,'RB_CoverZ+RB_BackGap','A03 Tray wall blank',JOIN)
# Four screw pads; bottom pads will be trimmed by the phone pocket.
for tag,xe,ye,de in [('TL','-RB_TopScrewX','RB_TopScrewY','10 mm'),('TR','RB_TopScrewX','RB_TopScrewY','10 mm'),('BL','-RB_BottomScrewX','RB_BottomScrewY','8 mm'),('BR','RB_BottomScrewX','RB_BottomScrewY','8 mm')]:
    s=circle(holder,floor,de,xe,ye,'A04 '+tag+' screw pad')
    extrude(holder,s,'RB_CoverZ+RB_BackGap','A04 '+tag+' pad',JOIN)
s=rounded(holder,mate,'RB_PocketWidth','RB_PocketHeight','RB_PocketRadius','0 mm','0 mm','A05 Phone pocket - FIT')
extrude(holder,s,'-(RB_CoverZ+RB_BackGap)','A05 Phone pocket',CUT)
# Open side-control access while retaining the flange behind the phone.
for tag,xe in [('Left','-RB_TrayWidth/2'),('Right','RB_TrayWidth/2')]:
    s=rectangle(holder,mate,'12 mm','48 mm',xe,'34 mm','A06 '+tag+' control access')
    extrude(holder,s,'-(RB_CoverZ+RB_BackGap)','A06 '+tag+' side opening',CUT)
# Bottom slot includes the back flange, leaving two corner supports.
s=rectangle(holder,mate,'RB_BottomOpening','16 mm','0 mm','-RB_CaseHeight/2','A07 Bottom acoustic and plug clearance')
extrude(holder,s,'-(RB_CoverZ-RB_BackZ)','A07 Open bottom',CUT)
s=rounded(holder,mate,'RB_RearCameraWidth','RB_RearCameraHeight','2 mm','-18 mm','54.5 mm','A08 Rear camera keepout')
extrude(holder,s,'-(RB_CoverZ-RB_BackZ)','A08 Rear camera opening',CUT)
s=rounded(holder,mate,'RB_VentWidth','RB_VentHeight','4 mm','0 mm','-7 mm','A09 Rear ventilation and removal access')
extrude(holder,s,'-(RB_CoverZ-RB_BackZ)','A09 Rear ventilation',CUT)

# YZ sketch local X = global Z, or its inverse depending on Fusion plane basis.
# Inspect the basis rather than assuming it. Local Y must be global Y.
yz_probe=holder.sketches.add(holder.yZConstructionPlane)
probe_origin=yz_probe.sketchToModelSpace(pt(0,0))
probe_u=yz_probe.sketchToModelSpace(pt(1,0))
probe_v=yz_probe.sketchToModelSpace(pt(0,1))
u_sign=1 if probe_u.z-probe_origin.z > 0 else -1
if abs(probe_v.y-probe_origin.y-1)>1e-6:
    raise RuntimeError('Unexpected YZ sketch basis')
yz_probe.deleteMe()

def yz(zexpr,yexpr):
    return (f'({u_sign})*({zexpr})',yexpr)

front_z='RB_BaseFront*cos(RB_Tilt)'
rear_z='-(RB_BaseDepth-RB_BaseFront)*cos(RB_Tilt)'
rib_rear_z='-(RB_BaseDepth-RB_BaseFront-4 mm)*cos(RB_Tilt)'
rib_front_z='-RB_BackGap'

def desk_y(zexpr,top=False):
    return f'RB_DeskY-({zexpr})*tan(RB_Tilt)'+ ('+RB_BaseThickness/cos(RB_Tilt)' if top else '')

for side,xe in [('L','-RB_RibX-RB_RibThickness/2'),('R','RB_RibX-RB_RibThickness/2')]:
    pl=plane(holder,holder.yZConstructionPlane,xe,'A PL10 '+side+' rib')
    coords=[yz(rib_front_z,'0 mm'),yz(rib_front_z,desk_y(rib_front_z,True)+'-0.3 mm'),yz(rib_rear_z,desk_y(rib_rear_z,True)+'-0.3 mm')]
    s=polygon(holder,pl,coords,'A10 '+side+' stand rib - TILT')
    extrude(holder,s,'RB_RibThickness','A10 '+side+' rear stand rib',JOIN)
base_pl=plane(holder,holder.yZConstructionPlane,'-RB_BaseWidth/2','A PL11 Base left side')
front_top_z=f'({front_z})+RB_BaseThickness*sin(RB_Tilt)'
rear_top_z=f'({rear_z})+RB_BaseThickness*sin(RB_Tilt)'
coords=[yz(front_z,desk_y(front_z)),yz(rear_z,desk_y(rear_z)),yz(rear_top_z,desk_y(rear_top_z,True)),yz(front_top_z,desk_y(front_top_z,True))]
s=polygon(holder,base_pl,coords,'A11 Base section - DEPTH LIFT TILT')
extrude(holder,s,'RB_BaseWidth','A11 Desk base',JOIN)
# Open rear cable notch; no connector threading required. The front bridge remains.
channel_pl=plane(holder,holder.xYConstructionPlane,'4 mm','A PL12 Cable channel front stop')
s=rectangle(holder,channel_pl,'RB_CableWidth','RB_BaseDepth','0 mm','RB_DeskY','A12 Cable channel')
extrude(holder,s,'-RB_BaseDepth','A12 Rear-open cable channel',CUT)

cover_occ,cover=new_component('Robot V1 - B Front Cover')
cover_back=plane(cover,cover.xYConstructionPlane,'RB_CoverZ','B PL01 Cover rear face')
cover_front=plane(cover,cover.xYConstructionPlane,'RB_CoverTopZ','B PL02 Cover front face')
silhouette(cover,cover_back,'RB_CoverThickness','B ')
for tag,xe in [('Left','-RB_EyeX'),('Right','RB_EyeX')]:
    s=rounded(cover,cover_front,'RB_EyeWidth','RB_EyeHeight','RB_EyeRadius',xe,'RB_EyeY','B03 '+tag+' eye - EDIT')
    extrude(cover,s,'-RB_CoverThickness','B03 '+tag+' eye aperture',CUT)
s=rounded(cover,cover_front,'RB_BellyWidth','RB_BellyHeight','RB_BellyRadius','0 mm','RB_BellyY','B04 Message window - EDIT')
extrude(cover,s,'-RB_CoverThickness','B04 Message aperture',CUT)
s=circle(cover,cover_front,'RB_TalkDiameter','0 mm','RB_TalkY','B05 Talk button - EDIT')
extrude(cover,s,'-RB_CoverThickness','B05 Touch aperture',CUT)
# Bevel only the front circular edge of the talk aperture.
edge_set=adsk.core.ObjectCollection.create()
for e in cover.bRepBodies.item(0).edges:
    geom=adsk.core.Circle3D.cast(e.geometry)
    if geom and abs(geom.center.z-ev('RB_CoverTopZ'))<1e-6 and abs(geom.center.y-ev('RB_TalkY'))<1e-6 and abs(geom.radius-ev('RB_TalkDiameter')/2)<1e-6:
        edge_set.add(e)
if edge_set.count != 1:
    raise RuntimeError('Could not identify touch aperture edge')
ch=cover.features.chamferFeatures.createInput2()
ch.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edge_set,V('RB_TouchBevel'),False)
f=cover.features.chamferFeatures.add(ch); f.name='B06 Touch entry bevel - EDIT'
s=rounded(cover,cover_front,'RB_ForeheadWidth','RB_ForeheadHeight','2 mm','RB_ForeheadX','RB_ForeheadY','B07 Forehead optics and receiver')
extrude(cover,s,'-RB_CoverThickness','B07 Forehead opening',CUT)
s=circle(cover,cover_front,'RB_HomeDiameter','0 mm','-SE3_OverallHeight/2+SE3_HomeBottomOffset','B08 Home maintenance access')
extrude(cover,s,'-RB_CoverThickness','B08 Home access',CUT)
s=rectangle(cover,cover_front,'RB_MouthWidth','RB_MouthHeight','0 mm','RB_MouthY','B09 Decorative mouth')
extrude(cover,s,'-RB_MouthDepth','B09 Shallow mouth groove',CUT)

for c,pl,depth,prefix in [(holder,mate,'-(RB_CoverZ-RB_BackZ)','A'),(cover,cover_front,'-RB_CoverThickness','B')]:
    for tag,xe,ye in [('TL','-RB_TopScrewX','RB_TopScrewY'),('TR','RB_TopScrewX','RB_TopScrewY'),('BL','-RB_BottomScrewX','RB_BottomScrewY'),('BR','RB_BottomScrewX','RB_BottomScrewY')]:
        s=circle(c,pl,'RB_ScrewDiameter',xe,ye,prefix+'20 '+tag+' M3 clearance')
        extrude(c,s,depth,prefix+'20 '+tag+' bolt hole',CUT)

# One white appearance for both printed parts. Do not recolor the reference phone.
white=design.appearances.itemByName('Robot White PLA')
if not white:
    source=None
    for lib in app.materialLibraries:
        for a in lib.appearances:
            if ('白' in a.name or 'white' in a.name.lower()) and ('プラスチック' in a.name or 'plastic' in a.name.lower()):
                source=a; break
        if source: break
    if not source:
        source=design.appearances.itemByName('SE3 Ceramic White')
    if source:
        white=design.appearances.addByCopy(source,'Robot White PLA')
        for key in ('opaque_albedo','generic_diffuse','metal_f0'):
            p=white.appearanceProperties.itemById(key)
            cp=adsk.core.ColorProperty.cast(p) if p else None
            if cp:
                cp.value=adsk.core.Color.create(235,233,225,255)
                break
for c,name in [(holder,'A - White PLA holder and stand'),(cover,'B - White PLA front cover')]:
    if c.bRepBodies.count != 1:
        raise RuntimeError(f'{c.name}: expected one connected solid, got {c.bRepBodies.count}')
    c.bRepBodies.item(0).name=name
    if white: c.bRepBodies.item(0).appearance=white
    for s in c.sketches: s.isLightBulbOn=False
    for p in c.constructionPlanes: p.isLightBulbOn=False
    c.isOriginFolderLightBulbOn=False

# Keep the phone's original position. Only the view is adjusted to show its desk angle.
cam=app.activeViewport.camera
cam.isSmoothTransition=False
cam.cameraType=adsk.core.CameraTypes.OrthographicCameraType
angle=design.userParameters.itemByName('RB_Tilt').value
cam.target=adsk.core.Point3D.create(0,-1.7,-1.5)
cam.eye=adsk.core.Point3D.create(20,13,32)
cam.upVector=adsk.core.Vector3D.create(0,math.cos(angle),math.sin(angle))
app.activeViewport.camera=cam
app.activeViewport.fit()
app.activeViewport.refresh()
design.computeAll()

result={'components':[], 'backup':backup}
for c in (holder,cover):
    result['components'].append({'name':c.name,'bodies':c.bRepBodies.count,'sketches':c.sketches.count,'features':c.features.count,'unconstrained_sketches':[s.name for s in c.sketches if not s.isFullyConstrained], 'feature_issues':[{'name':f.name,'message':f.errorOrWarningMessage} for f in c.features if f.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState]})
