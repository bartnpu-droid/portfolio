"""TACET One over-ear headphones for the product page: procedural model, three colourways, studio light.

Blender:  blender -b --factory-startup -P tacet_scene.py -- --shot look --colour bone --out out/tacet/look_bone --gpu
bpy:      python tacet_scene.py --shot still --colour bone --out test.png --res 480x480 --samples 24
Shots:    still | look (turntable) | hero (all three colours) | explode (one ear cup coming apart)
          | cushion (close-up) | layers (ear cup taken apart, stacked)
Units: 1 Blender unit = 1 cm. Z is up, the headphones face -Y (the camera) and the ear cups sit on +-X.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import bpy  # noqa: I001  (bpy before bmesh / mathutils)
import bmesh
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

TAU = 2 * math.pi


def lin(h):
    """sRGB hex -> linear RGBA."""
    c = [((h >> s) & 255) / 255 for s in (16, 8, 0)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return (*c, 1.0)


COLORWAYS = {
    "obsidian": dict(shell=0x1d1e21, cap=0x34353a, metal=0x3a3b40, cushion=0x18181a, pad=0x161618, fabric=0x0d0d0e,
                     logo=0x707177),
    "bone": dict(shell=0xe2dccf, cap=0xd0c6b5, metal=0xc4baa8, cushion=0xd8d0c2, pad=0xd1c9ba, fabric=0x8c877f,
                 logo=0xece4d4),
    "moss": dict(shell=0x48533f, cap=0x737a6b, metal=0x5f665a, cushion=0x363e33, pad=0x30372d, fabric=0x1c201b,
                 logo=0x99a090),
}

# ---------------------------------------------------------------- dimensions (cm)
A, B, NEXP = 3.4, 4.1, 2.5          # ear cup outline: half-width (front-back), half-height, superellipse exponent
J = 192                             # points around the outline
CX = 7.0                            # shell front (cushion side) from the middle of the head
XY = 1.05                           # yoke plane, outwards from the shell front
DY = 0.55                           # yoke centre line outside the outline
BAND_END_Z, BAND_H, BAND_N, BAND_T = 6.5, 7.1, 2.3, 0.34
FLOOR_Z = -4.15
SHELL_OUT = [(-0.64, 2.32), (-0.50, 2.29), (-0.32, 2.20), (-0.16, 2.03), (-0.04, 1.76), (0.03, 1.42), (0.06, 1.02),
             (0.06, 0.62), (0.03, 0.30), (-0.03, 0.09), (-0.10, 0.0)]   # (offset from the outline, x) from cap to rim
CUSH_C, CUSH_U, CUSH_X = -0.86, 0.80, 1.0   # cushion ring: centre offset, half width, half thickness


# ---------------------------------------------------------------- curves
def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def catmull(pts, n=5):
    p = np.asarray(pts, float)
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2])
    return np.array(out)


def resample(p, m, closed=True):
    p = np.asarray(p, float)
    pc = np.vstack([p, p[:1]]) if closed else p
    seg = np.linalg.norm(np.diff(pc, axis=0), axis=1)
    L = np.concatenate([[0], np.cumsum(seg)])
    u = np.linspace(0, L[-1], m, endpoint=not closed)
    return np.stack([np.interp(u, L, pc[:, k]) for k in range(p.shape[1])], -1)


def tangents(p, closed=True):
    if closed:
        d = np.roll(p, -1, 0) - np.roll(p, 1, 0)
    else:
        d = np.gradient(p, axis=0)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def superellipse(a, b, e, t):
    c, s = np.cos(t), np.sin(t)
    return np.stack([a * np.sign(c) * np.abs(c) ** (2 / e), b * np.sign(s) * np.abs(s) ** (2 / e)], -1)


def outline(n=J, a=A, b=B, e=NEXP):
    """Ear cup outline in (y, z), resampled by arc length; starts at (+a, 0) and runs over the top."""
    C = resample(superellipse(a, b, e, np.linspace(0, TAU, 8192, endpoint=False)), n)
    T = tangents(C)
    N = np.stack([T[:, 1], -T[:, 0]], -1)
    return C, N


OUT_C, OUT_N = outline()


def ring(d, x, scale=1.0, C=None, N=None):
    """3D ring at axial position x: the outline offset by d, then scaled about the axis."""
    C = OUT_C if C is None else C
    N = OUT_N if N is None else N
    yz = (C + d * N) * scale
    return np.column_stack([np.broadcast_to(np.asarray(x, float), (len(yz),)), yz])


def rrect(hw, hh, r, m=48):
    pts = []
    for cx, cy, a0 in ((hw - r, hh - r, 0), (-hw + r, hh - r, 90), (-hw + r, -hh + r, 180), (hw - r, -hh + r, 270)):
        for a in np.linspace(a0, a0 + 90, 24):
            pts.append((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
    p = np.array(pts)
    p = np.roll(p, -int(np.argmin(np.abs(p[:, 1]) - p[:, 0] * 1e-3)), 0)   # start on the +u side
    return resample(p, m)


def superprofile(hw, hh, e=2.6, m=48):
    return resample(superellipse(hw, hh, e, np.linspace(0, TAU, 4096, endpoint=False)), m)


# ---------------------------------------------------------------- meshes
def surface(name, rings, seg_mat=None, wrap_rows=False, pole_start=None, pole_end=None, sharp=38.0, smooth=True):
    """Quad surface through rings (R, C, 3); per-loop UVs (u around, v along), material index per row."""
    rings = np.asarray(rings, float)
    R, C, _ = rings.shape
    verts = rings.reshape(-1, 3).tolist()
    faces, uvs, mats = [], [], []
    nrow = R - 1 + (1 if wrap_rows else 0)
    for i in range(nrow):
        a, b = i * C, ((i + 1) % R) * C
        v0, v1 = i / max(nrow, 1), (i + 1) / max(nrow, 1)
        m = seg_mat(i) if seg_mat else 0
        for j in range(C):
            j2 = (j + 1) % C
            faces.append((a + j, a + j2, b + j2, b + j))
            uvs += [(j / C, v0), ((j + 1) / C, v0), ((j + 1) / C, v1), (j / C, v1)]
            mats.append(m)
    if pole_start is not None:
        k = len(verts)
        verts.append(list(pole_start))
        m = seg_mat(-1) if seg_mat else 0
        for j in range(C):
            faces.append((k, (j + 1) % C, j))
            uvs += [((j + 0.5) / C, 0.0), ((j + 1) / C, 0.0), (j / C, 0.0)]
            mats.append(m)
    if pole_end is not None:
        k = len(verts)
        verts.append(list(pole_end))
        a = (R - 1) * C
        m = seg_mat(R - 1) if seg_mat else 0
        for j in range(C):
            faces.append((a + j, a + (j + 1) % C, k))
            uvs += [(j / C, 1.0), ((j + 1) / C, 1.0), ((j + 0.5) / C, 1.0)]
            mats.append(m)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
    me.polygons.foreach_set("material_index", mats)
    finish(me, sharp, smooth)
    return me


def finish(me, sharp=38.0, smooth=True):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = smooth
    if smooth and sharp:
        lim = math.radians(sharp)
        for e in bm.edges:
            if e.is_manifold and e.calc_face_angle(0.0) > lim:
                e.smooth = False
    bm.to_mesh(me)
    bm.free()
    me.update()


def lathe(name, prof, origin, axis, seg_mat=None, n=64, sharp=38.0):
    """Surface of revolution: prof = [(r, h)], r = 0 at either end makes a pole."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    tmp = np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = np.cross(axis, tmp)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(axis, e1)
    al = np.linspace(0, TAU, n, endpoint=False)
    o = np.asarray(origin, float)
    rings, ps, pe = [], None, None
    prof = list(prof)
    if prof[0][0] == 0:
        ps = o + prof[0][1] * axis
        prof = prof[1:]
    if prof[-1][0] == 0:
        pe = o + prof[-1][1] * axis
        prof = prof[:-1]
    for r, h in prof:
        rings.append(o + h * axis + r * (np.cos(al)[:, None] * e1 + np.sin(al)[:, None] * e2))
    return surface(name, rings, seg_mat, pole_start=ps, pole_end=pe, sharp=sharp)


