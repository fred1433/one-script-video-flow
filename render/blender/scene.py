"""Builds the fictional cartridge lock and renders one frame range from one camera.

Run:  blender -b --factory-startup -P render/blender/scene.py -- job.json

job.json
  {"timeline": {...}, "camera": "wide"|"tall", "frame_start": 1, "frame_end": 120,
   "out": "path/clip.mp4", "anchors_out": "path/anchors.json", "res": [1920,1080],
   "samples": 32, "kit": {...}}

The timeline is produced by the storyboard step: absolute keyframes (seconds) for the
mechanism (lug_z, theta, section, pull) and for each camera rig.
"""
import bpy, bmesh, json, math, sys
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv[sys.argv.index("--") + 1:]
JOB = json.load(open(argv[0]))
KIT = JOB["kit"]
FPS = JOB["timeline"].get("fps", 24)

def hex_rgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]

# ---------------------------------------------------------------- scene setup
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = FPS
sc.render.engine = "BLENDER_EEVEE"
ee = sc.eevee
ee.taa_render_samples = JOB.get("samples", 32)
for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 3),
                  ("shadow_step_count", 10), ("use_fast_gi", True)):
    if hasattr(ee, attr):
        setattr(ee, attr, val)
if hasattr(ee, "ray_tracing_options"):
    ee.ray_tracing_options.resolution_scale = "1"
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast" if "AgX - Base Contrast" in [i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else "None"
sc.view_settings.exposure = KIT["render"].get("exposure", 0.0)

world = bpy.data.worlds.new("studio")
sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = hex_rgb(KIT["render"]["world"])
bg.inputs[1].default_value = KIT["render"].get("world_strength", 0.9)

def mat(name, color, rough=0.62, spec=0.35, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = hex_rgb(color)
    p.inputs["Roughness"].default_value = rough
    for key in ("Specular IOR Level", "Specular"):
        if key in p.inputs:
            p.inputs[key].default_value = spec
    if coat and "Coat Weight" in p.inputs:
        p.inputs["Coat Weight"].default_value = coat
        p.inputs["Coat Roughness"].default_value = 0.35
    return m

M = KIT["materials"]
CLAY = mat("clay", M["clay"], 0.6)
CLAY2 = mat("clay_cartridge", M["cartridge"], 0.5, coat=0.15)
LUG = mat("lug", M["lug"], 0.4, coat=0.3)
STOP = mat("stop", M["stop"], 0.45)
SECT = mat("section", M["section"], 0.8, spec=0.1)
SPRING = mat("spring", M["spring"], 0.3, spec=0.6)
FLOOR = mat("floor", M["floor"], 0.9, spec=0.1)

def link(obj):
    sc.collection.objects.link(obj)
    return obj

def mesh_obj(name, bm, material=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    if material:
        ob.data.materials.append(material)
    return ob

def cyl(name, r, z0, z1, seg=96, material=None, loc=(0, 0, 0), rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=z1 - z0)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, (z0 + z1) / 2))
    ob = mesh_obj(name, bm, material)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob

def box(name, size, loc, material=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    ob = mesh_obj(name, bm, material)
    ob.location = loc
    return ob

def arc_block(name, r0, r1, z0, z1, a0, a1, steps=48):
    """Solid ring sector between angles a0..a1 (radians)."""
    bm = bmesh.new()
    vs = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        ring = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in ((r0, z0), (r1, z0), (r1, z1), (r0, z1))]
        vs.append(ring)
    bm.faces.new(vs[0][::-1])
    bm.faces.new(vs[-1])
    for i in range(steps):
        a, b = vs[i], vs[i + 1]
        for k in range(4):
            bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_obj(name, bm)

