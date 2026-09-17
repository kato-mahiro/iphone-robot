"""Run in Fusion after build/validation; export editable CAD and mm STL files.
Native Fusion coordinates are preserved in F3D/STEP. STL copies are oriented
for slicing: cover rear face down, holder desk-contact face down (Z=0).
No occurrence or body in the design is moved.
"""
import adsk.core
import adsk.fusion
import math
import os
import struct

ROOT='/Users/kato-mahiro/Projects/personal/iphone-robot'
OUT=ROOT+'/cad'
os.makedirs(OUT,exist_ok=True)
em=design.exportManager

def mm(name):
    return design.userParameters.itemByName(name).value*10

angle=design.userParameters.itemByName('RB_Tilt').value
sin_a,cos_a=math.sin(angle),math.cos(angle)
height_offset=design.userParameters.itemByName('SE3_OverallHeight').value*10/2*cos_a+mm('RB_Lift')

def orient_binary_stl(path,holder):
    with open(path,'rb') as f:
        data=bytearray(f.read())
    triangles=struct.unpack_from('<I',data,80)[0]
    if len(data)!=84+50*triangles:
        raise RuntimeError('Expected binary STL: '+path)
    for i in range(triangles):
        offset=84+i*50
        values=list(struct.unpack_from('<12f',data,offset))
        for j in range(0,12,3):
            x,y,z=values[j:j+3]
            if holder:
                # Rotate +78 deg about X at nominal 12 degree back tilt.
                yy=y*sin_a-z*cos_a
                zz=y*cos_a+z*sin_a+(height_offset if j>0 else 0)
                values[j:j+3]=[x,yy,zz]
            elif j>0:
                values[j+2]=z-mm('RB_CoverZ')
        struct.pack_into('<12f',data,offset,*values)
    data[:80]=b'Robot V1 | millimeters | oriented for slicing'.ljust(80,b' ')
    with open(path,'wb') as f:
        f.write(data)

exports=[]
for o in design.rootComponent.occurrences:
    c=o.component
    if not c.name.startswith('Robot V1 - '):
        continue
    is_holder=c.name.startswith('Robot V1 - A')
    stem='robot-v1-holder' if is_holder else 'robot-v1-cover'
    step=OUT+'/'+stem+'.step'
    if not em.execute(em.createSTEPExportOptions(step,c)):
        raise RuntimeError('STEP export failed')
    stl=OUT+'/'+stem+'.stl'
    opt=em.createSTLExportOptions(c.bRepBodies.item(0),stl)
    opt.isBinaryFormat=True
    opt.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
    if not em.execute(opt):
        raise RuntimeError('STL export failed')
    orient_binary_stl(stl,is_holder)
    exports.extend([step,stl])

# Three inspection views; the assembly itself stays in the phone's coordinates.
vp=app.activeViewport
cam=vp.camera
cam.cameraType=adsk.core.CameraTypes.OrthographicCameraType
cam.isSmoothTransition=False
cam.target=adsk.core.Point3D.create(0,-1.7,-1.5)
cam.eye=adsk.core.Point3D.create(0,-1.7,45)
cam.upVector=adsk.core.Vector3D.create(0,1,0)
vp.camera=cam; vp.fit(); vp.refresh()
vp.saveAsImageFile(OUT+'/robot-v1-front.png',1400,1600)

cam=vp.camera
cam.target=adsk.core.Point3D.create(0,-1.7,-1.5)
cam.eye=adsk.core.Point3D.create(-22,8,-36)
cam.upVector=adsk.core.Vector3D.create(0,cos_a,sin_a)
vp.camera=cam; vp.fit(); vp.refresh()
vp.saveAsImageFile(OUT+'/robot-v1-rear.png',1600,1400)

cam=vp.camera
cam.target=adsk.core.Point3D.create(0,-1.7,-1.5)
cam.eye=adsk.core.Point3D.create(20,13,32)
cam.upVector=adsk.core.Vector3D.create(0,cos_a,sin_a)
vp.camera=cam; vp.fit(); vp.refresh()
vp.saveAsImageFile(OUT+'/robot-v1-perspective.png',1600,1400)
archive=OUT+'/phone-robot-case-v1.f3d'
if not em.execute(em.createFusionArchiveExportOptions(archive)):
    raise RuntimeError('F3D export failed')
exports.append(archive)
result={'exports':exports,'stl_units':'mm','stl_orientation':'Cover back down; holder base down. Holder supports still needed.'}
