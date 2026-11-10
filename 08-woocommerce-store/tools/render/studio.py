"""
Ombra product renders: procedural candle packaging, a plaster studio with a window shadow, Cycles.

Run with the Blender Python module:
    bvenv/bin/python studio.py <shot> [--res 1200] [--samples 160] [--out out/]
"""
import argparse
import math
import random
import sys
from pathlib import Path

import bpy  # noqa: I001  (bpy must come first: it makes bmesh and mathutils importable)
import bmesh
from mathutils import Euler, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels  # noqa: E402

LABELS = HERE / "labels"
LABELS.mkdir(exist_ok=True)


def srgb(hex_color: str, alpha: float = 1.0):
    """Hex sRGB colour to the linear RGBA Blender expects."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)


# ----------------------------------------------------------------------------- scene basics


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_object(name, verts, faces, smooth=True, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    obj = link(bpy.data.objects.new(name, me))
    if mat:
        obj.data.materials.append(mat)
    return obj


def arc(cx, cz, r, a0, a1, n=6):
    """Points on a quarter-ish arc in the (radius, z) profile plane, angles in degrees."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def lathe(name, profile, segments=128, mat=None, smooth=True):
    """Revolve a (radius, z) profile around Z. Points with radius 0 become poles."""
    verts, rings = [], []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for s in range(segments):
                a = 2 * math.pi * s / segments
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    faces = []
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for s in range(segments):
                faces.append((a[0], b[s], b[(s + 1) % segments]))
        elif len(b) == 1:
            for s in range(segments):
                faces.append((a[s], a[(s + 1) % segments], b[0]))
        else:
            for s in range(segments):
                faces.append((a[s], a[(s + 1) % segments], b[(s + 1) % segments], b[s]))
    return mesh_object(name, verts, faces, smooth, mat)