def boolean(target, cutter, op="DIFFERENCE", apply=True):
    mod = target.modifiers.new("bool_" + cutter.name, "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = cutter
    if apply:
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    return mod

def bevel(ob, width=0.025, seg=3, angle=35):
    b = ob.modifiers.new("bevel", "BEVEL")
    b.width = width
    b.segments = seg
    b.limit_method = "ANGLE"
    b.angle_limit = math.radians(angle)
    b.harden_normals = False
    return b

def smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True
    if hasattr(ob.data, "set_sharp_from_angle"):
        ob.data.set_sharp_from_angle(angle=math.radians(35))

G = KIT["geometry"]
RO, RI, H = G["housing_r_out"], G["housing_r_in"], G["housing_h"]
W = G["slot_w"]
ZL, ZN = G["leg_z"], G["notch_z"]           # lug centre height in the side leg / in the notch
A_IN = math.radians(90)                       # entry slot angle (+Y)
D = (W / 2) / RO                               # half slot width as an angle

# ---------------------------------------------------------------- housing
housing = cyl("housing", RO, 0, H, 128, CLAY)
boolean(housing, cyl("bore", RI, G["floor_t"], H + 1, 128))
# entry leg (axial), open at the top
cut = box("leg_axial", (0.9, W, H), (0, (RO + RI) / 2, ZL + H / 2))
cut.rotation_euler = (0, 0, A_IN - math.radians(90))
cut.location = (0, (RO + RI) / 2, ZL + H / 2)
cut.dimensions = (W, 0.9, H)
boolean(housing, cut)
# rounded bottom of the entry leg
boolean(housing, cyl("leg_round", W / 2 + 0.004, -0.6, 0.6, 48, loc=(0, (RO + RI) / 2, ZL), rot=(math.radians(90), 0, 0)))
# side leg, a quarter turn
boolean(housing, arc_block("leg_side", RI - 0.2, RO + 0.2, ZL - W / 2, ZL + W / 2, 0, A_IN, 64))
# notch at the end of the side leg (lug rises into it)
for z in (ZL, ZN):
    boolean(housing, cyl("notch_round", W / 2 + 0.004, -0.6, 0.6, 48, loc=((RO + RI) / 2, 0, z), rot=(0, math.radians(90), 0)))
boolean(housing, box("notch_box", (0.9, W, ZN - ZL), ((RO + RI) / 2, 0, (ZL + ZN) / 2)))
# the stop: an amber insert in the wall, right beside the notch
STOP_A = 0.30
boolean(housing, arc_block("stop_seat", RI - 0.05, RO + 0.05, ZL + W / 2 - 0.03, ZN + W / 2 + 0.16, D, D + STOP_A, 16))
stop = arc_block("stop", RI, RO + 0.05, ZL + W / 2, ZN + W / 2 + 0.16, D, D + STOP_A, 24)
stop.data.materials.append(STOP)
smooth(stop)
bevel(stop, 0.018, 3)
smooth(housing)
bevel(housing, 0.022, 3)

pedestal = cyl("pedestal", G["pedestal_r"], -G["pedestal_h"], 0, 128, CLAY)
smooth(pedestal)
bevel(pedestal, 0.06, 4)

# ---------------------------------------------------------------- cartridge (origin = lug centre)
cart = cyl("cartridge", G["cart_r"], G["cart_bottom"], G["cart_top"], 128, CLAY2)
cap = cyl("cap", G["cap_r"], G["cart_top"] - 0.05, G["cart_top"] + G["cap_h"], 128, CLAY2)
boolean(cart, cap, "UNION")
for i in range(24):
    a = 2 * math.pi * i / 24
    boolean(cart, cyl("knurl", 0.07, G["cart_top"] + 0.05, G["cart_top"] + G["cap_h"] + 0.2, 16,
                      loc=(G["cap_r"] * math.cos(a), G["cap_r"] * math.sin(a), 0)))
smooth(cart)
bevel(cart, 0.03, 3)
lug = cyl("lug", G["lug_r"], 0, G["lug_len"], 48, LUG, loc=(0, G["cart_r"] - 0.15, 0), rot=(math.radians(-90), 0, 0))
smooth(lug)
bevel(lug, 0.035, 3)
lug.parent = cart
lug.location = (0, G["cart_r"] - 0.15, 0)
cart_rig = link(bpy.data.objects.new("cart_rig", None))
cart.parent = cart_rig

# ---------------------------------------------------------------- spring (screw modifier keeps the wire round)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=False, segments=16, radius=G["spring_wire"])
bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.radians(90), 3, "X"))
bmesh.ops.translate(bm, verts=bm.verts, vec=(G["spring_r"], 0, 0))
spring = mesh_obj("spring", bm, SPRING)
spring.location = (0, 0, G["floor_t"])
scr = spring.modifiers.new("screw", "SCREW")
scr.angle = 2 * math.pi
scr.iterations = G["spring_turns"]
scr.steps = 48
scr.render_steps = 48
scr.use_smooth_shade = True
scr.screw_offset = G["spring_free"] / G["spring_turns"]