def sweep(name, path, B, N, profile, seg_mat=None, caps=(True, True), sharp=38.0):
    """Rings along a path; profile(k) -> (M, 2) points: u along B, v along N."""
    rings = []
    for k in range(len(path)):
        pr = profile(k)
        rings.append(path[k] + pr[:, :1] * B[k] + pr[:, 1:2] * N[k])
    rings = np.array(rings)
    ps = rings[0].mean(0) if caps[0] else None
    pe = rings[-1].mean(0) if caps[1] else None
    return surface(name, rings, seg_mat, pole_start=ps, pole_end=pe, sharp=sharp)


def flat_mesh(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([list(v) for v in verts], [], faces)
    finish(me, sharp=0, smooth=False)
    return me


def rbox(name, size, centre, axes, mat, parent, bevel=0.03):
    """Box with rounded edges; axes = 3 column vectors (x, y, z directions)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = add(name, me, [mat], parent)
    m = Matrix(np.column_stack([np.asarray(a, float) for a in axes]).tolist()).to_4x4()
    m.translation = Vector(centre)
    o.matrix_basis = m
    bv = o.modifiers.new("Bevel", "BEVEL")
    bv.width, bv.segments = bevel, 3
    for p in me.polygons:
        p.use_smooth = True
    return o


def add(name, me, mats, parent=None, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, me)
    for m in mats:
        me.materials.append(m)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    o.location = loc
    return o


def empty(name, parent=None, loc=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.parent = parent
    o.location = loc
    return o


# ---------------------------------------------------------------- materials
def principled(name, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat, bsdf


def node(mat, kind, **props):
    n = mat.node_tree.nodes.new(kind)
    for k, v in props.items():
        if k.startswith("in_"):
            n.inputs[k[3:].replace("_", " ")].default_value = v
        else:
            setattr(n, k, v)
    return n


def link(mat, a, b):
    mat.node_tree.links.new(a, b)


def math_node(mat, op, a, b=None, clamp=False):
    n = node(mat, "ShaderNodeMath", operation=op, use_clamp=clamp)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            link(mat, v, n.inputs[i])
    return n.outputs[0]


def bump(mat, bsdf, height, strength, distance):
    b = node(mat, "ShaderNodeBump", in_Strength=strength, in_Distance=distance)
    link(mat, height, b.inputs["Height"])
    link(mat, b.outputs["Normal"], bsdf.inputs["Normal"])
    return b


def obj_coords(mat):
    return node(mat, "ShaderNodeTexCoord").outputs["Object"]


def rough_variation(mat, bsdf, base, amount, scale=6.0):
    n = node(mat, "ShaderNodeTexNoise", in_Scale=scale, in_Detail=2.0)
    link(mat, obj_coords(mat), n.inputs["Vector"])
    r = math_node(mat, "MULTIPLY_ADD", n.outputs["Fac"], amount * 2)
    r.node.inputs[2].default_value = base - amount
    link(mat, r, bsdf.inputs["Roughness"])


def mat_polymer(name, col):
    """Soft-touch polymer: matte, a little sheen, very fine grain."""
    mat, bsdf = principled(name, **{"Base Color": lin(col), "Roughness": 0.44, "Specular IOR Level": 0.45,
                                    "Sheen Weight": 0.12, "Sheen Roughness": 0.5})
    rough_variation(mat, bsdf, 0.44, 0.05)
    n = node(mat, "ShaderNodeTexNoise", in_Scale=90.0, in_Detail=3.0)
    link(mat, obj_coords(mat), n.inputs["Vector"])
    bump(mat, bsdf, n.outputs["Fac"], 0.05, 0.01)
    return mat


def mat_metal(name, col, rough=0.32, blasted=True):
    mat, bsdf = principled(name, **{"Base Color": lin(col), "Metallic": 1.0, "Roughness": rough})
    rough_variation(mat, bsdf, rough, 0.03, scale=9.0)
    if blasted:
        n = node(mat, "ShaderNodeTexNoise", in_Scale=260.0, in_Detail=2.0)
        link(mat, obj_coords(mat), n.inputs["Vector"])
        bump(mat, bsdf, n.outputs["Fac"], 0.06, 0.004)
    return mat


def mat_steel(name):
    mat, bsdf = principled(name, **{"Base Color": (0.56, 0.56, 0.57, 1), "Metallic": 1.0, "Roughness": 0.2,
                                    "Anisotropic": 0.5})
    return mat


def mat_leather(name, col, pleats=False):
    """Protein leather: grain, soft sheen; pleats where it gathers at the opening of the cushion."""
    mat, bsdf = principled(name, **{"Base Color": lin(col), "Roughness": 0.5, "Specular IOR Level": 0.45,
                                    "Sheen Weight": 0.25, "Sheen Roughness": 0.45, "Coat Weight": 0.06,
                                    "Coat Roughness": 0.35})
    rough_variation(mat, bsdf, 0.5, 0.06, scale=4.0)
    vor = node(mat, "ShaderNodeTexVoronoi", in_Scale=30.0)
    link(mat, obj_coords(mat), vor.inputs["Vector"])
    noi = node(mat, "ShaderNodeTexNoise", in_Scale=7.0, in_Detail=3.0)
    link(mat, obj_coords(mat), noi.inputs["Vector"])
    grain = math_node(mat, "ADD", math_node(mat, "MULTIPLY", vor.outputs["Distance"], 0.7),
                      math_node(mat, "MULTIPLY", noi.outputs["Fac"], 0.3))
    g = node(mat, "ShaderNodeBump", in_Strength=0.45, in_Distance=0.006)
    link(mat, grain, g.inputs["Height"])
    if not pleats:
        link(mat, g.outputs["Normal"], bsdf.inputs["Normal"])
        return mat
    # soft wrinkles where the leather gathers: the inner wall and the edge of the face against the head
    uv = node(mat, "ShaderNodeUVMap", uv_map="UVMap")
    sep = node(mat, "ShaderNodeSeparateXYZ")
    link(mat, uv.outputs["UV"], sep.inputs["Vector"])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    st = node(mat, "ShaderNodeCombineXYZ")
    link(mat, math_node(mat, "MULTIPLY", u, 70.0), st.inputs["X"])
    link(mat, math_node(mat, "MULTIPLY", v, 5.0), st.inputs["Y"])
    wr = node(mat, "ShaderNodeTexNoise", in_Scale=1.0, in_Detail=2.0, in_Roughness=0.4)
    link(mat, st.outputs["Vector"], wr.inputs["Vector"])
    ph = math_node(mat, "MULTIPLY_ADD", u, TAU * 46)
    link(mat, math_node(mat, "MULTIPLY", wr.outputs["Fac"], 5.0), ph.node.inputs[2])
    wave = math_node(mat, "MULTIPLY_ADD", math_node(mat, "SINE", ph), 0.5)
    wave.node.inputs[2].default_value = 0.5
    lo = node(mat, "ShaderNodeMapRange", in_From_Min=0.38, in_From_Max=0.50, clamp=True)
    link(mat, v, lo.inputs["Value"])
    hi = node(mat, "ShaderNodeMapRange", in_From_Min=0.86, in_From_Max=0.64, clamp=True)
    link(mat, v, hi.inputs["Value"])
    mask = math_node(mat, "MULTIPLY", lo.outputs["Result"], hi.outputs["Result"])
    wrinkles = math_node(mat, "MULTIPLY", math_node(mat, "ADD", math_node(mat, "MULTIPLY", wave, 0.6),
                                                     math_node(mat, "MULTIPLY", wr.outputs["Fac"], 0.8)), mask)
    w = node(mat, "ShaderNodeBump", in_Strength=0.8, in_Distance=0.035)
    link(mat, wrinkles, w.inputs["Height"])
    link(mat, g.outputs["Normal"], w.inputs["Normal"])
    link(mat, w.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def mat_fabric(name, col):
    mat, bsdf = principled(name, **{"Base Color": lin(col), "Roughness": 0.85, "Sheen Weight": 0.6,
                                    "Sheen Roughness": 0.4, "Specular IOR Level": 0.3})
    co = obj_coords(mat)
    w1 = node(mat, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Y", in_Scale=26.0)
    w2 = node(mat, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", in_Scale=26.0)
    link(mat, co, w1.inputs["Vector"])
    link(mat, co, w2.inputs["Vector"])
    bump(mat, bsdf, math_node(mat, "MULTIPLY", w1.outputs["Fac"], w2.outputs["Fac"]), 0.35, 0.004)
    return mat


def mat_plain(name, col, rough=0.6, metal=0.0, spec=0.5):
    mat, _ = principled(name, **{"Base Color": col if isinstance(col, tuple) else lin(col), "Roughness": rough,
                                 "Metallic": metal, "Specular IOR Level": spec})
    return mat


def mat_baffle(name):
    """Dark plastic with a grid of perforations."""
    mat, bsdf = principled(name, **{"Base Color": lin(0x1a1b1d), "Roughness": 0.55})
    vor = node(mat, "ShaderNodeTexVoronoi", in_Scale=7.0, in_Randomness=0.0)
    link(mat, obj_coords(mat), vor.inputs["Vector"])
    holes = math_node(mat, "LESS_THAN", vor.outputs["Distance"], 0.2)
    ramp = node(mat, "ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = lin(0x1a1b1d)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.002, 0.002, 0.002, 1)
    link(mat, holes, ramp.inputs["Fac"])
    link(mat, ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump(mat, bsdf, math_node(mat, "SUBTRACT", 1.0, holes), 0.4, 0.01)
    return mat


def mat_cone(name):
    """Driver cone: dark composite with fine radial ribs."""
    mat, bsdf = principled(name, **{"Base Color": lin(0x202124), "Roughness": 0.5})
    uv = node(mat, "ShaderNodeUVMap", uv_map="UVMap")
    sep = node(mat, "ShaderNodeSeparateXYZ")
    link(mat, uv.outputs["UV"], sep.inputs["Vector"])
    ribs = math_node(mat, "SINE", math_node(mat, "MULTIPLY", sep.outputs["X"], TAU * 36))
    bump(mat, bsdf, ribs, 0.15, 0.01)
    return mat


def materials(cw):
    c = COLORWAYS[cw]
    return {
        "shell": mat_polymer(f"{cw} shell", c["shell"]),
        "band": mat_polymer(f"{cw} band", c["shell"]),
        "cap": mat_metal(f"{cw} cap", c["cap"], 0.34),
        "metal": mat_metal(f"{cw} yoke", c["metal"], 0.27),
        "logo": mat_metal(f"{cw} logo", c["logo"], 0.08, blasted=False),
        "polished": mat_metal(f"{cw} polished", c["metal"], 0.1, blasted=False),
        "cushion": mat_leather(f"{cw} cushion", c["cushion"], pleats=True),
        "pad": mat_leather(f"{cw} pad", c["pad"]),
        "fabric": mat_fabric(f"{cw} fabric", c["fabric"]),
        "steel": mat_steel(f"{cw} steel"),
        "interior": mat_plain(f"{cw} chamber", 0x0b0b0c, 0.75),
        "button": mat_plain(f"{cw} button", c["shell"], 0.3),
        "led": mat_plain(f"{cw} led", (0.01, 0.01, 0.01, 1), 0.08),
        # inside the cup, only seen in the exploded views
        "dome": mat_plain("dome", 0xc9b48c, 0.16, metal=1.0),
        "cone": mat_cone("cone"),
        "rubber": mat_plain("surround", 0x0c0c0d, 0.7),
        "frame": mat_plain("frame", 0x3d3e42, 0.32, metal=1.0),
        "magnet": mat_plain("magnet", 0xa7a8ab, 0.2, metal=1.0),
        "baffle": mat_baffle("baffle"),
        "pcb": mat_plain("pcb", 0x101112, 0.35),
        "mic": mat_plain("mic", 0xb9babd, 0.25, metal=1.0),
        "gold": mat_plain("contacts", 0xd8b26a, 0.2, metal=1.0),
    }


# ---------------------------------------------------------------- the ear cup (local x points away from the head)
def shell_mesh(name):
    prof = catmull(SHELL_OUT, 5)
    rings, mats = [], []
    for f in (0.12, 0.35, 0.6, 0.82):                       # back face, hidden under the cap
        rings.append(ring(-0.64, 2.32, f)); mats.append(0)
    for d, x in prof:                                       # outer surface, cap groove -> front rim
        rings.append(ring(d, x)); mats.append(0)
    rings.append(ring(-0.30, 0.0)); mats.append(1)          # front rim
    for x in (0.2, 0.8, 1.4, 1.85):                         # acoustic chamber wall
        rings.append(ring(-0.30, x)); mats.append(1)
    for f in (0.82, 0.6, 0.35, 0.12):                       # chamber floor
        rings.append(ring(-0.30, 1.85, f)); mats.append(1)
    n_out = 4 + len(prof)
    seg = lambda i: 0 if (i < 0 or i < n_out) else 1        # noqa: E731
    me = surface(name, rings, seg, pole_start=(2.32, 0, 0), pole_end=(1.85, 0, 0))
    return me


def cap_mesh(name):
    rings = []
    for f in (0.12, 0.4, 0.7, 0.9):
        rings.append(ring(-0.72, 2.30, f))
    for d, x in ((-0.72, 2.30), (-0.72, 2.44), (-0.725, 2.475), (-0.745, 2.505), (-0.78, 2.528), (-0.83, 2.54)):
        rings.append(ring(d, x))
    for f in (0.97, 0.9, 0.78, 0.6, 0.4, 0.2, 0.07):
        rings.append(ring(-0.83, 2.54 + 0.04 * (1 - f * f), f))
    return surface(name, rings, pole_start=(2.30, 0, 0), pole_end=(2.58, 0, 0), sharp=50)


def logo_mesh(name):
    """The TACET mark, inlaid in the cap: a rounded square and two bars (from the site logo)."""
    u = 1.25 / 28
    outer, inner = rrect(14 * u, 14 * u, 9 * u, 64), rrect(12 * u, 12 * u, 7 * u, 64)
    verts, faces = [], []
    x = 2.58 + 0.002
    for p in outer:
        verts.append((x, p[0], p[1]))
    for p in inner:
        verts.append((x, p[0], p[1]))
    n = len(outer)
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((i, i2, n + i2, n + i))
    for cy in (-3.1 * u, 3.1 * u):
        bar = rrect(1.4 * u, 6 * u, 1.39 * u, 24)
        k = len(verts)
        for p in bar:
            verts.append((x, p[0] + cy, p[1]))
        faces.append(tuple(range(k, k + len(bar))))
    return flat_mesh(name, verts, faces)


def cushion_mesh(name):
    prof = superprofile(CUSH_U, CUSH_X, 2.6, 56)            # (radial offset, x) around the cross-section
    rings = []
    for pu, px in prof:
        rings.append(ring(CUSH_C + pu, -CUSH_X + px))
    return surface(name, rings, wrap_rows=True)


def fabric_mesh(name):
    d = CUSH_C - CUSH_U + 0.06
    rings = [ring(d, -0.55, f) for f in (1.0, 0.8, 0.55, 0.3, 0.1)]
    return surface(name, rings, pole_end=(-0.55, 0, 0))


def driver_mesh(name, x0=0.35):
    prof, mats = [], []
    for t in np.linspace(0, 1, 9)[1:]:                      # dome
        prof.append((0.85 * t, x0 - 0.22 * (1 - t * t))); mats.append(0)
    for t in np.linspace(0, 1, 8)[1:]:                      # cone
        prof.append((0.85 + 0.9 * t, x0 + 0.3 * t ** 1.2)); mats.append(1)
    for t in np.linspace(0, 1, 9)[1:]:                      # surround roll
        prof.append((1.75 + 0.3 * t, x0 + 0.3 - 0.11 * math.sin(math.pi * t))); mats.append(2)
    for r, h in ((2.42, x0 + 0.32), (2.44, x0 + 0.36), (2.44, x0 + 0.6), (2.4, x0 + 0.64), (1.6, x0 + 0.64),
                 (1.16, x0 + 0.64)):
        prof.append((r, h)); mats.append(3)                 # basket
    for r, h in ((1.15, x0 + 0.7), (1.15, x0 + 1.2), (1.1, x0 + 1.25), (0.0, x0 + 1.26)):
        prof.append((r, h)); mats.append(4)                 # magnet
    prof = [(0.0, x0 - 0.22)] + prof
    mats = [0] + mats
    return lathe(name, prof, (0, 0, 0), (1, 0, 0), seg_mat=lambda i: mats[min(i + 2, len(mats) - 1)] if i >= 0 else mats[1],
                 n=96)


def baffle_mesh(name):
    al = np.arctan2(OUT_C[:, 1], OUT_C[:, 0])
    circ = np.stack([2.2 * np.cos(al), 2.2 * np.sin(al)], -1)
    edge = OUT_C - 0.32 * OUT_N
    rings = []
    for lam, x in [(t, -0.02) for t in (0.0, 0.33, 0.66, 1.0)] + [(1.0, 0.12), (0.5, 0.12), (0.0, 0.12)]:
        yz = (1 - lam) * edge + lam * circ
        rings.append(np.column_stack([np.full(len(yz), x), yz]))
    return surface(name, rings, wrap_rows=True, sharp=30)


def ear_cup(m, parent, name, inside=False, details=False):
    """One ear cup under `parent`; returns the parts as pivots for the exploded views."""
    parts = {}
    for key in ("cap", "shell", "driver", "baffle", "cushion"):
        parts[key] = empty(f"{name} {key}", parent)
    add(f"{name} shell", shell_mesh(f"{name} shell"), [m["shell"], m["interior"]], parts["shell"])
    add(f"{name} cap", cap_mesh(f"{name} cap"), [m["cap"]], parts["cap"])
    add(f"{name} logo", logo_mesh(f"{name} logo"), [m["logo"]], parts["cap"])
    add(f"{name} cushion", cushion_mesh(f"{name} cushion"), [m["cushion"]], parts["cushion"])
    add(f"{name} fabric", fabric_mesh(f"{name} fabric"), [m["fabric"]], parts["cushion"])
    if inside:
        add(f"{name} driver", driver_mesh(f"{name} driver"), [m["dome"], m["cone"], m["rubber"], m["frame"],
                                                            m["magnet"]], parts["driver"])
        add(f"{name} baffle", baffle_mesh(f"{name} baffle"), [m["baffle"]], parts["baffle"])
        for k in range(4):                                  # four of the eight microphones
            a = math.pi / 4 + k * math.pi / 2
            r = 2.68
            c = Vector((-0.07, r * math.cos(a), r * math.sin(a) * 1.05))
            t = Vector((0, -math.sin(a), math.cos(a)))
            rad = Vector((0, math.cos(a), math.sin(a)))
            rbox(f"{name} mic board {k}", (0.08, 0.5, 0.36), c, ((1, 0, 0), t, rad), m["pcb"], parts["baffle"], 0.02)
            can = lathe(f"{name} mic {k}", [(0, 0), (0.12, 0), (0.12, 0.07), (0.1, 0.09), (0, 0.09)],
                        (c.x - 0.04, c.y, c.z), (-1, 0, 0), n=32)
            add(f"{name} mic {k}", can, [m["mic"]], parts["baffle"])
            for s in (-1, 1):
                rbox(f"{name} pad {k}{s}", (0.02, 0.08, 0.06), c + t * (0.18 * s) + rad * 0.1 - Vector((0.04, 0, 0)),
                     ((1, 0, 0), t, rad), m["gold"], parts["baffle"], 0.005)
    if details:                                             # button and status light on the back edge
        al = np.arctan2(OUT_C[:, 1], OUT_C[:, 0])
        for idx_angle, kind in ((-0.62, "button"), (-0.80, "led")):
            j = int(np.argmin(np.abs(np.angle(np.exp(1j * (al - idx_angle))))))
            n2 = OUT_N[j]
            t2 = np.array([-n2[1], n2[0]])
            d = float(np.interp(1.15, catmull(SHELL_OUT, 5)[::-1, 1], catmull(SHELL_OUT, 5)[::-1, 0]))
            p = OUT_C[j] + (d - 0.01) * n2
            c = Vector((1.15, p[0], p[1]))
            axes = ((1, 0, 0), (0, t2[0], t2[1]), (0, n2[0], n2[1]))
            if kind == "button":
                rbox(f"{name} button", (0.2, 0.62, 0.1), c, axes, m["button"], parts["shell"], 0.045)
            else:
                rbox(f"{name} led", (0.07, 0.07, 0.06), c, axes, m["led"], parts["shell"], 0.03)
    return parts


# ---------------------------------------------------------------- yoke, slider, headband
def yoke_path(d=DY, ext=0.05):
    t = np.linspace(-ext, math.pi + ext, 4096)
    C = resample(superellipse(A, B, NEXP, t), 160, closed=False)
    T = tangents(C, closed=False)
    N = np.stack([T[:, 1], -T[:, 0]], -1)
    return C + d * N, T, N


def side(m, root, s, name, inside=False):
    """One side of the headphones (s = +1 right, -1 left, mirrored)."""
    g = empty(name, root)
    g.scale.x = s
    cup = empty(f"{name} cup", g, (CX, 0, 0))
    parts = ear_cup(m, cup, f"{name}", inside=inside, details=(s > 0))
    xy = CX + XY
    P, T, N = yoke_path()
    path = np.column_stack([np.full(len(P), xy), P])
    Bv = np.tile([1.0, 0, 0], (len(P), 1))
    Nv = np.column_stack([np.zeros(len(P)), N])
    prof = rrect(0.30, 0.17, 0.14, 40)
    add(f"{name} yoke", sweep(f"{name} yoke", path, Bv, Nv, lambda k: prof), [m["metal"]], g)
    for sy in (1, -1):                                      # pivots
        hub = lathe(f"{name} hub", [(0, 0), (0.4, 0), (0.4, 0.62), (0.385, 0.69), (0.34, 0.735), (0.21, 0.74),
                                     (0.2, 0.755), (0, 0.758)],
                    (xy, sy * (A - 0.05), 0), (0, sy, 0), seg_mat=lambda i: 1 if i >= 5 else 0, n=56)
        add(f"{name} hub", hub, [m["metal"], m["polished"]], g)
    top = B + DY
    stem = lathe(f"{name} stem", [(0, top - 0.2), (0.4, top - 0.2), (0.4, top + 0.8), (0.385, top + 0.87),
                                  (0.34, top + 0.91), (0, top + 0.915)], (xy, 0, 0), (0, 0, 1), n=56)
    add(f"{name} stem", stem, [m["metal"]], g)
    z0, z1 = top + 0.7, BAND_END_Z + 0.45                   # polished steel slider
    zs = np.linspace(z0, z1, 6)
    path = np.column_stack([np.full(6, xy), np.zeros(6), zs])
    sl = rrect(0.44, 0.085, 0.06, 32)
    add(f"{name} slider", sweep(f"{name} slider", path, np.tile([0, 1.0, 0], (6, 1)), np.tile([1.0, 0, 0], (6, 1)),
                                lambda k: sl), [m["steel"]], g)
    zs = np.linspace(BAND_END_Z - 0.16, BAND_END_Z + 0.3, 5)   # collar where the slider goes into the band
    path = np.column_stack([np.full(5, xy), np.zeros(5), zs])
    col = rrect(1.34, 0.42, 0.32, 48)
    add(f"{name} collar", sweep(f"{name} collar", path, np.tile([0, 1.0, 0], (5, 1)), np.tile([1.0, 0, 0], (5, 1)),
                                lambda k: col, sharp=50), [m["metal"]], g)
    return g, parts


def band_path(n=220):
    t = np.linspace(0, math.pi, 8192)
    c, s = np.cos(t), np.sin(t)
    xe = CX + XY
    P = np.stack([xe * np.sign(c) * np.abs(c) ** (2 / BAND_N), BAND_END_Z + BAND_H * np.abs(s) ** (2 / BAND_N)], -1)
    P = resample(P, n, closed=False)
    T2 = tangents(P, closed=False)
    path = np.column_stack([P[:, 0], np.zeros(n), P[:, 1]])
    T = np.column_stack([T2[:, 0], np.zeros(n), T2[:, 1]])
    Bv = np.tile([0, 1.0, 0], (n, 1))
    Nv = np.cross(Bv, T)                                     # outwards, away from the head
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    return path, Bv, Nv, L


def headband(m, root, name):
    path, Bv, Nv, L = band_path()
    s = L / L[-1]
    w = 1.28 + 0.47 * np.sin(np.pi * s) ** 1.6
    band = sweep(f"{name} band", path, Bv, Nv, lambda k: rrect(w[k], BAND_T, 0.3, 48), sharp=50)
    add(f"{name} band", band, [m["band"]], root)
    # padded underside, rounded ends
    lo, hi = np.searchsorted(s, 0.16), np.searchsorted(s, 0.84)
    idx = np.arange(lo, hi)
    e = np.minimum(L[idx] - L[lo], L[hi - 1] - L[idx])
    f = np.sqrt(np.clip(1 - (1 - np.clip(e / 1.4, 0, 1)) ** 2, 0.02, 1))
    hp = 0.4

    def pad_prof(k):
        pr = superprofile((w[idx[k]] - 0.22) * (0.75 + 0.25 * f[k]), hp * f[k], 2.8, 48)
        return pr + np.array([0.0, -BAND_T - hp * f[k] + 0.05])

    pad = sweep(f"{name} pad", path[idx], Bv[idx], Nv[idx], pad_prof)
    add(f"{name} pad", pad, [m["pad"]], root)


def headphones(cw, name="TACET", inside=False):
    m = materials(cw)
    root = empty(name)
    right, parts_r = side(m, root, 1, f"{name} R", inside)
    left, parts_l = side(m, root, -1, f"{name} L", inside)
    headband(m, root, name)
    return root, {"R": parts_r, "L": parts_l}, m


def single_cup(cw, name="Cup", inside=True):
    m = materials(cw)
    pivot = empty(name)
    cup = empty(f"{name} body", pivot)
    parts = ear_cup(m, cup, name, inside=inside, details=False)
    return pivot, cup, parts


# ---------------------------------------------------------------- light, camera, render
def area_light(name, loc, size, energy, target=(0, 0, 0), size_y=None, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    if size_y:
        data.shape = "RECTANGLE"
        data.size, data.size_y = size, size_y
    else:
        data.size = size
    o = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    o.visible_camera = False
    return o


def world_gradient(bottom, top, strength):
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    coords = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coords.outputs["Generated"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = -0.3, 1.0
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].color = (*([bottom] * 3), 1)
    ramp.color_ramp.elements[1].color = (*([top] * 3), 1)
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = world


def studio_white(t=(0, 0, 4.9), k=1.0):
    area_light("Key", (-62, -70, 62), 70, 30000 * k, t, size_y=50, color=(1.0, 0.975, 0.95))
    area_light("Fill", (78, -44, 12), 80, 9000 * k, t)
    area_light("Top", (0, 8, 92), 64, 15000 * k, t)
    area_light("Rim L", (-58, 56, 26), 10, 9000 * k, t, size_y=90, color=(0.93, 0.96, 1.0))
    area_light("Rim R", (58, 56, 26), 10, 9000 * k, t, size_y=90)
    area_light("Front low", (0, -90, -10), 90, 4000 * k, t, size_y=20)
    world_gradient(0.35, 1.0, 0.55)


def studio_dark(t=(0, 0, 0), k=1.0, back_top=0.0):
    area_light("Key", (-48, -62, 56), 46, 15000 * k, t, color=(1.0, 0.97, 0.94))
    area_light("Rim L", (-54, 48, 22), 8, 20000 * k, t, size_y=80, color=(0.86, 0.92, 1.0))
    area_light("Rim R", (54, 48, 22), 8, 17000 * k, t, size_y=80, color=(1.0, 0.95, 0.9))
    area_light("Top", (0, 12, 82), 40, 9000 * k, t)
    area_light("Front strip", (30, -70, -8), 70, 4000 * k, t, size_y=8)
    if back_top:                                            # lights the upward faces in the stacked view
        area_light("Back top", (0, 70, 42), 64, back_top * k, t)
    world_gradient(0.0, 0.04, 1.0)


def studio_cushion(t=(0, 0, 0), k=1.0):
    """Raking light for the close-up: shows the pillow shape and the grain of the leather."""
    area_light("Key", (-30, -22, 34), 22, 13000 * k, t, color=(1.0, 0.97, 0.93))
    area_light("Fill", (40, -40, 6), 60, 3200 * k, t)
    area_light("Rim", (26, 40, 30), 8, 7000 * k, t, size_y=50, color=(0.95, 0.97, 1.0))
    area_light("Top", (0, 10, 70), 50, 4500 * k, t)
    world_gradient(0.4, 1.0, 0.5)


def floor(z=FLOOR_Z):
    me = bpy.data.meshes.new("Floor")
    s = 400
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    o = add("Floor", me, [mat_plain("floor", (0.85, 0.85, 0.85, 1), 0.6)])
    o.is_shadow_catcher = True
    return o


def camera(target, dist, elev, azim=0.0, lens=85.0, dof=None):
    cd = bpy.data.cameras.new("Camera")
    cd.lens, cd.sensor_width = lens, 36
    cd.clip_start, cd.clip_end = 1.0, 2000.0
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.scene.collection.objects.link(cam)
    el, az = math.radians(elev), math.radians(azim)
    t = Vector(target)
    cam.location = t + Vector((dist * math.cos(el) * math.sin(az), -dist * math.cos(el) * math.cos(az),
                               dist * math.sin(el)))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    if dof:
        cd.dof.use_dof = True
        cd.dof.focus_distance, cd.dof.aperture_fstop = dof
    bpy.context.scene.camera = cam
    return cam


def render_settings(res, samples, threshold=0.02):
    sc = bpy.context.scene
    sc.unit_settings.scale_length = 0.01
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = threshold
    c.use_denoising = True
    try:
        c.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 8, 3, 5
    c.transmission_bounces, c.transparent_max_bounces = 4, 8
    c.caustics_reflective = c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    c.blur_glossy = 0.6
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    st = sc.render.image_settings
    st.file_format, st.color_mode, st.color_depth = "PNG", "RGBA", "8"
    st.compression = 30
    vs = sc.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = 0.0


def use_gpu():
    sc = bpy.context.scene
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
            sc.cycles.device = "GPU"
            return kind
    return "CPU"


def render_to(path, skip=False):
    path = os.path.abspath(path)
    if skip and os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"skip {path}", flush=True)
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f"wrote {path} in {time.time() - t0:.1f}s", flush=True)
    return True


# ---------------------------------------------------------------- shots
EXPLODE = {"cap": 5.0, "shell": 0.0, "driver": -4.6, "baffle": -8.6, "cushion": -13.0}
ANCHORS = {"cap": (2.45, B - 0.72), "shell": (1.2, B + 0.06), "driver": (0.9, 2.44), "baffle": (0.05, B - 0.32),
           "cushion": (-1.0, B - 0.06)}


def set_explode(cup, parts, e, axis_shift=True):
    s = float(smooth01(e))
    for key, d in EXPLODE.items():
        parts[key].location.x = d * s
    if axis_shift:
        cup.location.x = -0.29 - 0.5 * (EXPLODE["cap"] + EXPLODE["cushion"]) * s


def anchors(cam, parts):
    bpy.context.view_layer.update()
    sc = bpy.context.scene
    out = {}
    for key, (x, z) in ANCHORS.items():
        w = parts[key].matrix_world @ Vector((x, 0.0, z + 0.35))
        p = world_to_camera_view(sc, cam, w)
        out[key] = [round(p.x, 4), round(1 - p.y, 4)]
    return out


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--shot", default="still")
    p.add_argument("--colour", default="bone")
    p.add_argument("--out", required=True, help="file for a still, folder for a sequence")
    p.add_argument("--frames", type=int, default=72)
    p.add_argument("--only", default="")
    p.add_argument("--res", default="")
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--yaw", type=float, default=-30.0)
    p.add_argument("--elev", type=float, default=10.0)
    p.add_argument("--explode", type=float, default=0.0)
    p.add_argument("--light", type=float, default=1.0)
    p.add_argument("--exposure", type=float, default=0.0)
    p.add_argument("--gpu", action="store_true")
    p.add_argument("--skip", action="store_true", help="keep frames that already exist")
    p.add_argument("--blend", default="")
    p.add_argument("--cam", default="", help="override: tx,ty,tz,dist,elev,azim,lens[,fstop]")
    p.add_argument("--layout", default="c")
    p.add_argument("--rot", default="", help="override for the single-cup shots: rx,ry,rz in degrees")
    a = p.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shot = a.shot

    if shot in ("still", "look"):
        root, _, _ = headphones(a.colour)
        cam = camera((0, 0, 4.9), 56, a.elev, lens=85)
        studio_white(k=a.light)
        floor()
        render_settings(tuple(int(v) for v in (a.res or "1000x1000").split("x")), a.samples)
    elif shot == "hero":
        layout = {
            "a": [("bone", -15.0, 9.0, -32.0), ("obsidian", 0.0, 0.0, -32.0), ("moss", 15.0, -9.0, -32.0)],
            "b": [("bone", -15.5, 8.0, -52.0), ("obsidian", 0.0, -1.0, -28.0), ("moss", 15.5, 8.0, -6.0)],
            "c": [("moss", -16.0, 10.0, 34.0), ("obsidian", 0.0, -2.0, -6.0), ("bone", 16.0, 10.0, -40.0)],
        }[a.layout]
        for cw, x, y, yaw in layout:
            r, _, _ = headphones(cw, f"TACET {cw}")
            r.location = (x, y, 0)
            r.rotation_euler.z = math.radians(yaw)
        cam = camera((0, 3, 4.6), 134, 7.5, lens=85)
        studio_white(t=(0, 3, 4.6), k=a.light)
        floor()
        render_settings(tuple(int(v) for v in (a.res or "2400x1200").split("x")), a.samples)
    elif shot == "explode":
        pivot, cup, parts = single_cup(a.colour)
        cam = camera((0, 0, 0.3), 52, 12.0, lens=70)
        studio_dark(k=a.light)
        render_settings(tuple(int(v) for v in (a.res or "1600x1000").split("x")), a.samples)
    elif shot == "layers":
        pivot, cup, parts = single_cup(a.colour)
        pivot.rotation_euler = (0, math.radians(90), math.radians(-28))
        for key, d in EXPLODE.items():
            parts[key].location.x = d * 0.82
        cup.location.x = -0.29 - 0.5 * (EXPLODE["cap"] + EXPLODE["cushion"]) * 0.82
        cam = camera((0, 0, 1.2), 45, 28.0, lens=70)
        studio_dark(k=a.light, back_top=9000)
        render_settings(tuple(int(v) for v in (a.res or "900x1300").split("x")), a.samples)
    elif shot == "cushion":
        pivot, cup, parts = single_cup(a.colour, inside=False)
        pivot.rotation_euler = (math.radians(-14), 0, math.radians(118))
        cam = camera((0.6, -1.2, 0.6), 24, 30.0, azim=-10, lens=100, dof=(24.0, 4.0))
        cushion_light = True
        if a.rot:
            pivot.rotation_euler = [math.radians(float(v)) for v in a.rot.split(",")]
        if a.cam:
            v = [float(x) for x in a.cam.split(",")]
            bpy.data.objects.remove(cam)
            cam = camera(v[:3], v[3], v[4], azim=v[5], lens=v[6], dof=(v[3], v[7]) if len(v) > 7 else None)
        studio_cushion(k=a.light)
        floor(-4.6)
        render_settings(tuple(int(v) for v in (a.res or "900x1200").split("x")), a.samples)
    else:
        raise SystemExit(f"unknown shot {shot}")
    bpy.context.scene.view_settings.exposure = a.exposure
    device = use_gpu() if a.gpu else "CPU"
    print(f"shot {shot} {a.colour} device {device}", flush=True)
    if a.blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.blend))

    if shot == "still":
        root.rotation_euler.z = math.radians(a.yaw)
        render_to(a.out)
    elif shot == "look":
        lo, hi = (int(v) for v in a.only.split(":")) if a.only else (0, a.frames)
        for i in range(lo, min(hi, a.frames)):
            root.rotation_euler.z = math.radians(a.yaw + 360.0 * i / a.frames)
            render_to(os.path.join(a.out, f"look_{a.colour}_{i:03d}.png"), a.skip)
            print(f"frame {i + 1}/{a.frames}", flush=True)
    elif shot == "explode":
        n = a.frames
        plan = []
        for i in range(n):
            e = i / (n - 1) if n > 1 else a.explode
            plan.append((e, 157.0 - 11.0 * float(smooth01(e))))
        tags = []
        for e, yaw in plan:
            pivot.rotation_euler.z = math.radians(yaw)
            set_explode(cup, parts, e)
            tags.append(anchors(cam, parts))
        os.makedirs(os.path.abspath(a.out), exist_ok=True)
        with open(os.path.join(os.path.abspath(a.out), "anchors.json"), "w") as fh:
            json.dump({"frames": n, "anchors": tags}, fh)
        lo, hi = (int(v) for v in a.only.split(":")) if a.only else (0, n)
        for i in range(lo, min(hi, n)):
            e, yaw = plan[i]
            pivot.rotation_euler.z = math.radians(yaw)
            set_explode(cup, parts, e)
            render_to(os.path.join(a.out, f"explode_{i:03d}.png"), a.skip)
            print(f"frame {i + 1}/{n}", flush=True)
    else:
        render_to(a.out, a.skip)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(argv)
