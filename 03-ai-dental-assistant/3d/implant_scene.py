"""Photoreal dental implant for the BrightSmile site: porcelain molar crown + gold abutment + titanium implant.

Run with the bpy module:  python implant_scene.py --out preview.png [--yaw -35 --explode 0 --res 600x750 --samples 48]
Units: 1 Blender unit = 1 mm.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import bpy  # noqa: I001  (bpy must be imported before bmesh/mathutils)
import bmesh
import numpy as np
from mathutils import Vector

TAU = 2 * math.pi


# ---------------------------------------------------------------- helpers
def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ring(r, th, z):
    r = np.broadcast_to(r, th.shape)
    return np.stack([r * np.cos(th), r * np.sin(th), np.broadcast_to(np.asarray(z, float), th.shape)], -1)


def hex_r(th, af, rot=0.0):
    """Radius of a regular hexagon with across-flats `af` at angle th."""
    a = (th - rot + math.pi / 6) % (math.pi / 3) - math.pi / 6
    return (af / 2) / np.cos(a)


def surface(name, rings, wrap_rows=False, pole_start=None, pole_end=None, smooth=True):
    """Quad surface through a list of rings (each C points around the axis)."""
    rings = np.asarray(rings, dtype=float)
    R, C, _ = rings.shape
    verts = rings.reshape(-1, 3).tolist()
    faces = []
    for i in range(R - 1 + (1 if wrap_rows else 0)):
        a, b = i * C, ((i + 1) % R) * C
        for j in range(C):
            j2 = (j + 1) % C
            faces.append((a + j, a + j2, b + j2, b + j))
    if pole_start is not None:
        k = len(verts)
        verts.append(list(pole_start))
        faces += [(k, j2, j) for j, j2 in ((j, (j + 1) % C) for j in range(C))]
    if pole_end is not None:
        k = len(verts)
        verts.append(list(pole_end))
        a = (R - 1) * C
        faces += [(a + j, a + (j + 1) % C, k) for j in range(C)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ---------------------------------------------------------------- titanium implant (fixture)
PITCH, THREAD_DEPTH = 0.8, 0.40
Z_COLLAR_END, Z_THREAD_END, Z_TIP = -1.25, -9.2, -10.75


def implant_core(z):
    """Core radius: slight taper, then a rounded apex."""
    z = np.asarray(z, float)
    r = np.interp(z, [-9.0, -1.25], [1.48, 1.60])
    apex = np.clip((z - (-9.0)) / (Z_TIP - (-9.0)), 0, 1)       # 0 at -9.0, 1 at tip
    return r * np.sqrt(np.clip(1 - apex ** 2.2, 0, 1))


def thread_profile(phi):
    up = smoothstep(0.06, 0.36, phi)
    down = 1 - smoothstep(0.50, 0.80, phi)
    return np.minimum(up, down)


def build_implant(C=224):
    th = np.linspace(0, TAU, C, endpoint=False)
    rings = []
    af = 2.30                                   # internal hex, across flats
    z_floor = -1.75
    for s in (0.3, 0.6, 0.85, 0.97):            # socket floor
        rings.append(ring(hex_r(th, af) * s, th, z_floor))
    for z in np.linspace(z_floor + 0.04, -0.10, 7):   # socket walls
        rings.append(ring(hex_r(th, af), th, z))
    rings.append(ring(hex_r(th, af + 0.14), th, 0.0))  # chamfer at the top of the socket
    for t in np.linspace(0.12, 1.0, 7):                # platform: hexagon -> circle
        rings.append(ring((1 - t) * hex_r(th, af + 0.14) + t * 1.84, th, 0.0))
    for a in np.linspace(0.12, 1.0, 6) * (math.pi / 2):  # rounded outer edge
        rings.append(ring(1.84 + 0.21 * np.sin(a), th, -0.21 * (1 - np.cos(a))))
    for z in np.linspace(-0.3, Z_COLLAR_END, 8):        # polished collar
        rings.append(ring(np.interp(z, [Z_COLLAR_END, -0.3], [2.0, 2.05]), th, z))
    # threaded body: radius = core + thread, with 3 cutting flutes at the apex
    zs = np.linspace(Z_COLLAR_END - 0.02, -10.55, int((10.55 + Z_COLLAR_END) / PITCH * 34))
    for z in zs:
        core = implant_core(z)
        depth = THREAD_DEPTH * smoothstep(Z_COLLAR_END, Z_COLLAR_END - 0.75, z) * (1 - smoothstep(-8.7, -10.1, z))
        phi = (z / PITCH + th / TAU) % 1.0
        r = core + depth * thread_profile(phi)
        flute = np.zeros_like(th)
        if z < -6.2:
            for k in range(3):
                centre = k * TAU / 3 + 0.18 * (z + 6.2)
                d = np.angle(np.exp(1j * (th - centre)))
                flute = np.maximum(flute, np.exp(-(d / 0.24) ** 4))
            flute *= smoothstep(-6.2, -7.4, z)
            r = r - flute * (depth * thread_profile(phi) + 0.28 * core / 1.5)
        rings.append(ring(np.maximum(r, 0.02), th, z))
    obj = surface("Implant", rings, pole_end=(0, 0, Z_TIP))
    return obj


# ---------------------------------------------------------------- abutment (gold-coloured titanium nitride)
def build_abutment(C=224):
    th = np.linspace(0, TAU, C, endpoint=False)
    rings = []
    af = 2.18
    hole, bore = 0.60, 0.86
    rings.append(ring(hole, th, -1.40))                       # inner edge of the bottom face
    for t in (0.35, 0.7, 0.92):
        rings.append(ring((1 - t) * hole + t * (hex_r(th, af) - 0.08), th, -1.48))
    rings.append(ring(hex_r(th, af) - 0.03, th, -1.45))
    for z in np.linspace(-1.36, -0.06, 6):                    # hex that locks into the implant
        rings.append(ring(hex_r(th, af), th, z))
    rings.append(ring(hex_r(th, af), th, 0.0))
    for t in np.linspace(0.2, 1.0, 5):                         # seating face on the implant platform
        rings.append(ring((1 - t) * hex_r(th, af) + t * 1.80, th, 0.0))
    for t in np.linspace(0.04, 1.0, 16):                       # concave emergence profile
        rings.append(ring(1.80 + 0.82 * t ** 1.7, th, 2.0 * t))
    for a in np.linspace(0.25, 1.0, 4) * (math.pi / 2):        # rounded shoulder
        rings.append(ring(2.62 + 0.05 * np.sin(a), th, 2.0 + 0.1 * (1 - np.cos(a))))
    for t in np.linspace(0.0, 1.0, 5):                         # ledge where the crown sits
        rings.append(ring(2.67 - 0.64 * t, th, 2.12))
    # tapered post with one anti-rotation flat (facing +x)
    for z in np.linspace(2.2, 6.68, 18):
        r = np.interp(z, [2.2, 6.68], [2.00, 1.62])
        flat = 0.80 * r
        cos = np.cos(th)
        r = np.where(cos > 1e-3, np.minimum(r, flat / np.maximum(cos, 1e-3)), r)
        rings.append(ring(r, th, z))
    for a in np.linspace(0.15, 1.0, 6) * (math.pi / 2):        # rounded top edge
        r_top = 1.62 - 0.30 * np.sin(a)
        cos = np.cos(th)
        r = np.where(cos > 1e-3, np.minimum(r_top, 0.80 * r_top / np.maximum(cos, 1e-3)), r_top)
        rings.append(ring(r, th, 6.68 + 0.30 * (1 - np.cos(a))))
    for t in np.linspace(0.25, 1.0, 4):                         # top face towards the screw hole
        rings.append(ring(1.32 * (1 - t) + (bore + 0.06) * t, th, 6.98))
    rings.append(ring(bore, th, 6.90))
    for z in np.linspace(6.7, 3.7, 5):                          # screw channel
        rings.append(ring(bore, th, z))
    rings.append(ring(hole, th, 3.55))
    for z in np.linspace(3.3, -1.2, 5):
        rings.append(ring(hole, th, z))
    return surface("Abutment", rings, wrap_rows=True)


# ---------------------------------------------------------------- porcelain crown: lower first molar
# x = mesio-distal (+mesial), y = bucco-lingual (-buccal, +lingual), z = up from the margin
CUSPS = [  # x, y, tip height, slope, ridge stretch
    (2.80, -2.25, 7.05, 0.62, 1.45),   # mesiobuccal
    (-0.45, -2.65, 6.90, 0.62, 1.45),  # distobuccal
    (-3.30, -1.55, 6.45, 0.68, 1.30),  # distal
    (2.40, 2.35, 7.35, 0.66, 1.50),    # mesiolingual
    (-1.55, 2.50, 7.15, 0.66, 1.50),   # distolingual
]
CENTRE = np.array([0.15, 0.15])


def occlusal_height(x, y, rim=None):
    """Cusps as soft cones meeting in fissures; marginal ridges at the mesial and distal ends.
    `rim` (0 centre .. 1 edge of the occlusal table) makes fissures shallower towards the edge."""
    terms = []
    for cx, cy, h, k, stretch in CUSPS:
        u = CENTRE - np.array([cx, cy])
        u /= np.linalg.norm(u)
        v = np.array([-u[1], u[0]])
        dx, dy = x - cx, y - cy
        du, dv = dx * u[0] + dy * u[1], dx * v[0] + dy * v[1]
        rho = np.sqrt((du / stretch) ** 2 + dv ** 2 + 0.06)
        terms.append(h - k * rho ** 1.25)
    for mx, h in ((4.35, 6.30), (-4.55, 5.95)):                  # marginal ridges
        rho = np.sqrt(((x - mx) / 0.6) ** 2 + (np.maximum(np.abs(y) - 2.2, 0) / 1.5) ** 2 + 0.05)
        terms.append(h - 0.8 * rho ** 1.35)
    T = np.stack(terms)
    beta = 9.0
    m = T.max(0)
    H = m + np.log(np.exp(beta * (T - m)).sum(0)) / beta
    top2 = np.sort(T, axis=0)[-2:]
    gap = top2[1] - top2[0]
    inner = 1.0 if rim is None else 1 - 0.8 * smoothstep(0.55, 1.0, rim)
    H = H - inner * (0.55 * np.exp(-(gap / 0.10) ** 2) + 0.16 * np.exp(-(gap / 0.40) ** 2))   # fissures
    fossa = np.exp(-(((x - CENTRE[0]) / 1.4) ** 2 + ((y - CENTRE[1]) / 1.1) ** 2))
    return H - 0.22 * fossa


def crown_outline(th):
    """Occlusal outline of a lower molar seen from above (rounded, slightly pentagonal, lobed buccally)."""
    a, b, n = 5.45, 4.95, 2.7
    c, s = np.cos(th), np.sin(th)
    r = 1.0 / ((np.abs(c) / a) ** n + (np.abs(s) / b) ** n) ** (1 / n)
    r *= 1 - 0.05 * smoothstep(0.2, 1.0, -c) * (1 - np.abs(s)) ** 2      # distal end narrower
    for ang, amp in ((-1.25, 0.015), (-1.85, 0.018), (-2.55, 0.01), (1.05, 0.01), (2.0, 0.01)):
        d = np.angle(np.exp(1j * (th - ang)))
        r *= 1 + amp * np.exp(-(d / 0.28) ** 2)                          # cusp lobes
    return r


GROOVES = [(-1.62, 0.022), (-2.25, 0.016), (1.55, 0.012)]  # buccal, distobuccal, lingual: angle, depth


def build_crown(C=288):
    th = np.linspace(0, TAU, C, endpoint=False)
    R_hc = crown_outline(th)                                   # height of contour (widest)
    R_occ = 0.845 * R_hc                                       # edge of the occlusal table
    occ_x, occ_y = R_occ * np.cos(th), R_occ * np.sin(th)
    z_edge = occlusal_height(occ_x, occ_y, rim=1.0)
    kernel = np.exp(-np.linspace(-3, 3, 41) ** 2)
    kernel /= kernel.sum()
    z_edge = np.convolve(np.concatenate([z_edge[-20:], z_edge, z_edge[:20]]), kernel, mode="same")[20:-20]
    z_edge = 0.55 * z_edge + 0.45 * np.convolve(np.concatenate([z_edge[-20:], z_edge, z_edge[:20]]),
                                                np.ones(41) / 41, mode="same")[20:-20]
    lingual = np.clip(np.sin(th), 0, 1)
    z_hc = 3.0 + 0.8 * lingual                                  # buccal contour lower than lingual
    notch = np.zeros_like(th)
    for ang, depth in GROOVES:
        d = np.angle(np.exp(1j * (th - ang)))
        notch = np.maximum(notch, depth * np.exp(-(d / 0.09) ** 2))
    r_margin = 2.78
    rings = []
    # intaglio (inside, fits the abutment post) from the cavity roof down to the margin
    for t in (0.35, 0.7):
        rings.append(ring(1.60 * t, th, 5.05))
    for z in np.linspace(4.95, 0.25, 10):
        rings.append(ring(np.interp(z, [0.25, 4.95], [2.06, 1.66]), th, z))
    rings.append(ring(2.12, th, 0.0))
    rings.append(ring(r_margin, th, 0.0))
    # emergence profile up to the height of contour (S-curve), then the walls round over onto the occlusal table
    for t in np.linspace(0.04, 1.0, 26):
        f = t * t * (3 - 2 * t)
        r = r_margin + (R_hc - r_margin) * f
        z = z_hc * t
        g = smoothstep(0.55, 1.0, t)                            # grooves fade out towards the neck
        rings.append(ring(r * (1 - notch * g * 0.6), th, z))
    for t in np.linspace(0.04, 1.0, 26):
        r = R_hc + (R_occ - R_hc) * t ** 1.9
        z = z_hc + (z_edge - z_hc) * (1 - (1 - t) ** 1.6)
        rings.append(ring(r * (1 - notch * (0.6 + 0.4 * t)), th, z))
    # occlusal surface, from the rim to the central fossa
    for rho in np.linspace(0.985, 0.02, 70) ** 0.92:
        x, y = rho * occ_x, rho * occ_y
        h = occlusal_height(x, y, rim=rho)
        blend = smoothstep(0.80, 0.985, rho)
        h = h * (1 - blend) + z_edge * blend
        rings.append(np.stack([x * (1 - notch * 0.4 * rho ** 6), y * (1 - notch * 0.4 * rho ** 6), h], -1))
    centre_z = float(occlusal_height(np.array([0.0]), np.array([0.0]))[0])
    obj = surface("Crown", rings, pole_start=(0, 0, 5.05), pole_end=(0, 0, centre_z))
    return obj


# ---------------------------------------------------------------- materials
def principled(name, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat, bsdf


def link(mat, a, b):
    mat.node_tree.links.new(a, b)


def add_bump(mat, bsdf, scale, strength, detail=3.0, distance=0.02):
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    coords = nt.nodes.new("ShaderNodeTexCoord")
    link(mat, coords.outputs["Object"], tex.inputs["Vector"])
    link(mat, tex.outputs["Fac"], bump.inputs["Height"])
    link(mat, bump.outputs["Normal"], bsdf.inputs["Normal"])
    return tex


def radial_tangent(mat, bsdf):
    nt = mat.node_tree
    tan = nt.nodes.new("ShaderNodeTangent")
    tan.direction_type = "RADIAL"
    tan.axis = "Z"
    link(mat, tan.outputs["Tangent"], bsdf.inputs["Tangent"])


def make_materials():
    ti_rough, b1 = principled("Titanium SLA", **{"Base Color": (0.62, 0.60, 0.58, 1), "Metallic": 1.0, "Roughness": 0.44})
    add_bump(ti_rough, b1, scale=60.0, strength=0.12, detail=6.0, distance=0.01)
    ti_polish, b2 = principled("Titanium polished", **{"Base Color": (0.72, 0.70, 0.67, 1), "Metallic": 1.0,
                                                       "Roughness": 0.22, "Anisotropic": 0.55})
    radial_tangent(ti_polish, b2)
    gold, b3 = principled("TiN gold", **{"Base Color": (0.88, 0.62, 0.27, 1), "Metallic": 1.0, "Roughness": 0.20,
                                          "Anisotropic": 0.45})
    radial_tangent(gold, b3)
    add_bump(gold, b3, scale=90.0, strength=0.04, detail=4.0, distance=0.005)

    por, b4 = principled("Porcelain", **{"Roughness": 0.30, "Subsurface Weight": 1.0,
                                         "Subsurface Radius": (1.0, 0.70, 0.48), "Subsurface Scale": 0.45,
                                         "Coat Weight": 0.7, "Coat Roughness": 0.07, "IOR": 1.52})
    nt = por.node_tree
    coords = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    link(por, coords.outputs["Object"], sep.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")                  # cervical shade -> brighter, cooler cusps
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = 0.0
    mapr.inputs["From Max"].default_value = 7.6
    link(por, sep.outputs["Z"], mapr.inputs["Value"])
    link(por, mapr.outputs["Result"], ramp.inputs["Fac"])
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.80, 0.66, 0.45, 1)
    els[1].position, els[1].color = 0.62, (0.90, 0.83, 0.70, 1)
    e = els.new(1.0)
    e.color = (0.92, 0.88, 0.80, 1)
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")            # stain in the fissures, like a technician's tint
    ao.inputs["Distance"].default_value = 0.45
    ao.only_local = True
    stain = nt.nodes.new("ShaderNodeMix")
    stain.data_type = "RGBA"
    stain.blend_type = "MULTIPLY"
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    link(por, ao.outputs["AO"], inv.inputs[1])
    powr = nt.nodes.new("ShaderNodeMath")
    powr.operation = "MULTIPLY"
    powr.inputs[1].default_value = 0.55
    link(por, inv.outputs["Value"], powr.inputs[0])
    link(por, powr.outputs["Value"], stain.inputs["Factor"])
    link(por, ramp.outputs["Color"], stain.inputs["A"])
    stain.inputs["B"].default_value = (0.62, 0.45, 0.26, 1)
    link(por, stain.outputs["Result"], b4.inputs["Base Color"])
    coat = nt.nodes.new("ShaderNodeMapRange")                  # glaze fades out towards the neck: its sharp
    coat.inputs["From Min"].default_value = 1.4                # reflection of the abutment looked like a window
    coat.inputs["From Max"].default_value = 3.6
    coat.inputs["To Min"].default_value = 0.0
    coat.inputs["To Max"].default_value = 0.7
    link(por, sep.outputs["Z"], coat.inputs["Value"])
    link(por, coat.outputs["Result"], b4.inputs["Coat Weight"])
    add_bump(por, b4, scale=14.0, strength=0.05, detail=5.0, distance=0.02)
    return {"ti_rough": ti_rough, "ti_polish": ti_polish, "gold": gold, "porcelain": por}


# ---------------------------------------------------------------- scene
def build(explode=0.0, yaw_deg=-35.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mats = make_materials()

    implant = build_implant()
    implant.data.materials.append(mats["ti_rough"])
    implant.data.materials.append(mats["ti_polish"])
    for p in implant.data.polygons:                   # polished platform + collar, rough threads
        p.material_index = 1 if p.center.z > Z_COLLAR_END - 0.05 else 0
    abutment = build_abutment()
    abutment.data.materials.append(mats["gold"])
    crown = build_crown()
    crown.data.materials.append(mats["porcelain"])
    sub = crown.modifiers.new("Subdivision", "SUBSURF")
    sub.levels = sub.render_levels = 1

    rig = bpy.data.objects.new("Model", None)
    scene.collection.objects.link(rig)
    for o in (implant, abutment, crown):
        o.parent = rig
    crown.location.z = 2.12
    rig.rotation_euler = (math.radians(0), 0, math.radians(yaw_deg))
    set_explode(explode, implant, abutment, crown)
    return scene, rig, implant, abutment, crown


def set_explode(e, implant, abutment, crown):
    e = max(0.0, min(1.0, e))
    s = e * e * (3 - 2 * e)
    abutment.location.z = 4.6 * s
    crown.location.z = 2.12 + 4.6 * s + 6.4 * s
    implant.location.z = -1.2 * s


def area_light(name, loc, size, energy, target=(0, 0, 0), size_y=None, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    if size_y:
        data.shape = "RECTANGLE"
        data.size, data.size_y = size, size_y
    else:
        data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    direction = Vector(target) - Vector(loc)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    obj.visible_camera = False
    return obj


def studio(scene, zc=-0.6, aspect=(4, 5), dist=78.0, elev_deg=17.0, lens=100.0):
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = lens
    cam_data.sensor_width = 36
    cam_data.clip_start, cam_data.clip_end = 1.0, 1000.0
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    el = math.radians(elev_deg)
    cam.location = (0, -dist * math.cos(el), zc + dist * math.sin(el))
    cam.rotation_euler = (Vector((0, 0, zc)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    t = (0, 0, zc)
    area_light("Key", (-48, -46, 44), 46, 14000, t, color=(1.0, 0.97, 0.93))
    area_light("Fill", (52, -40, 2), 60, 3000, t)
    area_light("Rim L", (-40, 34, 14), 7, 8500, t, size_y=70, color=(0.86, 0.93, 1.0))
    area_light("Rim R", (42, 30, 6), 7, 7500, t, size_y=70, color=(1.0, 0.95, 0.88))
    area_light("Top", (0, 6, 62), 40, 5200, t)
    area_light("Floor bounce", (0, -20, -55), 60, 900, t, color=(0.92, 0.97, 0.96))
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    coords = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(coords.outputs["Generated"], sep.inputs["Vector"])
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1.0
    mapr.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.30, (0.05, 0.055, 0.055, 1)
    els[1].position, els[1].color = 1.0, (0.58, 0.60, 0.60, 1)
    mid = els.new(0.55)
    mid.color = (0.20, 0.21, 0.21, 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    return cam


def render_settings(scene, res=(600, 750), samples=48, threshold=0.02):
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 8, 3, 6
    c.transmission_bounces, c.transparent_max_bounces = 6, 8
    c.caustics_reflective = c.caustics_refractive = False
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = 0.0
    scene.render.threads_mode = "AUTO"


def use_gpu(scene):
    """Metal on Apple Silicon, CUDA/OptiX/HIP elsewhere; falls back to CPU."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return "CPU"
    for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        try:
            prefs.refresh_devices()
        except AttributeError:
            prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == kind]
        if gpus:
            for d in prefs.devices:
                d.use = True
            scene.cycles.device = "GPU"
            return kind
    return "CPU"