# ---------------------------------------------------------------- section cutter (live boolean, animated)
cutter = box("section_cutter", (12, 6, 12), (0, -3 - 0.001, 2), SECT)
cutter.hide_render = True
for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_shadow", "visible_transmission", "visible_volume_scatter"):
    if hasattr(cutter, attr):
        setattr(cutter, attr, False)
cutter.display_type = "WIRE"
for ob in (housing, pedestal):
    m = boolean(ob, cutter, apply=False)
    m.material_mode = "TRANSFER"
cutter_home = Vector((0, -3 - 0.001, 2))

# ---------------------------------------------------------------- studio: infinity cove all around
bm = bmesh.new()
flat, rr, top = 30.0, 12.0, 60.0
prof = [(0.001, 0), (flat, 0)]
for i in range(1, 17):
    a = math.pi / 2 * i / 16
    prof.append((flat + rr * math.sin(a), rr * (1 - math.cos(a))))
prof.append((flat + rr, top))
segs = 96
rings = []
for j in range(segs):
    a = 2 * math.pi * j / segs
    rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z - G["pedestal_h"])) for r, z in prof])
for j in range(segs):
    A, B = rings[j], rings[(j + 1) % segs]
    for k in range(len(prof) - 1):
        bm.faces.new((A[k], A[k + 1], B[k + 1], B[k]))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cove = mesh_obj("cove", bm, FLOOR)
smooth(cove)

# ---------------------------------------------------------------- lights
light_rig = link(bpy.data.objects.new("light_rig", None))
def area(name, loc, size, power, color="#FFFFFF"):
    ld = bpy.data.lights.new(name, "AREA")
    ld.size = size
    ld.energy = power
    ld.color = hex_rgb(color)[:3]
    ob = link(bpy.data.objects.new(name, ld))
    ob.parent = light_rig
    ob.location = loc
    d = Vector((0, 0, 1.8)) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob
L = KIT["render"]["lights"]
# positions are relative to the active camera (camera sits on local -Y)
area("key", (-7.0, -6.0, 9.0), 5.0, L["key"])
area("fill", (8.0, -4.0, 3.0), 8.0, L["fill"], "#F2F6FF")
area("rim", (3.0, 8.0, 7.0), 4.0, L["rim"])
area("top", (0, 0, 11), 6.0, L["top"])
# backdrop: lifts the cove wall behind the part so the frame stays light
bd = area("backdrop", (0, 9.0, 9.0), 14.0, L.get("backdrop", 0))
bd.rotation_euler = (Vector((0, 40.0, 3.0)) - Vector((0, 9.0, 9.0))).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- cameras on rigs
def rig(name, aspect_w, aspect_h):
    r = link(bpy.data.objects.new(name + "_rig", None))
    r.rotation_mode = "XYZ"
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = "VERTICAL" if aspect_h > aspect_w else "HORIZONTAL"
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = KIT["render"].get("fstop", 5.6)
    cam = link(bpy.data.objects.new(name, cd))
    cam.parent = r
    cam.rotation_euler = (math.radians(90), 0, 0)
    focus = link(bpy.data.objects.new(name + "_focus", None))
    focus.parent = r
    cd.dof.focus_object = focus
    return r, cam, focus
RIGS = {"wide": rig("wide", 16, 9), "tall": rig("tall", 9, 16)}

# ---------------------------------------------------------------- anchors for 2D callouts
anchors = {}
def anchor(name, parent, loc):
    e = link(bpy.data.objects.new("a_" + name, None))
    e.parent = parent
    e.location = loc
    anchors[name] = e
anchor("lug", lug, (0, 0, G["lug_len"]))
anchor("stop", None, ((RO + 0.02) * math.cos(D + 0.15), (RO + 0.02) * math.sin(D + 0.15), ZN + 0.1))
anchor("groove", None, (0, RO + 0.02, (ZL + H) / 2 + 0.2))
anchor("spring", None, (G["spring_r"] * 0.2, -G["spring_r"] - 0.05, G["floor_t"] + 0.45))
anchor("cap", cart, (0, -G["cap_r"], G["cart_top"] + G["cap_h"] * 0.5))
anchor("housing", None, ((RO + 0.02) * math.cos(math.radians(125)), (RO + 0.02) * math.sin(math.radians(125)), 1.1))
anchor("ledge", None, (RO - 0.05, -0.01, ZN + W / 2 + 0.02))