def box(name, sx, sy, sz, mat=None, bevel=0.0, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        mod = obj.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 4
        mod.limit_method = "NONE"
        for p in obj.data.polygons:
            p.use_smooth = True
        obj.data.set_sharp_from_angle(angle=math.radians(35))
    if mat:
        obj.data.materials.append(mat)
    return obj


def band(name, radius, angle_deg, z0, height, mat, center_deg=-90.0, segments=64, rows=8):
    """A label wrapped around a cylinder: UV u runs around, v runs up. radius may be a function of z."""
    verts, faces = [], []
    a0 = math.radians(center_deg - angle_deg / 2)
    a1 = math.radians(center_deg + angle_deg / 2)
    for j in range(rows + 1):
        z = z0 + height * j / rows
        r = radius(z) if callable(radius) else radius
        for i in range(segments + 1):
            a = a0 + (a1 - a0) * i / segments
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for j in range(rows):
        for i in range(segments):
            k = j * (segments + 1) + i
            faces.append((k, k + 1, k + segments + 2, k + segments + 1))  # normal points outwards
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            j, i = divmod(vi, segments + 1)
            uv.data[li].uv = (i / segments, j / rows)
    obj = link(bpy.data.objects.new(name, me))
    obj.data.materials.append(mat)
    return obj


def disc(name, radius, z, mat, segments=96):
    """Flat round label facing up, UV mapped to the square label image."""
    verts = [(0, 0, z)] + [(radius * math.cos(2 * math.pi * i / segments), radius * math.sin(2 * math.pi * i / segments), z) for i in range(segments)]
    faces = [(0, i + 1, (i + 1) % segments + 1) for i in range(segments)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, _ = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.5 + x / (2 * radius), 0.5 + y / (2 * radius))
    obj = link(bpy.data.objects.new(name, me))
    obj.data.materials.append(mat)
    return obj


def curve_tube(name, points, radius, mat, resolution=12):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    sp.resolution_u = resolution
    obj = link(bpy.data.objects.new(name, cu))
    obj.data.materials.append(mat)
    return obj


def parent_all(objs, name):
    root = link(bpy.data.objects.new(name, None))
    for o in objs:
        o.parent = root
    return root


# ----------------------------------------------------------------------------- materials


def material(name, **inputs):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat


def nodes(mat):
    return mat.node_tree.nodes, mat.node_tree.links


def plaster(name="plaster", color="#E3D9CC", bump=0.08, scale=60.0):
    mat = material(name, **{"Base Color": srgb(color), "Roughness": 0.92})
    n, l = nodes(mat)
    bsdf = n["Principled BSDF"]
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8
    noise.inputs["Roughness"].default_value = 0.6
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 3.0
    big.inputs["Detail"].default_value = 3
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = srgb(color)
    r, g, b, _ = srgb(color)
    mix.inputs["B"].default_value = (r * 0.93, g * 0.92, b * 0.9, 1)
    l.new(big.outputs["Fac"], mix.inputs["Factor"])
    l.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.0005
    l.new(noise.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def travertine(name="travertine"):
    mat = material(name, **{"Base Color": srgb("#D9CDBB"), "Roughness": 0.78})
    n, l = nodes(mat)
    bsdf = n["Principled BSDF"]
    coord = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 6.0, 1.0)
    l.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = n.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 9
    wave.inputs["Distortion"].default_value = 6
    wave.inputs["Detail"].default_value = 6
    l.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#CDBFAA")
    ramp.color_ramp.elements[1].color = srgb("#E2D8C8")
    l.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    pores = n.new("ShaderNodeTexVoronoi")
    pores.inputs["Scale"].default_value = 180
    l.new(coord.outputs["Object"], pores.inputs["Vector"])
    pr = n.new("ShaderNodeMapRange")
    pr.inputs["From Min"].default_value = 0.0
    pr.inputs["From Max"].default_value = 0.08
    l.new(pores.outputs["Distance"], pr.inputs["Value"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.25
    bmp.inputs["Distance"].default_value = 0.0004
    l.new(pr.outputs["Result"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def see_through_shadows(mat, tint):
    """Without caustics glass would cast a solid shadow; let shadow rays pass, tinted like the glass."""
    n, l = nodes(mat)
    out = n["Material Output"]
    bsdf = n["Principled BSDF"]
    lp = n.new("ShaderNodeLightPath")
    tr = n.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = srgb(tint)
    mix = n.new("ShaderNodeMixShader")
    l.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    l.new(bsdf.outputs["BSDF"], mix.inputs[1])
    l.new(tr.outputs["BSDF"], mix.inputs[2])
    l.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def glass(name, tint="#FFFFFF", roughness=0.015):
    mat = material(
        name,
        **{"Base Color": srgb(tint), "Transmission Weight": 1.0, "Roughness": roughness, "IOR": 1.5, "Specular IOR Level": 0.5},
    )
    return see_through_shadows(mat, tint)


def liquid(name, tint, ior):
    mat = material(name, **{"Base Color": srgb(tint), "Transmission Weight": 1.0, "Roughness": 0.0, "IOR": ior})
    return see_through_shadows(mat, tint)


def wax(name="wax", color="#EFE6D8"):
    return material(
        name,
        **{
            "Base Color": srgb(color),
            "Roughness": 0.45,
            "Subsurface Weight": 1.0,
            "Subsurface Radius": (1.0, 0.72, 0.5),
            "Subsurface Scale": 0.006,
            "Specular IOR Level": 0.4,
        },
    )


def label_material(name, image_path, roughness=0.6):
    mat = material(name, **{"Roughness": max(roughness, 0.72), "Specular IOR Level": 0.12})
    n, l = nodes(mat)
    bsdf = n["Principled BSDF"]
    tex = n.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image_path), check_existing=True)
    tex.interpolation = "Cubic"
    # The back of a label seen through glass is plain paper
    geo = n.new("ShaderNodeNewGeometry")
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["B"].default_value = srgb("#E9E0D2")
    l.new(tex.outputs["Color"], mix.inputs["A"])
    l.new(geo.outputs["Backfacing"], mix.inputs["Factor"])
    l.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return mat


def wood(name="ash", color_a="#C9AE8C", color_b="#A88A66"):
    mat = material(name, **{"Roughness": 0.62})
    n, l = nodes(mat)
    bsdf = n["Principled BSDF"]
    coord = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 9.0, 1.0)
    l.new(coord.outputs["Object"], mapping.inputs["Vector"])
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.inputs["Scale"].default_value = 38
    wave.inputs["Distortion"].default_value = 9
    wave.inputs["Detail"].default_value = 4
    l.new(mapping.outputs["Vector"], wave.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb(color_b)
    ramp.color_ramp.elements[1].color = srgb(color_a)
    l.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.08
    l.new(wave.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def metal(name, color="#C8C4BE", roughness=0.32, brushed=True):
    mat = material(name, **{"Base Color": srgb(color), "Metallic": 1.0, "Roughness": roughness})
    if brushed:
        n, l = nodes(mat)
        bsdf = n["Principled BSDF"]
        bsdf.inputs["Anisotropic"].default_value = 0.6
        noise = n.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 900
        coord = n.new("ShaderNodeTexCoord")
        mapping = n.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1, 1, 0.02)
        l.new(coord.outputs["Object"], mapping.inputs["Vector"])
        l.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        bmp = n.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = 0.04
        l.new(noise.outputs["Fac"], bmp.inputs["Height"])
        l.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def terracotta(name="terracotta"):
    mat = material(name, **{"Base Color": srgb("#B36A47"), "Roughness": 0.85})
    n, l = nodes(mat)
    bsdf = n["Principled BSDF"]
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 140
    noise.inputs["Detail"].default_value = 10
    big = n.new("ShaderNodeTexNoise")
    big.inputs["Scale"].default_value = 12
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("#94482A")
    ramp.color_ramp.elements[1].color = srgb("#B0603B")
    l.new(big.outputs["Fac"], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.35
    bmp.inputs["Distance"].default_value = 0.0006
    l.new(noise.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def emission(name, color, strength):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    n, l = nodes(mat)
    for node in list(n):
        if node.type != "OUTPUT_MATERIAL":
            n.remove(node)
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = srgb(color)
    em.inputs["Strength"].default_value = strength
    l.new(em.outputs["Emission"], n["Material Output"].inputs["Surface"])
    return mat


def flame_material():
    """Candle flame: bright yellow-white core, orange edges, faint blue base, by height and facing."""
    mat = bpy.data.materials.new("flame")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    n, l = nodes(mat)
    for node in list(n):
        if node.type != "OUTPUT_MATERIAL":
            n.remove(node)
    coord = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(coord.outputs["Generated"], sep.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.10, 0.18, 0.9, 1)
    cr.elements[1].position = 0.16
    cr.elements[1].color = (1.0, 0.55, 0.12, 1)
    e = cr.elements.new(0.45)
    e.color = (1.0, 0.86, 0.55, 1)
    e = cr.elements.new(0.92)
    e.color = (1.0, 0.45, 0.08, 1)
    l.new(sep.outputs["Z"], ramp.inputs["Fac"])
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    soft = n.new("ShaderNodeMath")
    soft.operation = "POWER"
    soft.inputs[1].default_value = 1.6
    l.new(lw.outputs["Facing"], soft.inputs[0])
    core = n.new("ShaderNodeMath")
    core.operation = "SUBTRACT"
    core.inputs[0].default_value = 1.0
    l.new(soft.outputs["Value"], core.inputs[1])
    em = n.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 38.0
    l.new(ramp.outputs["Color"], em.inputs["Color"])
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    l.new(core.outputs["Value"], mix.inputs["Fac"])
    l.new(tr.outputs["BSDF"], mix.inputs[1])
    l.new(em.outputs["Emission"], mix.inputs[2])
    l.new(mix.outputs["Shader"], n["Material Output"].inputs["Surface"])
    return mat


# ----------------------------------------------------------------------------- products

GLASS_TINTS = {"fig": "#EDC594", "salt": "#D3DDCD", "amber": "#9A938D"}
LIQUID_TINTS = {"fig": "#E7B66E", "salt": "#E9E3C2", "amber": "#C98E52"}


def wick(z_top_wax, lit=False, height=0.0095, bend=0.0016):
    cotton = material("cotton", **{"Base Color": srgb("#E4DACB"), "Roughness": 0.9})
    char = material("char", **{"Base Color": srgb("#1E1A17"), "Roughness": 0.8})
    h = height * (0.75 if lit else 1.0)
    pts = [(0, 0, z_top_wax - 0.002), (0, 0, z_top_wax + h * 0.5), (bend, 0.0004, z_top_wax + h)]
    body = curve_tube("wick", pts, 0.00075, cotton)
    tip_len = 0.0045 if lit else 0.002
    tip = curve_tube(
        "wick_tip",
        [(bend * 0.82, 0.0003, z_top_wax + h - tip_len), (bend, 0.0004, z_top_wax + h), (bend * 1.05, 0.0004, z_top_wax + h + 0.0006)],
        0.0008,
        char,
    )
    parts = [body, tip]
    if lit:
        parts += flame((bend, 0.0004, z_top_wax + h - 0.002))
    return parts


def flame(base):
    L, R = 0.024, 0.0052
    prof = [(0.0, 0.0)]
    for i in range(1, 25):
        t = i / 24
        prof.append((max(0.0001, R * math.sin(math.pi * (t ** 0.72)) ** 0.8 * (1 - 0.35 * t)), L * t))
    prof.append((0.0, L * 1.02))
    fl = lathe("flame", prof, 48, flame_material())
    fl.location = base
    fl.visible_shadow = False
    try:
        fl.visible_diffuse = False
    except Exception:
        pass
    light = bpy.data.lights.new("flame_light", "POINT")
    light.energy = 0.42
    light.shadow_soft_size = 0.004
    light.color = (1.0, 0.62, 0.30)
    lo = link(bpy.data.objects.new("flame_light", light))
    lo.location = (base[0], base[1], base[2] + 0.011)
    glow = bpy.data.lights.new("flame_glow", "POINT")
    glow.energy = 0.2
    glow.shadow_soft_size = 0.012
    glow.color = (1.0, 0.55, 0.25)
    go = link(bpy.data.objects.new("flame_glow", glow))
    go.location = (base[0], base[1], base[2] + 0.018)
    return [fl, lo, go]


def jar_candle(scent="fig", size="200", lit=False, lid="side"):
    """Straight glass tumbler with wax, wick, wrapped paper label and an optional ash lid."""
    R, H = (0.0375, 0.088) if size == "200" else (0.0465, 0.104)
    T, B = 0.0042, 0.0085
    g = glass(f"glass_{scent}", GLASS_TINTS[scent])
    prof = [(0, 0)]
    prof += arc(R - 0.004, 0.004, 0.004, -90, 0, 5)
    prof += [(R, H - 0.002)]
    prof += arc(R - 0.0021, H - 0.0021, 0.0021, 0, 180, 8)
    prof += [(R - T, B + 0.003)]
    prof += arc(R - T - 0.003, B + 0.003, 0.003, 0, -90, 5)
    prof += [(0, B)]
    jar = lathe("jar", prof, 160, g)
    wax_top = H - (0.017 if size == "200" else 0.019)
    if lit:
        wax_top -= 0.004
    wr = R - T - 0.00015
    wprof = [(0, B + 0.0003), (wr, B + 0.0003), (wr, wax_top + 0.0012)]
    wprof += arc(wr - 0.0018, wax_top + 0.0012, 0.0018, 0, 75, 4)
    wprof += [(wr * 0.5, wax_top - 0.0002), (0, wax_top - 0.0006 if not lit else wax_top - 0.0015)]
    wx = lathe("wax", wprof, 128, wax())
    parts = [jar, wx]
    if lit:
        pool = material("melt", **{"Base Color": srgb("#E6D7BE"), "Roughness": 0.08, "Subsurface Weight": 1.0, "Subsurface Radius": (1, 0.7, 0.45), "Subsurface Scale": 0.01})
        mp = lathe("melt_pool", [(0, wax_top - 0.0013), (wr * 0.62, wax_top - 0.0011), (wr * 0.66, wax_top - 0.0016), (0, wax_top - 0.003)], 96, pool)
        parts.append(mp)
    parts += wick(wax_top - (0.0006 if not lit else 0.0015), lit)
    weight = "200 G / 7 OZ" if size == "200" else "400 G / 14 OZ"
    lab_w, lab_h = R * math.radians(92), (0.038 if size == "200" else 0.046)
    lp = LABELS / f"jar-{scent}-{size}.png"
    labels.jar_label(scent, weight, lab_w, lab_h, lp)
    z0 = (H - lab_h) / 2 - 0.004
    parts.append(band("label", R + 0.00025, 92, z0, lab_h, label_material(f"label_{scent}{size}", lp)))
    if lid == "side":
        lid_obj = ash_lid(R + 0.0008)
        lid_obj.location = (R * 2.35, R * 0.9, 0)
        lid_obj.rotation_euler = (0, 0, math.radians(20))
        parts.append(lid_obj)
    root = parent_all(parts, f"jar_{scent}_{size}")
    return root, H


def ash_lid(r):
    w = wood()
    prof = [(0, 0)] + arc(r - 0.002, 0.002, 0.002, -90, 0, 4) + arc(r - 0.002, 0.012, 0.002, 0, 90, 4) + [(0, 0.014)]
    top = lathe("lid", prof, 128, w)
    gasket_mat = material("gasket", **{"Base Color": srgb("#D8CFC2"), "Roughness": 0.7})
    gasket = lathe("gasket", [(0, -0.0001), (r - 0.0052, -0.0001), (r - 0.0052, 0.0001), (0, 0.0001)], 96, gasket_mat)
    gasket.parent = top
    # lid lies upside down next to the jar: flip so the gasket faces up
    return top


def vessel_candle(lit=False):
    """Hand-thrown terracotta bowl candle."""
    t = terracotta()
    R, H, foot = 0.058, 0.062, 0.031

    def r_out(z):
        return foot + (R - foot) * math.sin(math.pi / 2 * min(1.0, max(0.0, z / H))) ** 0.7

    def r_in(z):
        return r_out(z) - 0.0068

    prof = [(0, 0), (foot - 0.004, 0)] + arc(foot - 0.004, 0.004, 0.004, -90, 0, 4)
    prof += [(r_out(z), z) for z in [0.006 + (H - 0.009) * i / 16 for i in range(1, 17)]]
    prof += arc(r_out(H) - 0.0034, H - 0.003, 0.0034, 0, 170, 6)
    prof += [(r_in(z), z) for z in [0.013 + (H - 0.017) * i / 14 for i in range(14, -1, -1)]]
    prof += [(0, 0.012)]
    bowl = lathe("vessel", prof, 160, t)
    disp = bowl.modifiers.new("wobble", "DISPLACE")
    tex = bpy.data.textures.new("wobble", "CLOUDS")
    tex.noise_scale = 0.05
    disp.texture = tex
    disp.strength = 0.0010
    disp.mid_level = 0.5
    wax_top = H - 0.016 - (0.004 if lit else 0)
    zs = [0.0125 + (wax_top - 0.0125) * i / 8 for i in range(9)]
    wprof = [(0, 0.0125)] + [(r_in(z) - 0.0002, z) for z in zs] + [(0, wax_top - 0.0008)]
    wx = lathe("wax", wprof, 128, wax())
    parts = [bowl, wx]
    parts += wick(wax_top - 0.0008, lit)
    sticker = LABELS / "vessel.png"
    labels.band_label(
        [("mark", "OMBRA", 18, 22, None), ("italic", "Ember", 45, 26, None), ("caps", "NO. 04", 79, 10, 0.2)],
        0.034, 0.021, sticker,
    )
    parts.append(band("label", lambda z: r_out(z) + 0.0012, 36, 0.024, 0.021, label_material("label_vessel", sticker)))
    root = parent_all(parts, "vessel")
    return root, H


def travel_tin(scent="fig"):
    """Open brushed aluminium tin with its lid leaning against it."""
    R, H = 0.036, 0.042
    m = metal("aluminium", "#CFCAC2", 0.3)
    prof = [(0, 0)] + arc(R - 0.002, 0.002, 0.002, -90, 0, 4)
    prof += [(R, H - 0.0015)] + arc(R - 0.0012, H - 0.0012, 0.0012, 0, 180, 6) + [(R - 0.0024, 0.003), (0, 0.003)]
    tin = lathe("tin", prof, 160, m)
    wax_top = H - 0.008
    wx = lathe("wax", [(0, 0.0032), (R - 0.0025, 0.0032), (R - 0.0025, wax_top + 0.0008), (R - 0.004, wax_top), (0, wax_top - 0.0004)], 128, wax())
    parts = [tin, wx] + wick(wax_top - 0.0004, False, height=0.008)
    LR = R + 0.0012
    lid_prof = [(0, 0)] + arc(LR - 0.0015, 0.0015, 0.0015, -90, 0, 4) + [(LR, 0.011)] + arc(LR - 0.001, 0.011, 0.001, 0, 180, 5) + [(LR - 0.0006, 0.0006), (0, 0.0006)]
    lid = lathe("tin_lid", lid_prof, 160, m)
    s = labels.SCENTS[scent]
    lp = LABELS / f"tin-{scent}.png"
    labels.round_label(
        [("mark", "OMBRA", 24, 9.5, None), ("italic", s["name"], 42, 11 if len(s["name"]) < 13 else 9.5, None),
         ("dot", "", 62, 1.1, None), ("caps", "TRAVEL CANDLE", 68, 4.6, 0.2), ("caps", "80 G / 2.8 OZ", 76, 4.2, 0.16)],
        2 * (LR - 0.003), lp,
    )
    lab = disc("tin_label", LR - 0.003, 0.00018, label_material(f"label_tin_{scent}", lp, 0.5))
    lab.rotation_euler = (math.pi, 0, 0)
    lab.parent = lid
    # lid stands on its rim behind the tin, label facing the camera
    lid.rotation_euler = (math.radians(-106), 0, 0)
    lid.location = (0.014, R + 0.018, LR * 0.962 + 0.0012)
    parts.append(lid)
    root = parent_all(parts, f"tin_{scent}")
    return root, 0.085


def reed_diffuser(scent="fig"):
    R, H = 0.031, 0.118
    g = glass(f"dglass_{scent}", "#F4F1EC" if scent != "amber" else "#C9C3BC")
    neck_r, neck_h = 0.0105, 0.016
    prof = [(0, 0)] + arc(R - 0.005, 0.005, 0.005, -90, 0, 5) + [(R, H - 0.022)]
    prof += arc(R - 0.016, H - 0.022, 0.016, 0, 90, 8)[:-1]
    prof += [(neck_r, H - 0.006), (neck_r, H + neck_h - 0.001)] + arc(neck_r - 0.001, H + neck_h - 0.001, 0.001, 0, 180, 4)
    prof += [(neck_r - 0.0035, H - 0.004), (R - 0.004, H - 0.026), (R - 0.004, 0.012), (0, 0.012)]
    bottle = lathe("bottle", prof, 160, g)
    liquid_mat = liquid(f"liquid_{scent}", LIQUID_TINTS[scent], 1.40)
    lv = 0.074
    liquid_obj = lathe("liquid", [(0, 0.0122), (R - 0.0042, 0.0122), (R - 0.0042, lv), (0, lv)], 128, liquid_mat)
    z0, z1 = H + neck_h - 0.005, H + neck_h + 0.001
    collar = lathe("collar", [(neck_r + 0.0003, z0), (neck_r + 0.0024, z0), (neck_r + 0.0024, z1), (neck_r + 0.0003, z1), (neck_r + 0.0003, z0)], 96, wood("collar", "#5B4636", "#3F2F24"))
    parts = [bottle, liquid_obj, collar]
    rattan = material("rattan", **{"Base Color": srgb("#3B2C22"), "Roughness": 0.85})
    rng = random.Random(4)
    pivot_z = H + neck_h
    for i in range(8):
        az = 2 * math.pi * i / 8 + rng.uniform(-0.3, 0.3)
        tilt = math.radians(rng.uniform(4, 12))
        d = Vector((math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), math.cos(tilt)))
        pivot = Vector((0.0035 * math.cos(az + 2.0), 0.0035 * math.sin(az + 2.0), pivot_z))
        below = (pivot_z - 0.016) / math.cos(tilt)
        above = rng.uniform(0.17, 0.2)
        p0, p1 = pivot - d * below, pivot + d * above
        parts.append(curve_tube(f"reed{i}", [tuple(p0), tuple(pivot), tuple(p1)], 0.0016, rattan, 4))
    s = labels.SCENTS[scent]
    lp = LABELS / f"diffuser-{scent}.png"
    labels.band_label(
        [("mark", "OMBRA", 10, 12.5, None), ("rule", "", 28, 8, None), ("italic", s["name"], 33, 13 if len(s["name"]) < 13 else 11.5, None),
         ("caps", "REED DIFFUSER", 58, 5.4, 0.22), ("dot", "", 71, 1.0, None), ("caps", f"NO. {s['no']}  ·  100 ML", 77, 5, 0.16)],
        R * math.radians(100), 0.052, lp,
    )
    parts.append(band("label", R + 0.00025, 100, 0.024, 0.052, label_material(f"label_d_{scent}", lp)))
    root = parent_all(parts, f"diffuser_{scent}")
    return root, 0.36


def room_spray(scent="fig"):
    R, H = 0.024, 0.112
    g = glass(f"sglass_{scent}", "#F6F3EE" if scent != "amber" else "#B8B0A8")
    prof = [(0, 0)] + arc(R - 0.004, 0.004, 0.004, -90, 0, 5) + [(R, H - 0.012)] + arc(R - 0.012, H - 0.012, 0.012, 0, 90, 8)[:-1]
    prof += [(0.0085, H), (0.0085, H + 0.006), (0.0055, H + 0.006), (0.0055, H - 0.002), (R - 0.0035, H - 0.014), (R - 0.0035, 0.009), (0, 0.009)]
    bottle = lathe("spray_bottle", prof, 160, g)
    liquid_mat = liquid(f"sliquid_{scent}", LIQUID_TINTS[scent], 1.36)
    liquid_obj = lathe("liquid", [(0, 0.0092), (R - 0.0037, 0.0092), (R - 0.0037, 0.082), (0, 0.082)], 128, liquid_mat)
    brass = metal("brass", "#B89B6A", 0.28, brushed=False)
    collar = lathe("crimp", [(0, H - 0.001), (0.0098, H - 0.001)] + arc(0.0094, H + 0.006, 0.0006, 0, 90, 3) + [(0, H + 0.0068)], 96, brass)
    stem = lathe("stem", [(0, H + 0.006), (0.0022, H + 0.006), (0.0022, H + 0.012), (0, H + 0.012)], 48, brass)
    act_mat = material("actuator", **{"Base Color": srgb("#1F1C1A"), "Roughness": 0.4})
    actuator = lathe("actuator", [(0, H + 0.011)] + arc(0.0074, H + 0.0125, 0.0015, -90, 0, 3) + [(0.0089, H + 0.024)] + arc(0.0074, H + 0.024, 0.0015, 0, 90, 3) + [(0, H + 0.0255)], 96, act_mat)
    nozzle = lathe("nozzle", [(0, -0.0005), (0.0011, -0.0005), (0.0011, 0.0005), (0, 0.0005)], 24, emission("hole", "#000000", 0))
    nozzle.rotation_euler = (math.radians(90), 0, 0)
    nozzle.location = (0, -0.0089, H + 0.019)
    tube_mat = material("diptube", **{"Base Color": srgb("#F2F2F2"), "Transmission Weight": 0.8, "Roughness": 0.2})
    tube = curve_tube("diptube", [(0, 0, H), (0.001, 0, H * 0.5), (0.003, 0, 0.011)], 0.0011, tube_mat, 4)
    parts = [bottle, liquid_obj, collar, stem, actuator, nozzle, tube]
    s = labels.SCENTS[scent]
    lp = LABELS / f"spray-{scent}.png"
    labels.band_label(
        [("mark", "OMBRA", 10, 12.5, None), ("rule", "", 28, 8, None), ("italic", s["name"], 33, 13 if len(s["name"]) < 13 else 11, None),
         ("caps", "ROOM SPRAY", 58, 5.6, 0.22), ("dot", "", 71, 1.0, None), ("caps", f"NO. {s['no']}  ·  100 ML", 77, 5, 0.16)],
        R * math.radians(120), 0.05, lp,
    )
    parts.append(band("label", R + 0.00025, 120, 0.026, 0.05, label_material(f"label_s_{scent}", lp)))
    root = parent_all(parts, f"spray_{scent}")
    return root, 0.15


def matches_jar():
    R, H = 0.03, 0.135
    g = glass("mglass", "#FAF8F4")
    prof = [(0, 0)] + arc(R - 0.004, 0.004, 0.004, -90, 0, 5) + [(R, H - 0.002)] + arc(R - 0.0015, H - 0.0015, 0.0015, 0, 180, 6)
    prof += [(R - 0.003, 0.008), (0, 0.008)]
    jar = lathe("mjar", prof, 160, g)
    cork = material("cork", **{"Base Color": srgb("#B88B5E"), "Roughness": 0.9})
    n, l = nodes(cork)
    vor = n.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 900
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.5
    l.new(vor.outputs["Distance"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], n["Principled BSDF"].inputs["Normal"])
    stopper = lathe("cork", [(0, 0), (R - 0.0028, 0), (R - 0.0024, 0.016), (R + 0.0015, 0.0165), (R + 0.0015, 0.024), (0, 0.024)], 128, cork)
    stopper.location = (0, 0, H - 0.0158)
    stick = material("stick", **{"Base Color": srgb("#D9C3A0"), "Roughness": 0.8})
    head = material("head", **{"Base Color": srgb("#2A2422"), "Roughness": 0.55})
    parts = [jar, stopper]
    rng = random.Random(11)
    placed = 0
    tries = 0
    while placed < 34 and tries < 2000:
        tries += 1
        rr = (R - 0.006) * math.sqrt(rng.random())
        a = rng.uniform(0, 2 * math.pi)
        x, y = rr * math.cos(a), rr * math.sin(a)
        L = 0.104
        tilt_a = rng.uniform(0, 2 * math.pi)
        tilt = math.radians(rng.uniform(0, 6))
        base = Vector((x, y, 0.009))
        d = Vector((math.sin(tilt) * math.cos(tilt_a), math.sin(tilt) * math.sin(tilt_a), math.cos(tilt)))
        top = base + d * L
        if math.hypot(top.x, top.y) > R - 0.0045:
            continue
        s = box(f"stick{placed}", 0.0024, 0.0024, L, stick, loc=tuple(base.lerp(top, 0.5)))
        s.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        s.rotation_euler.rotate_axis("Z", rng.uniform(0, math.pi))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0024, location=tuple(top), segments=16, ring_count=10)
        hd = bpy.context.active_object
        hd.scale = (1, 1, 1.7)
        hd.data.materials.append(head)
        for p in hd.data.polygons:
            p.use_smooth = True
        parts += [s, hd]
        placed += 1
    lp = LABELS / "matches.png"
    labels.band_label(
        [("mark", "OMBRA", 8, 11, None), ("italic", "Long matches", 27, 12.5, None), ("caps", "34 × 11 CM", 48, 5, 0.2), ("dot", "", 61, 1.0, None)],
        R * math.radians(110), 0.056, lp, striker=True,
    )
    parts.append(band("label", R + 0.00025, 110, 0.022, 0.056, label_material("label_matches", lp)))
    root = parent_all(parts, "matches")
    return root, 0.15


def gift_box():
    """Rigid charcoal box with a paper band, standing behind the set."""
    board = material("board", **{"Base Color": srgb("#2C2826"), "Roughness": 0.75})
    n, l = nodes(board)
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 400
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.08
    l.new(noise.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], n["Principled BSDF"].inputs["Normal"])
    W, D, Hh = 0.27, 0.075, 0.19
    b = box("gift_box", W, D, Hh, board, bevel=0.0012, loc=(0, 0, Hh / 2))
    lid_line = box("lid_line", W + 0.0012, D + 0.0012, 0.0006, material("seam", **{"Base Color": srgb("#1B1817"), "Roughness": 0.9}), loc=(0, 0, Hh - 0.035))
    lp = LABELS / "giftbox.png"
    labels.band_label(
        [("mark", "OMBRA", 12, 20, None), ("italic", "The Evening Set", 48, 20, None), ("dot", "", 84, 2.0, None)],
        0.07, 0.04, lp,
    )
    lab_mat = label_material("label_gift", lp)
    verts = [(-0.035, -D / 2 - 0.0004, 0.128), (0.035, -D / 2 - 0.0004, 0.128), (0.035, -D / 2 - 0.0004, 0.168), (-0.035, -D / 2 - 0.0004, 0.168)]
    me = bpy.data.meshes.new("gift_label")
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, co in zip(me.polygons[0].loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[li].uv = co
    lab = link(bpy.data.objects.new("gift_label", me))
    lab.data.materials.append(lab_mat)
    root = parent_all([b, lid_line, lab], "gift_box")
    return root


# ----------------------------------------------------------------------------- studio


def studio(mood="day", backdrop="#E6DDD1"):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("world")
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes["Background"]
    if mood == "day":
        bg.inputs["Color"].default_value = srgb("#D9D2C8")
        bg.inputs["Strength"].default_value = 0.14
    else:
        bg.inputs["Color"].default_value = srgb("#30302F")
        bg.inputs["Strength"].default_value = 0.012

    # floor that curves up into a wall
    prof = [(-3.0, 0.0), (0.55, 0.0)]
    prof += [(0.55 + 0.45 * math.sin(math.radians(a)), 0.45 - 0.45 * math.cos(math.radians(a))) for a in range(5, 91, 5)]
    prof += [(1.0, 2.5)]
    verts, faces = [], []
    xs = [-3.0, 3.0]
    for i, (y, z) in enumerate(prof):
        for x in xs:
            verts.append((x, y, z))
    for i in range(len(prof) - 1):
        a, b = i * 2, (i + 1) * 2
        faces.append((a, a + 1, b + 1, b))
    sweep = mesh_object("sweep", verts, faces, True, plaster(color=backdrop if mood == "day" else "#8E847A"))

    if mood == "day":
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy = 8.0
        sun.angle = math.radians(1.2)
        sun.color = (1.0, 0.88, 0.74)
        so = link(bpy.data.objects.new("sun", sun))
        so.rotation_euler = Euler((math.radians(62), 0, math.radians(-58)), "XYZ")
        # window frame between the sun and the set: its shadow falls on the wall
        frame_mat = material("frame", **{"Base Color": (0.1, 0.1, 0.1, 1)})
        frame_parts = []
        W, Hh, bar = 1.6, 1.8, 0.07
        for x in (-W / 2, 0.0, W / 2):
            frame_parts.append(box("mullion", bar, 0.03, Hh, frame_mat, loc=(x, 0, 0)))
        for z in (-Hh / 2, 0.15, Hh / 2):
            frame_parts.append(box("transom", W, 0.03, bar, frame_mat, loc=(0, 0, z)))
        # solid wall around the window
        frame_parts.append(box("wall_l", 3, 0.03, 4, frame_mat, loc=(-W / 2 - 1.5, 0, 0)))
        frame_parts.append(box("wall_r", 3, 0.03, 4, frame_mat, loc=(W / 2 + 1.5, 0, 0)))
        frame_parts.append(box("wall_t", W, 0.03, 2, frame_mat, loc=(0, 0, Hh / 2 + 1.0)))
        frame_parts.append(box("wall_b", W, 0.03, 2, frame_mat, loc=(0, 0, -Hh / 2 - 1.0)))
        win = parent_all(frame_parts, "window")
        sun_dir = so.rotation_euler.to_matrix() @ Vector((0, 0, 1))
        win.location = Vector((0.12, 0.35, 0.25)) + sun_dir * 2.6
        win.rotation_euler = sun_dir.to_track_quat("Y", "Z").to_euler()
        for p in frame_parts:
            p.visible_camera = False
            p.visible_glossy = False
            p.visible_transmission = False
        fill = bpy.data.lights.new("fill", "AREA")
        fill.energy = 24
        fill.size = 1.6
        fill.color = (0.95, 0.96, 1.0)
        fo = link(bpy.data.objects.new("fill", fill))
        fo.location = (1.2, -1.4, 0.7)
        fo.rotation_euler = (Vector((0, 0, 0.1)) - fo.location).to_track_quat("-Z", "Y").to_euler()
        fo.visible_glossy = True
    if mood == "night":
        dusk = bpy.data.lights.new("dusk", "AREA")
        dusk.shape = "RECTANGLE"
        dusk.size, dusk.size_y = 0.8, 1.2
        dusk.energy = 6.0
        dusk.color = (0.72, 0.80, 1.0)
        do = link(bpy.data.objects.new("dusk", dusk))
        do.location = (-1.3, 0.1, 0.9)
        do.rotation_euler = (Vector((0.1, 0.25, 0.05)) - do.location).to_track_quat("-Z", "Y").to_euler()
    # tall strip lights that only show up as reflections in glass and metal
    for name, x, energy in (("strip_l", -0.75, 42 if mood == "day" else 0.8), ("strip_r", 0.9, 20 if mood == "day" else 0.4)):
        st = bpy.data.lights.new(name, "AREA")
        st.shape = "RECTANGLE"
        st.size = 0.12
        st.size_y = 1.2
        st.energy = energy
        o = link(bpy.data.objects.new(name, st))
        o.location = (x, -0.7, 0.35)
        o.rotation_euler = (Vector((0, 0, 0.08)) - o.location).to_track_quat("-Z", "Y").to_euler()
        o.visible_diffuse = False
    return sweep


def camera(target, height_frac, obj_h, aspect=1.0, lens=85, elev_deg=9.0, shift_x=0.0, fstop=4.0):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam_data.sensor_fit = "AUTO"
    cam = link(bpy.data.objects.new("cam", cam_data))
    bpy.context.scene.camera = cam
    fov_v = 2 * math.atan(18 / lens) if aspect >= 1 else 2 * math.atan(18 / lens) / 1
    if aspect >= 1:
        fov_v = 2 * math.atan((36 / aspect) / 2 / lens)
    else:
        fov_v = 2 * math.atan(18 / lens)
    dist = (obj_h / height_frac) / (2 * math.tan(fov_v / 2))
    el = math.radians(elev_deg)
    t = Vector(target)
    cam.location = t + Vector((0, -dist * math.cos(el), dist * math.sin(el)))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.shift_x = shift_x
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = dist
    cam_data.dof.aperture_fstop = fstop
    cam_data.clip_start = 0.01
    return cam


def render_settings(res_x, res_y, samples, path):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.015
    s.cycles.use_denoising = True
    try:
        s.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    s.cycles.max_bounces = 16
    s.cycles.diffuse_bounces = 3
    s.cycles.glossy_bounces = 6
    s.cycles.transmission_bounces = 12
    s.cycles.transparent_max_bounces = 12
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.cycles.blur_glossy = 1.0
    s.render.threads_mode = "FIXED"
    s.render.threads = 2
    s.render.resolution_x = res_x
    s.render.resolution_y = res_y
    s.render.resolution_percentage = 100
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_depth = "8"
    s.view_settings.view_transform = "AgX"
    for want in ("AgX - Medium High Contrast", "AgX - Base Contrast"):
        try:
            s.view_settings.look = want
            break
        except TypeError:
            continue
    s.render.filepath = str(path)


class _Floor:
    class dimensions:  # noqa: N801  (mimics an object's dimensions)
        z = 0.0


def plinth(w=0.30, d=0.20, h=0.032, show=False):
    """Stone slab and a near wall for the hero and story shots; packshots stand on the floor."""
    if not show:
        return _Floor()
    stone = material("stone", **{"Base Color": srgb("#6E655C"), "Roughness": 0.6})
    n, l = nodes(stone)
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 220
    noise.inputs["Detail"].default_value = 6
    bmp = n.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = 0.12
    l.new(noise.outputs["Fac"], bmp.inputs["Height"])
    l.new(bmp.outputs["Normal"], n["Principled BSDF"].inputs["Normal"])
    wall = box("near_wall", 3.0, 0.02, 1.6, plaster("wall", "#A39789", bump=0.12), loc=(0, d / 2 + 0.07, 0.8))
    return box("plinth", w, d, h, stone, bevel=0.003, loc=(0, 0, h / 2))


# ----------------------------------------------------------------------------- shots


def shot(name, res, samples, out):
    reset()
    lit = name.endswith("-lit")
    base = name[:-4] if lit else name
    mood = "night" if lit or base.startswith("hero") or base == "story" else "day"
    studio(mood)
    aspect = 1.0
    target_z = None
    if base.startswith("jar-"):
        _, scent, size = base.split("-")
        p = plinth()
        root, h = jar_candle(scent, size, lit, lid="none" if lit else "side")
        root.location = (0, 0, p.dimensions.z)
        target_z = p.dimensions.z + h * 0.5
        cam = camera((0.02, 0, target_z), 0.42 if size == "200" else 0.48, h, elev_deg=10)
    elif base == "vessel":
        p = plinth()
        root, h = vessel_candle(lit)
        root.location = (0, 0, p.dimensions.z)
        target_z = p.dimensions.z + h * 0.45
        cam = camera((0, 0, target_z), 0.30, h, elev_deg=16)
    elif base.startswith("tin-"):
        p = plinth()
        root, h = travel_tin(base.split("-")[1])
        root.location = (0, -0.01, p.dimensions.z)
        target_z = p.dimensions.z + 0.035
        cam = camera((0, 0, target_z), 0.42, h, elev_deg=14)
    elif base.startswith("diffuser-"):
        p = plinth()
        root, h = reed_diffuser(base.split("-")[1])
        root.location = (0, 0, p.dimensions.z)
        target_z = p.dimensions.z + h * 0.48
        cam = camera((0, 0, target_z), 0.80, h, elev_deg=8)
    elif base.startswith("spray-"):
        p = plinth()
        root, h = room_spray(base.split("-")[1])
        root.location = (0, 0, p.dimensions.z)
        target_z = p.dimensions.z + h * 0.48
        cam = camera((0, 0, target_z), 0.5, h, elev_deg=8)
    elif base == "matches":
        p = plinth()
        root, h = matches_jar()
        root.location = (-0.012, 0, p.dimensions.z)
        target_z = p.dimensions.z + h * 0.47
        cam = camera((0, 0, target_z), 0.52, h, elev_deg=9)
    elif base == "giftset":
        p = plinth(0.42, 0.24)
        z = p.dimensions.z
        box_root = gift_box()
        box_root.location = (0.035, 0.05, z)
        jar_root, _ = jar_candle("fig", "200", False, lid="none")
        jar_root.location = (-0.03, -0.05, z)
        spray_root, _ = room_spray("fig")
        spray_root.location = (-0.115, -0.02, z)
        m_root, _ = matches_jar()
        m_root.location = (0.11, -0.04, z)
        m_root.scale = (0.9, 0.9, 0.9)
        target_z = z + 0.085
        cam = camera((0.02, 0, target_z), 0.62, 0.22, elev_deg=12)
    elif base.startswith("hero"):
        mobile = base == "hero-mobile"
        p = plinth(0.6, 0.26, 0.04, show=True)
        z = p.dimensions.z
        a, ha = jar_candle("amber", "400", True, lid="none")
        a.location = (-0.07, 0.03, z)
        b, hb = jar_candle("fig", "200", True, lid="none")
        b.location = (0.035, -0.035, z)
        c, hc = jar_candle("salt", "200", True, lid="none")
        c.location = (0.135, 0.045, z)
        aspect = 16 / 9 if not mobile else 4 / 5
        target_z = z + 0.06
        if mobile:
            cam = camera((0.035, 0, target_z + 0.03), 0.42, 0.13, aspect, lens=70, elev_deg=11)
        else:
            cam = camera((0.04, 0, target_z), 0.5, 0.13, aspect, lens=70, elev_deg=7, shift_x=-0.25)
    elif base == "story":
        p = plinth(0.4, 0.24, show=True)
        z = p.dimensions.z
        root, h = jar_candle("amber", "400", True, lid="none")
        root.location = (-0.03, 0, z)
        m_root, _ = matches_jar()
        m_root.location = (0.065, 0.045, z)
        aspect = 4 / 5
        target_z = z + 0.065
        cam = camera((0.012, 0, target_z), 0.5, 0.15, aspect, lens=85, elev_deg=8)
    else:
        raise SystemExit(f"unknown shot {name}")

    if aspect >= 1:
        rx, ry = res, int(round(res / aspect))
    else:
        rx, ry = int(round(res * aspect)), res
    path = Path(out) / f"{name}.png"
    render_settings(rx, ry, samples, path)
    bpy.ops.render.render(write_still=True)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", nargs="+")
    ap.add_argument("--res", type=int, default=1200)
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    for s in a.shots:
        print("rendered", shot(s, a.res, a.samples, a.out), flush=True)
