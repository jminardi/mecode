#import sys
#sys.path.append("..")
import math
import numpy as np
import numpy.linalg as la
import os
from mecode import GMatrix
#from matrix import GMatrix

g = GMatrix()

def angle(v1,v2):
    cosang = np.dot(v1,v2)
    sinang = la.norm(np.cross(v1,v2))
    return np.arctan2(sinang,cosang)
    
def scaleMajor(theta1,theta2,prior,spacing):
    newDist = prior-spacing/np.tan(theta1)-spacing/np.tan(theta2)
    scale = newDist/prior
    return scale
    
def scaleMinor(theta,spc,pointStart,pointEnd):
    (x1,y1,z1) = pointStart
    (x2,y2,z2) = pointEnd
    original = math.sqrt((x2-x1)**2+(y2-y1)**2+(z2-z1)**2)
    newDist = spc/np.sin(theta)
    scale = newDist/original
    return scale    

def triangleFill(point1,point2,point3,spacing):
    (x1,y1,z1) = point1
    (x2,y2,z2) = point2
    (x3,y3,z3) = point3
    distance = math.fabs((y2-y1)*x3-(x2-x1)*y3-y2*x1)/math.sqrt((y2-y1)**2+(x2-x1)**2) #currently only works in 2D!!!
    initDist = math.sqrt((x2-x1)**2+(y2-y1)**2+(z2-z1)**2)
    vector1_2 = np.array(point2)-np.array(point1)
    vector1_3 = np.array(point3)-np.array(point1)
    vector2_3 = np.array(point3)-np.array(point2)
    angle1 = angle(vector1_2,vector1_3)
    angle2 = angle(vector2_3,-1*vector1_2) #don't need angle 3
    dist = 0
    sign = 1
    scale_major = 1
    while dist <= (distance-spacing): #each step we move along vector 1-2 by an amount that scales down according to how far we've gone. Use scale transformation
        #first major movement along 1-2 vector
        relative_scale_major = scaleMajor(angle1,angle2,initDist,spacing) #calculating absolute vs. relative scaling, I will want to switch this to relative for rhombus to work easily
        scale_minor1 = scaleMinor(angle1, spacing, point1, point3)
        ##print 'minor1 ' + scale_minor1
        scale_minor2 = scaleMinor(angle2, spacing, point2, point3)
        ##print 'minor2 ' + scale_minor2
        g.move((x2-x1)*scale_major*sign,(y2-y1)*scale_major*sign,(z2-z1)*scale_major*sign)
        #minor movement along 2-3 vector
        if sign == 1:
            g.move((x3-x2)*scale_minor2,(y3-y2)*scale_minor2,(z3-z2)*scale_minor2)
        else:
            g.move((x3-x1)*scale_minor1,(y3-y1)*scale_minor1,(z3-z1)*scale_minor1)
        dist = dist + spacing
        sign = sign*-1 #go the other way next time
        scale_major = scale_major*relative_scale_major #should let it go down then up again if necessary
        initDist = initDist*relative_scale_major #length of previous line

def rhombusFill(point1,point2,point3,point4,spacing):
    (x1,y1,z1) = point1
    (x2,y2,z2) = point2
    (x3,y3,z3) = point3
    (x4,y4,z4) = point4
    distance_3 = math.fabs((y2-y1)*x3-(x2-x1)*y3-y2*x1)/math.sqrt((y2-y1)**2+(x2-x1)**2) #currently only works in 2D!!!
    distance_4 = math.fabs((y2-y1)*x4-(x2-x1)*y4-y2*x1)/math.sqrt((y2-y1)**2+(x2-x1)**2) #currently only works in 2D!!!
    initDist = math.sqrt((x2-x1)**2+(y2-y1)**2+(z2-z1)**2)
    vector1_2 = np.array(point2)-np.array(point1)
    vector2_3 = np.array(point3)-np.array(point2)
    vector1_4 = np.array(point4)-np.array(point1)
    vector3_4 = np.array(point4)-np.array(point3)
    angle1 = angle(vector1_2,vector1_4)
    angle2 = angle(vector2_3,-1*vector1_2)
    angle3 = angle(-1*vector2_3,vector3_4)
    angle4 = angle(-1*vector1_4,-1*vector3_4)
    dist = 0
    sign = 1
    scale_major = 1 #initialize at 1; this is a changing value
    scale_minor1 = scaleMinor(angle1, spacing, point1, point4) #minor scale values are constant between points
    scale_minor2 = scaleMinor(angle2, spacing, point2, point3)
    scale_minor3 = scaleMinor(angle3-(math.pi-angle2), spacing, point3, point4)
    scale_minor4 = scaleMinor(angle4-(math.pi-angle1), spacing, point4, point3)
    
    if distance_4 <= distance_3:
        while dist <= (distance_3-spacing): #each step we move along vector 1-2 by an amount that scales down according to how far we've gone. Use scale transformation
            #first major movement along 1-2 vector
            if dist <= distance_4-spacing:
                relative_scale_major = scaleMajor(angle1,angle2,initDist,spacing) #relative scaling of next step vs. prior step
            else:
                relative_scale_major = scaleMajor((angle4-(math.pi-angle1)),angle2,initDist,spacing) #relative scaling of next step vs. prior step
            g.move((x2-x1)*scale_major*sign,(y2-y1)*scale_major*sign,(z2-z1)*scale_major*sign)
            if sign == 1:
                g.move((x3-x2)*scale_minor2,(y3-y2)*scale_minor2,(z3-z2)*scale_minor2)
            elif dist <= distance_4-spacing:
                g.move((x4-x1)*scale_minor1,(y4-y1)*scale_minor1,(z4-z1)*scale_minor1)
            else:
                g.move((x3-x4)*scale_minor4,(y3-y4)*scale_minor4,(z3-z4)*scale_minor4)
            dist = dist + spacing
            sign = sign*-1 #go the other way next time
            scale_major = scale_major*relative_scale_major #applies new scaling on top of previous one
            initDist = initDist*relative_scale_major #length of previous line

    else:
        while dist <= (distance_4-spacing): #each step we move along vector 1-2 by an amount that scales down according to how far we've gone. Use scale transformation
            #first major movement along 1-2 vector
            if dist <= distance_3-spacing:
                relative_scale_major = scaleMajor(angle1,angle2,initDist,spacing) #relative scaling of next step vs. prior step
            else:
                relative_scale_major = scaleMajor(angle1,(angle3-(math.pi-angle2)),initDist,spacing) #relative scaling of next step vs. prior step
            g.move((x2-x1)*scale_major*sign,(y2-y1)*scale_major*sign,(z2-z1)*scale_major*sign)
            if sign == 1 and dist <= distance_3-spacing:
                g.move((x3-x2)*scale_minor2,(y3-y2)*scale_minor2,(z3-z2)*scale_minor2)
            elif sign == 1:
                g.move((x4-x3)*scale_minor3,(y4-y3)*scale_minor3,(z4-z3)*scale_minor3)
            else:
                g.move((x4-x1)*scale_minor1,(y4-y1)*scale_minor1,(z4-z1)*scale_minor1)
            dist = dist + spacing
            sign = sign*-1 #go the other way next time
            scale_major = scale_major*relative_scale_major #applies new scaling on top of previous one
            initDist = initDist*relative_scale_major #length of previous line