# ---------------------------------------------------------------- keyframes from the timeline
T = JOB["timeline"]
def f(t):
    return 1 + t * FPS

def keys(track, setter, path_objs):
    for t, v in track:
        setter(v)
        for ob, path, idx in path_objs:
            ob.keyframe_insert(path, index=idx, frame=f(t))

def set_lug(v):
    cart_rig.location.z = v
def set_theta(v):
    cart_rig.rotation_euler.z = math.radians(v - 90)
def set_section(v):
    cutter.location = cutter_home + Vector((0, 6.0 * (1 - v) * -1, 0)) if v < 1 else cutter_home

keys(T["lug_z"], set_lug, [(cart_rig, "location", 2)])
keys(T["theta"], set_theta, [(cart_rig, "rotation_euler", 2)])
keys(T["section"], set_section, [(cutter, "location", 1)])

# spring top follows the cartridge bottom once compressed (modifiers off while scrubbing: fast)
def mods(on):
    for ob in bpy.data.objects:
        for m in ob.modifiers:
            m.show_viewport = on
mods(False)
free_top = G["floor_t"] + G["spring_free"]
for fr in range(1, T["frames"] + 2, 2):
    sc.frame_set(fr)
    bottom = cart_rig.matrix_world.translation.z + G["cart_bottom"]
    top = min(free_top, bottom)
    scr.screw_offset = max(0.05, (top - G["floor_t"]) / G["spring_turns"])
    spring.keyframe_insert(data_path='modifiers["screw"].screw_offset', frame=fr)

for cname, (r, cam, focus) in RIGS.items():
    for t, az, el, dist, tz, tx, lens in T["cams"][cname]:
        fr = f(t)
        a = math.radians(az)
        r.location = (-tx * math.cos(a), -tx * math.sin(a), tz)
        r.rotation_euler = (math.radians(-el), 0, math.radians(az))
        cam.location = (0, -dist, 0)
        cam.data.lens = lens
        focus.location = (0, 0, 0)
        r.keyframe_insert("location", frame=fr)
        r.keyframe_insert("rotation_euler", frame=fr)
        cam.keyframe_insert("location", frame=fr)
        cam.data.keyframe_insert("lens", frame=fr)

for ob in list(bpy.data.objects):
    ad = ob.animation_data
    for a in ([ad.action] if ad and ad.action else []):
        fcs = a.fcurves if hasattr(a, "fcurves") else [fc for l in a.layers for s in l.strips for cb in s.channelbags for fc in cb.fcurves]
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "AUTO"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

# ---------------------------------------------------------------- render
cname = JOB["camera"]
r, cam, focus = RIGS[cname]
sc.camera = cam
cr = light_rig.constraints.new("COPY_ROTATION")
cr.target = r
cr.use_x = cr.use_y = False
sc.render.resolution_x, sc.render.resolution_y = JOB["res"]
sc.render.resolution_percentage = JOB.get("res_pct", 100)
sc.frame_start, sc.frame_end = JOB["frame_start"], JOB["frame_end"]

mods(False)
if JOB.get("anchors_out"):
    out = {}
    for fr in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(fr)
        row = {}
        for n, e in anchors.items():
            p = world_to_camera_view(sc, cam, e.matrix_world.translation)
            row[n] = [round(p.x, 4), round(1 - p.y, 4), round(p.z, 3)]
        out[fr] = row
    json.dump(out, open(JOB["anchors_out"], "w"))

mods(True)
if JOB.get("debug"):
    exec(open(JOB["debug_script"]).read())
    raise SystemExit
if JOB.get("still"):
    sc.frame_set(JOB["frame_start"])
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = JOB["out"]
    bpy.ops.render.render(write_still=True)
else:
    # frames as high-quality JPEG; the render service encodes them with ffmpeg
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 94
    sc.render.filepath = JOB["out"].rstrip("/") + "/f_####"
    bpy.ops.render.render(animation=True)