def frame_plan(seq, n):
    """(yaw, explode, dist, zc) for every frame of a sequence."""
    if seq == "hero":        # assembled, turning +-30 degrees: driven by the cursor / drag on the site
        return [(-35.0 + a, 0.0, 78.0, -0.6) for a in np.linspace(-30, 30, n)]
    if seq == "explode":     # comes apart while turning a little: driven by scrolling
        plan = []
        for e in np.linspace(0, 1, n):
            s_ = e * e * (3 - 2 * e)
            plan.append((-35.0 + 40.0 * s_, float(e), 78.0 + 44.0 * s_, -0.6 + 4.6 * s_))
        return plan
    raise SystemExit(f"unknown sequence {seq}")


def place_camera(cam, dist, zc, elev_deg):
    el = math.radians(elev_deg)
    cam.location = (0, -dist * math.cos(el), zc + dist * math.sin(el))
    cam.rotation_euler = (Vector((0, 0, zc)) - cam.location).to_track_quat("-Z", "Y").to_euler()


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, help="file for a still, folder for a sequence")
    p.add_argument("--seq", default="", help="hero | explode")
    p.add_argument("--frames", type=int, default=61)
    p.add_argument("--only", default="", help="render a subset, e.g. 0:20")
    p.add_argument("--yaw", type=float, default=-35.0)
    p.add_argument("--explode", type=float, default=0.0)
    p.add_argument("--res", default="600x750")
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--elev", type=float, default=17.0)
    p.add_argument("--dist", type=float, default=78.0)
    p.add_argument("--zc", type=float, default=-0.6)
    p.add_argument("--gpu", action="store_true")
    p.add_argument("--hide", default="", help="comma-separated parts to leave out: implant,abutment,crown")
    p.add_argument("--blend", default="")
    a = p.parse_args(argv)
    scene, rig, implant, abutment, crown = build(a.explode, a.yaw)
    cam = studio(scene, zc=a.zc, dist=a.dist, elev_deg=a.elev)
    w, h = (int(v) for v in a.res.split("x"))
    render_settings(scene, (w, h), a.samples)
    parts = {"implant": implant, "abutment": abutment, "crown": crown}
    for name in filter(None, a.hide.split(",")):
        parts[name].hide_render = True
    device = use_gpu(scene) if a.gpu else "CPU"
    print(f"render device: {device}", flush=True)
    if a.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))
    if not a.seq:
        scene.render.filepath = os.path.abspath(a.out)
        bpy.ops.render.render(write_still=True)
        return
    os.makedirs(a.out, exist_ok=True)
    plan = frame_plan(a.seq, a.frames)
    lo, hi = (int(v) for v in a.only.split(":")) if a.only else (0, len(plan))
    for i in range(lo, min(hi, len(plan))):
        yaw, e, dist, zc = plan[i]
        rig.rotation_euler = (0, 0, math.radians(yaw))
        set_explode(e, implant, abutment, crown)
        place_camera(cam, dist, zc, a.elev)
        scene.render.filepath = os.path.join(os.path.abspath(a.out), f"{a.seq}_{i:03d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"frame {i + 1}/{len(plan)} done", flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