#will always return to where it started from
def triangleMultilayerMeander(rotation,com,speed,pres,point2,point3,z,spacing,layers):
    g.push_matrix()
    g.rotate(rotation)
    g.feed(speed)
    g.set_pressure(com,pres)
    for i in range(0,layers):
        g.move(0,0,-heaven+z*(i+1))
        g.toggle_pressure(com)#on
        triangleFill((0,0,0),point2,point3,spacing)
        g.toggle_pressure(com)#off
        g.move(0,0,heaven-z*(i+1))
        (r1,r2,r3) = point3
        g.move(-r1,-r2,-r3) #returns to start
    g.pop_matrix()
    
def rhombusMultilayerMeander(rotation,com,speed,pres,point2,point3,point4,z,spacing,layers):
    g.push_matrix()
    g.rotate(rotation)
    g.feed(speed)
    g.set_pressure(com,pres)
    (x1,y1,z1) = (0,0,0)
    (x2,y2,z2) = point2
    (x3,y3,z3) = point3
    (x4,y4,z4) = point4    
    distance_3 = math.fabs((y2-y1)*x3-(x2-x1)*y3-y2*x1)/math.sqrt((y2-y1)**2+(x2-x1)**2) #currently only works in 2D!!!
    distance_4 = math.fabs((y2-y1)*x4-(x2-x1)*y4-y2*x1)/math.sqrt((y2-y1)**2+(x2-x1)**2) #currently only works in 2D!!!
    
    for i in range(0,layers):
        g.move(0,0,-heaven+z*(i+1))
        g.toggle_pressure(com)#on
        rhombusFill((0,0,0),point2,point3,point4,spacing)
        g.toggle_pressure(com)#off
        g.move(0,0,heaven-z*(i+1))
        if distance_3 >= distance_4:
            g.move(-x3,-y3,-z3) #returns to start
        else:
            g.move(-x4,-y4,-z4) #alternative return to start
    g.pop_matrix()
    
def moveRotationCircumferential(rotation,r, ew,layers):
    g.push_matrix()
    g.rotate(rotation)
    g.move(r,0,0)
    triangleMultilayerMeander(0,com_LCE,spd_LCE,LCEpres,(0,ew,0),(-1*r,0,0),z_LCE,spc_LCE,layers)
    triangleMultilayerMeander(0,com_LCE,spd_LCE,LCEpres,(0,-1*ew,0),(-1*r,0,0),z_LCE,spc_LCE,layers)
    g.pop_matrix()
    
def moveRotationRadial(rotation,r, ew,layers):
    g.push_matrix()
    g.rotate(rotation)
    g.move(r,0,0)
    triangleMultilayerMeander(0,com_LCE,spd_LCE,LCEpres,(-1*r,0,0),(0,ew,0),z_LCE,spc_LCE,layers)
    triangleMultilayerMeander(0,com_LCE,spd_LCE,LCEpres,(-1*r,0,0),(0,-1*ew,0),z_LCE,spc_LCE,layers)
    g.pop_matrix()

#print parameters
z_LCE = 1
LCEpres = 25
spd_LCE = 15
spc_LCE = 1
com_LCE = 5
layers_radial = 2
layers_circumferential = 2
heaven = 30
spd_travel = 15

sections = 8
angle_step_degrees = 360.0/(sections*2)
angle_step_rad = math.pi*2*angle_step_degrees/360
radius = 10
end_width = math.tan(angle_step_rad)*radius

i = 0
j = 0
'''
'''
g.feed(spd_travel)

while i <= sections:
    g.abs_move(0,0,z_LCE*layers_radial)
    moveRotationRadial(i*2*angle_step_rad,radius,end_width,layers_radial)
    i = i+1

while j <= sections:
    g.abs_move(0,0,z_LCE*layers_circumferential+z_LCE*layers_radial)
    moveRotationCircumferential(j*2*angle_step_rad,radius,end_width,layers_circumferential)
    j = j+1

#g.view('matplotlib')
#g.view('vpython',substrate_dims=[0.0,0.0,-28.5,300,1,300],nozzle_dims=[1.0,5.0],nozzle_cam=True)
g.gen_geometry('test')
g.teardown()