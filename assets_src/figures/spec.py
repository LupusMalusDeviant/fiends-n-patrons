"""Character specifications: skeleton curves, cross-sections, rig and poses.

Everything is data. A character is a torso curve with keyed cross-sections, a
list of limbs (each a face patch on the surface plus its own curve and
cross-sections), a list of loop displacements that add the shape detail, a bone
list, and four poses that exercise the rig.

Coordinates: X right, Y forward (the way the character faces), Z up, floor at
Z = 0. Sizes are metres and follow the character briefs: imp about 1.0 m,
damned soul about 1.8 m, brute about 2.4 m.
"""
import lofting as L

key = L.profile_key


# =========================================================== the imp (1.0 m) ===
# Hunched, digitigrade, big skull, swept horns, long tail. The torso curve
# arches back at the shoulder line and throws the head forward -- that hunch is
# in the spine curve itself, not bolted on afterwards.
IMP = dict(
    name="imp",
    label="Imp",
    height=1.0,
    nseg=12,
    stations=32,
    torso=dict(
        region="skin",
        u_hint=(1.0, 0.0, 0.0),
        ctrl=[(0.0,  0.000, 0.400),   # crotch
              (0.0,  0.030, 0.500),   # lower belly
              (0.0,  0.040, 0.580),   # belly
              (0.0,  0.010, 0.680),   # chest
              (0.0, -0.050, 0.760),   # upper chest
              (0.0, -0.080, 0.810),   # shoulder line, the peak of the hunch
              (0.0, -0.050, 0.855),   # neck
              (0.0,  0.020, 0.890),   # head base, thrust forward
              (0.0,  0.050, 0.945),   # skull
              (0.0,  0.030, 0.995)],  # crown
        keys=[key(0.00, rx=0.100, ry=0.080, power=2.2),
              key(0.10, rx=0.122, ry=0.098, power=2.2),
              key(0.27, rx=0.124, ry=0.112, power=2.0, dv=0.010),   # pot belly
              key(0.43, rx=0.140, ry=0.104, power=2.2),
              key(0.56, rx=0.152, ry=0.100, power=2.4),
              key(0.65, rx=0.158, ry=0.094, power=2.5),             # shoulders
              key(0.695, rx=0.140, ry=0.088, power=2.4),
              key(0.745, rx=0.058, ry=0.056, power=2.0),            # neck
              key(0.80, rx=0.072, ry=0.084, power=2.0, dv=0.012),
              key(0.87, rx=0.098, ry=0.106, power=2.2, dv=0.016),   # skull
              key(0.94, rx=0.094, ry=0.098, power=2.2, dv=0.008),
              key(1.00, rx=0.040, ry=0.044, power=2.0)],
    ),
    limbs=[
        dict(name="arm.R", region="skin", mirror=True, steps=9, ease=2,
             seed=dict(stations=(18, 20), segments=(11, 0)),
             ctrl=[(0.150, -0.030, 0.795),
                   (0.245,  0.015, 0.700),
                   (0.300,  0.105, 0.615),
                   (0.320,  0.160, 0.570)],
             keys=[key(0.00, rx=0.058, ry=0.058, power=2.2),
                   key(0.35, rx=0.046, ry=0.046, power=2.0),
                   key(0.70, rx=0.036, ry=0.036, power=2.0),
                   key(0.88, rx=0.042, ry=0.034, power=2.4),   # mitten hand
                   key(1.00, rx=0.044, ry=0.030, power=2.6)],
             digits=[dict(pick=0, direction=(0.10, 0.92, -0.38), length=0.050,
                          radii=(0.014, 0.008, 0.002), steps=3, region="claw"),
                     dict(pick=1, direction=(0.35, 0.90, -0.26), length=0.055,
                          radii=(0.014, 0.008, 0.002), steps=3, region="claw"),
                     dict(pick=2, direction=(0.10, 0.94, 0.32), length=0.048,
                          radii=(0.013, 0.007, 0.002), steps=3, region="claw")],
             digit_sort_axis=(0.0, 0.0, 1.0)),
        # Digitigrade: knee forward, hock back and high, the character stands on
        # an elongated foot. The S-curve is why the frames must be transport-based.
        dict(name="leg.R", region="skin", mirror=True, steps=11, ease=2,
             seed=dict(stations=(1, 3), segments=(11, 0)),
             ctrl=[(0.085,  0.000, 0.440),
                   (0.105,  0.075, 0.300),   # knee, forward
                   (0.098, -0.035, 0.155),   # hock, back
                   (0.098,  0.020, 0.048),
                   (0.098,  0.062, 0.030)],  # toe base
             keys=[key(0.00, rx=0.074, ry=0.074, power=2.2),
                   key(0.22, rx=0.064, ry=0.070, power=2.2),
                   key(0.45, rx=0.048, ry=0.052, power=2.0),
                   key(0.68, rx=0.032, ry=0.036, power=2.0),
                   key(0.88, rx=0.030, ry=0.034, power=2.2),
                   key(1.00, rx=0.034, ry=0.030, power=2.6)],
             digits=[dict(pick=0, direction=(-0.30, 0.90, -0.30), length=0.062,
                          radii=(0.016, 0.009, 0.002), steps=3, region="claw"),
                     dict(pick=1, direction=(0.00, 0.95, -0.30), length=0.070,
                          radii=(0.017, 0.010, 0.002), steps=3, region="claw"),
                     dict(pick=2, direction=(0.32, 0.90, -0.28), length=0.062,
                          radii=(0.016, 0.009, 0.002), steps=3, region="claw")],
             digit_sort_axis=(1.0, 0.0, 0.0)),
        dict(name="horn.R", region="horn", mirror=True, steps=7, ease=1,
             seed=dict(stations=(27, 29), segments=(11, 0)),
             ctrl=[(0.080, -0.010, 0.958),
                   (0.104, -0.062, 1.012),
                   (0.100, -0.140, 1.020),
                   (0.078, -0.192, 0.982)],
             keys=[key(0.00, rx=0.026, ry=0.026, power=2.2),
                   key(0.40, rx=0.017, ry=0.017, power=2.0),
                   key(0.75, rx=0.009, ry=0.009, power=2.0),
                   key(1.00, rx=0.003, ry=0.003, power=2.0)]),
        # A snout has to be real geometry. Pushing loops around only rounded the
        # skull into a lumpier egg; growing the muzzle out of the face patch
        # gives it its own loops and an actual silhouette.
        dict(name="muzzle", region="skin", mirror=False, steps=4, ease=1,
             seed=dict(stations=(24, 26), segments=(2, 3)),
             ctrl=[(0.0, 0.096, 0.906),
                   (0.0, 0.140, 0.894),
                   (0.0, 0.178, 0.878)],
             keys=[key(0.00, rx=0.050, ry=0.044, power=2.4),
                   key(0.55, rx=0.044, ry=0.038, power=2.6),
                   key(1.00, rx=0.030, ry=0.026, power=2.6)]),
        dict(name="tail", region="skin", mirror=False, steps=12, ease=2,
             seed=dict(stations=(3, 5), segments=(8, 9)),
             ctrl=[(0.0, -0.105, 0.475),
                   (0.0, -0.210, 0.420),
                   (0.0, -0.300, 0.320),
                   (0.0, -0.345, 0.195),
                   (0.0, -0.325, 0.085)],
             keys=[key(0.00, rx=0.042, ry=0.042, power=2.2),
                   key(0.30, rx=0.030, ry=0.030, power=2.0),
                   key(0.60, rx=0.020, ry=0.020, power=2.0),
                   key(0.85, rx=0.011, ry=0.011, power=2.0),
                   key(1.00, rx=0.004, ry=0.004, power=2.0)]),
    ],
    # Shape detail by pushing loops that already exist -- never by adding blobs.
    # Subdivision averages displacement away, so a bump has to be a real
    # anatomical step (3-5 cm on a 1 m creature), not the 1-2 cm that vanished
    # in the first pass and left a smooth blob.
    bumps=[dict(center=(0.000,  0.104, 0.690), radius=0.105, offset=(0.0,  0.030, 0.0)),    # chest
           dict(center=(0.058,  0.096, 0.706), radius=0.062, offset=(0.012, 0.016, 0.0)),   # pectoral R
           dict(center=(-0.058, 0.096, 0.706), radius=0.062, offset=(-0.012, 0.016, 0.0)),  # pectoral L
           dict(center=(0.000, -0.098, 0.796), radius=0.110, offset=(0.0, -0.034, 0.012)),  # hunch
           dict(center=(0.152, -0.028, 0.790), radius=0.080, offset=(0.032, 0.0, 0.016)),   # deltoid R
           dict(center=(-0.152, -0.028, 0.790), radius=0.080, offset=(-0.032, 0.0, 0.016)),  # deltoid L
           dict(center=(0.000,  0.020, 0.588), radius=0.090, offset=(0.0, 0.0, -0.012)),    # waist pinch
           dict(center=(0.000,  0.100, 0.962), radius=0.050, offset=(0.0,  0.026, 0.010)),  # brow ridge
           dict(center=(0.000,  0.086, 0.872), radius=0.050, offset=(0.0,  0.028, -0.018)),  # jaw
           dict(center=(0.062,  0.086, 0.940), radius=0.036, offset=(0.0, -0.024, 0.0)),    # eye socket R
           dict(center=(-0.062, 0.086, 0.940), radius=0.036, offset=(0.0, -0.024, 0.0)),    # eye socket L
           dict(center=(0.072,  0.062, 0.918), radius=0.034, offset=(0.020, 0.010, 0.0)),   # cheekbone R
           dict(center=(-0.072, 0.062, 0.918), radius=0.034, offset=(-0.020, 0.010, 0.0)),  # cheekbone L
           dict(center=(0.000, -0.092, 0.466), radius=0.085, offset=(0.0, -0.022, 0.0)),    # rump
           # Round 2: a face needs a mouth. Upper/lower lip volume pushed out from
           # the muzzle base, a shadow groove pinched between them, a small chin,
           # and two nostril dimples on the muzzle tip -- all pushes of loops that
           # already exist, same rule as round 1's bumps.
           dict(center=(0.000,  0.100, 0.858), radius=0.040, offset=(0.0,  0.012,  0.006)),  # upper lip
           dict(center=(0.000,  0.096, 0.840), radius=0.038, offset=(0.0,  0.010, -0.008)),  # lower lip
           dict(center=(0.000,  0.108, 0.849), radius=0.028, offset=(0.0, -0.010,  0.0)),    # mouth groove
           dict(center=(0.000,  0.070, 0.820), radius=0.045, offset=(0.0,  0.014, -0.006)),  # chin
           dict(center=(0.013,  0.168, 0.884), radius=0.012, offset=(0.0, -0.007, -0.004)),  # nostril R
           dict(center=(-0.013, 0.168, 0.884), radius=0.012, offset=(0.0, -0.007, -0.004))],  # nostril L
    # Round 3: real eye sockets carved into the surface (headsculpt.carve_eye_
    # socket -- inset rim, sloped wall, recessed floor) at the same measured
    # points the round-2 flat eye decor already used, since those were
    # already validated against the actual rendered surface (see the decor
    # comment below). rim_radius/depth/seed_rings/subdiv_cuts were tuned and
    # measured on this exact mesh in test_headsculpt.py: seed_rings=1 keeps
    # the densified patch from crossing the head's own centre line (2 rings
    # already reached across on this narrow, nseg=12 face and corrupted both
    # sockets with a self-overlapping selection -- documented in
    # headsculpt.py), and depth=0.010 measured out at an ACHIEVED depth of
    # ~0.014 m once the inset's own in-plane shrink is accounted for.
    eye_sockets=[dict(name="eye.R", at=(0.062, 0.148, 0.940), rim_radius=0.032,
                      depth=0.010, region="skin"),
                dict(name="eye.L", at=(-0.062, 0.148, 0.940), rim_radius=0.032,
                      depth=0.010, region="skin")],
    # Round 3: head structure the round-2 isotropic bumps could not give --
    # an isotropic bump is always a round dimple, an eyebrow/jaw/cheek is a
    # wide, shallow, ELONGATED feature (headsculpt.bump_aniso, an ellipsoidal
    # falloff instead of a sphere). Brow volume sits above each new socket, a
    # snout ridge runs the length of the muzzle, a cheek fold and a sharper
    # jaw angle break up the side of the face, and a small collar (front +
    # back push) marks where each horn actually leaves the skull instead of
    # just tapering out of it.
    aniso_bumps=[
        dict(center=(0.062, 0.135, 0.955), radii=(0.040, 0.022, 0.016), offset=(0.0, 0.014, 0.010)),
        dict(center=(-0.062, 0.135, 0.955), radii=(0.040, 0.022, 0.016), offset=(0.0, 0.014, 0.010)),
        dict(center=(0.0, 0.150, 0.895), radii=(0.014, 0.045, 0.012), offset=(0.0, 0.0, 0.012)),
        dict(center=(0.045, 0.110, 0.865), radii=(0.028, 0.045, 0.018), offset=(-0.010, -0.006, -0.008)),
        dict(center=(-0.045, 0.110, 0.865), radii=(0.028, 0.045, 0.018), offset=(0.010, -0.006, -0.008)),
        dict(center=(0.055, 0.075, 0.845), radii=(0.030, 0.035, 0.020), offset=(0.012, 0.006, -0.010)),
        dict(center=(-0.055, 0.075, 0.845), radii=(0.030, 0.035, 0.020), offset=(-0.012, 0.006, -0.010)),
        dict(center=(0.078, 0.010, 0.958), radii=(0.022, 0.018, 0.014), offset=(0.004, 0.006, 0.004)),
        dict(center=(0.078, -0.035, 0.965), radii=(0.022, 0.018, 0.014), offset=(0.004, -0.006, 0.004)),
        dict(center=(-0.078, 0.010, 0.958), radii=(0.022, 0.018, 0.014), offset=(-0.004, 0.006, 0.004)),
        dict(center=(-0.078, -0.035, 0.965), radii=(0.022, 0.018, 0.014), offset=(-0.004, -0.006, 0.004)),
    ],
    # Round 2: small emissive eyes (#FF6A2A, the enemy-eye colour) plus a pale
    # sliver hinting at teeth in the mouth groove. Rigid props bound to the
    # head bone, same mechanism as the staff/orb attachment. The eye "at" is
    # measured against the actual rendered surface (diag_eye_raycast2.py cast
    # rays straight down through the intended socket): the socket bump's own
    # centre coordinate is a single interior vertex, not the visible surface,
    # which sits at y ~ 0.12-0.15 here, not the 0.062-0.086 the bump's control
    # point implied -- a first attempt buried the eye completely, invisible
    # from any angle (confirmed with the same raycast at a 15mm grid around it).
    decor=[dict(name="eye.R", bone="head", material="em_eye",
                at=(0.062, 0.148, 0.940), radius=(0.015, 0.012, 0.015)),
           dict(name="eye.L", bone="head", material="em_eye",
                at=(-0.062, 0.148, 0.940), radius=(0.015, 0.012, 0.015)),
           dict(name="teeth", bone="head", material="horn",
                at=(0.000, 0.113, 0.849), radius=(0.022, 0.006, 0.010))],
    creases=[dict(region="horn", value=0.35), dict(region="claw", value=0.55)],
    seams=[dict(line=("x", 0.0, 2e-3), side=("y", -1)),                       # centre back
           dict(radius=((0.300, 0.105, 0.615), 0.055)),                        # wrist R
           dict(radius=((-0.300, 0.105, 0.615), 0.055)),                       # wrist L
           dict(radius=((0.098, -0.035, 0.155), 0.060)),                       # hock R
           dict(radius=((-0.098, -0.035, 0.155), 0.060)),                      # hock L
           dict(radius=((0.000, -0.050, 0.858), 0.070)),                       # neck
           dict(region_border=("skin", "horn")),                               # horn bases
           dict(region_border=("skin", "claw"))],                              # claw bases
    bones=[
        dict(name="root", head=(0.0, 0.0, 0.0), tail=(0.0, 0.12, 0.0)),
        dict(name="hips", head=(0.0, 0.000, 0.440), tail=(0.0, 0.025, 0.530), parent="root"),
        dict(name="spine", head=(0.0, 0.025, 0.530), tail=(0.0, 0.010, 0.680), parent="hips", connect=True),
        dict(name="chest", head=(0.0, 0.010, 0.680), tail=(0.0, -0.070, 0.805), parent="spine", connect=True),
        dict(name="neck", head=(0.0, -0.070, 0.805), tail=(0.0, -0.030, 0.862), parent="chest", connect=True),
        dict(name="head", head=(0.0, -0.030, 0.862), tail=(0.0, 0.040, 0.975), parent="neck", connect=True),
        dict(name="horn.R", head=(0.075, -0.010, 0.958), tail=(0.095, -0.150, 1.010),
             parent="head", mirror=True),
        dict(name="shoulder.R", head=(0.045, -0.045, 0.800), tail=(0.150, -0.030, 0.795),
             parent="chest", mirror=True),
        dict(name="upperarm.R", head=(0.150, -0.030, 0.795), tail=(0.245, 0.015, 0.700),
             parent="shoulder.R", connect=True, mirror=True),
        dict(name="forearm.R", head=(0.245, 0.015, 0.700), tail=(0.300, 0.105, 0.615),
             parent="upperarm.R", connect=True, mirror=True),
        dict(name="hand.R", head=(0.300, 0.105, 0.615), tail=(0.320, 0.165, 0.565),
             parent="forearm.R", connect=True, mirror=True),
        dict(name="thigh.R", head=(0.085, 0.000, 0.440), tail=(0.105, 0.075, 0.300),
             parent="hips", mirror=True),
        dict(name="shin.R", head=(0.105, 0.075, 0.300), tail=(0.098, -0.035, 0.155),
             parent="thigh.R", connect=True, mirror=True),
        dict(name="foot.R", head=(0.098, -0.035, 0.155), tail=(0.098, 0.020, 0.048),
             parent="shin.R", connect=True, mirror=True),
        dict(name="toe.R", head=(0.098, 0.020, 0.048), tail=(0.098, 0.090, 0.028),
             parent="foot.R", connect=True, mirror=True),
        dict(name="tail1", head=(0.0, -0.105, 0.475), tail=(0.0, -0.210, 0.420), parent="hips"),
        dict(name="tail2", head=(0.0, -0.210, 0.420), tail=(0.0, -0.300, 0.320), parent="tail1", connect=True),
        dict(name="tail3", head=(0.0, -0.300, 0.320), tail=(0.0, -0.335, 0.140), parent="tail2", connect=True),
    ],
    # Round 3: claws get their own material (claw_nail) instead of sharing
    # "horn" -- a nail and a horn are both keratin but read very differently
    # (harder, glossier tip vs. fibrous matte base), which needs its own
    # roughness curve, not just a different UV tile of the same one.
    materials={"skin": "imp_skin", "horn": "horn", "claw": "claw_nail"},
    # Four poses that each exercise a different part of the rig. Signs were
    # verified against the rendered pose sheet, not guessed.
    poses=[
        ("arm lift", {"upperarm.R": (0, 0, -62), "forearm.R": (0, 0, -34),
                      "shoulder.R": (0, 0, -14), "upperarm.L": (0, 0, 24)}),
        ("spine twist", {"spine": (0, 34, 0), "chest": (0, 26, 0), "hips": (0, -10, 0),
                         "tail1": (0, 0, 30), "tail2": (0, 0, 24)}),
        ("head turn", {"head": (0, 0, 52), "neck": (0, 0, 22), "chest": (0, 0, 10)}),
        ("leg step", {"thigh.R": (0, 0, 42), "shin.R": (0, 0, -58), "foot.R": (0, 0, 26),
                      "thigh.L": (0, 0, -26), "shin.L": (0, 0, 16)}),
    ],
    cloth=None,
)


# ==================================================== the damned soul (1.8 m) ===
# Upright, robed and hooded, a bone mask grown out of the face and a staff held
# in the right hand. The cloak is not modelled: it is a lofted sheet dropped onto
# the body by the cloth solver and baked (see clothsim.py).
SOUL = dict(
    name="soul",
    label="Damned soul",
    height=1.8,
    nseg=12,
    stations=34,
    torso=dict(
        region="robe",
        u_hint=(1.0, 0.0, 0.0),
        ctrl=[(0.0,  0.000, 0.860),
              (0.0,  0.020, 1.020),
              (0.0,  0.010, 1.200),
              (0.0, -0.010, 1.340),
              (0.0, -0.020, 1.420),
              (0.0,  0.000, 1.500),
              (0.0,  0.020, 1.560),
              (0.0,  0.030, 1.660),
              (0.0,  0.010, 1.760)],
        keys=[key(0.00, rx=0.115, ry=0.095, power=2.2),
              key(0.18, rx=0.128, ry=0.108, power=2.2),
              key(0.30, rx=0.112, ry=0.098, power=2.0),
              key(0.38, rx=0.142, ry=0.112, power=2.2),
              key(0.53, rx=0.156, ry=0.106, power=2.3),
              key(0.62, rx=0.168, ry=0.100, power=2.5),
              key(0.71, rx=0.062, ry=0.062, power=2.0),
              key(0.78, rx=0.082, ry=0.094, power=2.1),
              key(0.89, rx=0.096, ry=0.104, power=2.2),
              key(1.00, rx=0.042, ry=0.046, power=2.0)],
    ),
    limbs=[
        dict(name="arm.R", region="robe", mirror=True, steps=11, ease=2,
             seed=dict(stations=(19, 21), segments=(11, 0)),
             ctrl=[(0.160, -0.015, 1.415), (0.300, 0.010, 1.180),
                   (0.400, 0.055, 0.960), (0.435, 0.075, 0.885)],
             keys=[key(0.00, rx=0.064, ry=0.064, power=2.2),
                   key(0.35, rx=0.052, ry=0.052, power=2.0),
                   key(0.70, rx=0.042, ry=0.042, power=2.0),
                   key(0.88, rx=0.048, ry=0.040, power=2.4),
                   key(1.00, rx=0.046, ry=0.034, power=2.6)],
             digits=[dict(pick=0, direction=(0.05, 0.70, -0.72), length=0.070,
                          radii=(0.015, 0.009, 0.003), steps=3, region="robe"),
                     dict(pick=2, direction=(0.30, 0.78, -0.55), length=0.062,
                          radii=(0.014, 0.008, 0.003), steps=3, region="robe"),
                     # Round 2: pick 3 is the outward-facing cap face -- the one
                     # nearest the staff line -- left empty in round 1, which is
                     # exactly why the grip read as open air beside the rod. This
                     # finger curls inward and down, closing over the staff.
                     dict(pick=3, direction=(-0.20, 0.55, -0.75), length=0.058,
                          radii=(0.013, 0.007, 0.003), steps=3, region="robe")],
             digit_sort_axis=(0.0, 0.0, 1.0)),
        dict(name="leg.R", region="robe", mirror=True, steps=12, ease=2,
             seed=dict(stations=(1, 3), segments=(11, 0)),
             ctrl=[(0.095, 0.000, 0.860), (0.105, 0.030, 0.480),
                   (0.100, 0.005, 0.090), (0.100, 0.105, 0.035)],
             keys=[key(0.00, rx=0.092, ry=0.092, power=2.2),
                   key(0.30, rx=0.076, ry=0.080, power=2.1),
                   key(0.62, rx=0.058, ry=0.062, power=2.0),
                   key(0.86, rx=0.050, ry=0.056, power=2.2),
                   key(1.00, rx=0.054, ry=0.044, power=2.6)]),
        # The bone mask is a shallow plate grown out of the face, so it sits on
        # the same surface and deforms with the head instead of hovering on it.
        dict(name="mask", region="mask", mirror=False, steps=3, ease=1,
             seed=dict(stations=(25, 28), segments=(2, 3)),
             ctrl=[(0.0, 0.092, 1.606), (0.0, 0.122, 1.600), (0.0, 0.140, 1.588)],
             keys=[key(0.00, rx=0.080, ry=0.066, power=3.0),
                   key(0.60, rx=0.078, ry=0.062, power=3.2),
                   key(1.00, rx=0.060, ry=0.046, power=3.0)]),
    ],
    bumps=[dict(center=(0.000,  0.112, 1.230), radius=0.120, offset=(0.0, 0.026, 0.0)),
           dict(center=(0.000, -0.105, 1.330), radius=0.130, offset=(0.0, -0.030, 0.010)),
           dict(center=(0.162, -0.018, 1.412), radius=0.090, offset=(0.034, 0.0, 0.018)),
           dict(center=(-0.162, -0.018, 1.412), radius=0.090, offset=(-0.034, 0.0, 0.018)),
           dict(center=(0.000,  0.030, 1.060), radius=0.100, offset=(0.0, 0.0, -0.012)),
           # The hood: the skull is pulled up and back into a cowl point.
           dict(center=(0.000, -0.040, 1.720), radius=0.110, offset=(0.0, -0.030, 0.030)),
           dict(center=(0.000,  0.100, 1.680), radius=0.070, offset=(0.0, 0.020, 0.014)),
           # Round 2: the mask was a blank plate. Two narrow eye-slit dents (dark
           # decor nested inside them, see `decor`) and a rolled lip at the chin
           # point of the mask give it a front edge instead of a smooth ellipse.
           # Centres and radius were measured off the actual grown surface
           # (diag_mask.py) rather than guessed from the skeleton curve -- the
           # mask balloons out to y~0.14-0.17 here, well past the ctrl chain
           # itself, and a first attempt centred on the chain barely reached
           # any real vertices (radius 0.022 from a point 3-4 cm off surface).
           dict(center=(0.045, 0.155, 1.620), radius=0.035, offset=(0.0, -0.032, -0.008)),
           dict(center=(-0.045, 0.155, 1.620), radius=0.035, offset=(0.0, -0.032, -0.008)),
           dict(center=(0.000, 0.140, 1.588), radius=0.032, offset=(0.0, 0.010, 0.005))],
    # Round 3: the mask stayed a smooth plate under its own dents. No eye
    # sockets here -- the mask itself hides the face, the eye slits already
    # read as dark hollows -- but it needed hard structure of its own: a
    # brow-plate ridge and two cheek-plate facets (ellipsoidal, headsculpt.
    # bump_aniso, so they are wide flat planes and not round bumps), plus a
    # real bevelled chamfer on its outer boundary (headsculpt.
    # bevel_region_boundary) so the mask/robe seam is an actual two-segment
    # facet under light, not only a subdivision crease.
    aniso_bumps=[
        dict(center=(0.0, 0.115, 1.615), radii=(0.075, 0.030, 0.018), offset=(0.0, 0.012, 0.010),
             region="mask"),
        dict(center=(0.040, 0.100, 1.592), radii=(0.035, 0.030, 0.014), offset=(0.010, 0.006, -0.006),
             region="mask"),
        dict(center=(-0.040, 0.100, 1.592), radii=(0.035, 0.030, 0.014), offset=(-0.010, 0.006, -0.006),
             region="mask"),
        dict(center=(0.0, 0.135, 1.585), radii=(0.030, 0.025, 0.014), offset=(0.0, 0.010, 0.006),
             region="mask"),
    ],
    bevels=[dict(region="mask", region_other="robe", width=0.006, segments=2)],
    creases=[dict(region="mask", value=0.45)],
    seams=[dict(line=("x", 0.0, 2e-3), side=("y", -1)),
           dict(radius=((0.000, 0.000, 1.502), 0.085)),
           dict(region_border=("robe", "mask"))],
    # Round 2: dark eye slits nested in the mask dents -- not emissive, the
    # bone mask hides the face behind it, but the hollows have to read as dark
    # so the hood is legible as a face and not a plate.
    decor=[dict(name="eyeslit.R", bone="head", material="hood_inside",
                at=(0.045, 0.121, 1.620), radius=(0.026, 0.013, 0.017)),
           dict(name="eyeslit.L", bone="head", material="hood_inside",
                at=(-0.045, 0.121, 1.620), radius=(0.026, 0.013, 0.017))],
    bones=[
        dict(name="root", head=(0.0, 0.0, 0.0), tail=(0.0, 0.20, 0.0)),
        dict(name="hips", head=(0.0, 0.000, 0.880), tail=(0.0, 0.020, 1.020), parent="root"),
        dict(name="spine", head=(0.0, 0.020, 1.020), tail=(0.0, 0.010, 1.200), parent="hips", connect=True),
        dict(name="chest", head=(0.0, 0.010, 1.200), tail=(0.0, -0.015, 1.420), parent="spine", connect=True),
        dict(name="neck", head=(0.0, -0.015, 1.420), tail=(0.0, 0.005, 1.510), parent="chest", connect=True),
        dict(name="head", head=(0.0, 0.005, 1.510), tail=(0.0, 0.025, 1.700), parent="neck", connect=True),
        dict(name="shoulder.R", head=(0.050, -0.020, 1.420), tail=(0.160, -0.015, 1.415),
             parent="chest", mirror=True),
        dict(name="upperarm.R", head=(0.160, -0.015, 1.415), tail=(0.300, 0.010, 1.180),
             parent="shoulder.R", connect=True, mirror=True),
        dict(name="forearm.R", head=(0.300, 0.010, 1.180), tail=(0.400, 0.055, 0.960),
             parent="upperarm.R", connect=True, mirror=True),
        dict(name="hand.R", head=(0.400, 0.055, 0.960), tail=(0.440, 0.080, 0.870),
             parent="forearm.R", connect=True, mirror=True),
        dict(name="thigh.R", head=(0.095, 0.000, 0.870), tail=(0.105, 0.030, 0.480),
             parent="hips", mirror=True),
        dict(name="shin.R", head=(0.105, 0.030, 0.480), tail=(0.100, 0.005, 0.095),
             parent="thigh.R", connect=True, mirror=True),
        dict(name="foot.R", head=(0.100, 0.005, 0.095), tail=(0.100, 0.115, 0.040),
             parent="shin.R", connect=True, mirror=True),
    ],
    materials={"robe": "cloak", "mask": "mask"},
    # Round 2: the staff line moves ~1.8 cm inward (x) and ~1.0 cm back (y) so it
    # sits between the grip fingers (see arm.R digits pick 0/2/3) instead of past
    # them -- the "floats beside the hand" defect from the round-1 renders.
    attachments=[dict(name="staff", region="staff", material="staff_wood", bone="hand.R",
                      nseg=8, stations=16,
                      ctrl=[(0.452, 0.080, 0.180), (0.452, 0.078, 1.000),
                            (0.450, 0.076, 1.820)],
                      keys=[key(0.00, rx=0.018, ry=0.018, power=2.0),
                            key(0.50, rx=0.022, ry=0.022, power=2.0),
                            key(1.00, rx=0.019, ry=0.019, power=2.0)],
                      orb=dict(material="em_orb", radius=0.072, at=(0.450, 0.076, 1.895)))],
    cloth=dict(name="cloak", material="cloak", nseg=30, stations=22,
               open_front_deg=46.0, pin_rows=2,
               ctrl=[(0.0, -0.010, 1.455), (0.0, -0.010, 1.150),
                     (0.0, -0.010, 0.800), (0.0, -0.010, 0.430), (0.0, -0.010, 0.140)],
               keys=[key(0.00, rx=0.185, ry=0.150, power=2.1),
                     key(0.30, rx=0.230, ry=0.200, power=2.0),
                     key(0.65, rx=0.290, ry=0.255, power=2.0),
                     key(1.00, rx=0.350, ry=0.310, power=2.0)],
               sim=dict(frames=70, quality=8, mass=0.32, tension=14.0, bending=0.45,
                        air=1.1, collision_distance=0.010, self_collision=True)),
    poses=[
        ("arm lift", {"upperarm.R": (0, 0, -70), "forearm.R": (0, 0, -30),
                      "shoulder.R": (0, 0, -12)}),
        ("spine twist", {"spine": (0, 38, 0), "chest": (0, 26, 0), "hips": (0, -12, 0)}),
        ("head turn", {"head": (0, 0, 48), "neck": (0, 0, 20), "chest": (0, 0, 10)}),
        ("leg step", {"thigh.R": (0, 0, 40), "shin.R": (0, 0, -52), "foot.R": (0, 0, 22),
                      "thigh.L": (0, 0, -24), "shin.L": (0, 0, 14)}),
    ],
)


# ========================================================= the brute (2.4 m) ===
# Top-heavy: a huge chest, a small head sunk between the shoulders, and armour
# plates grown off the upper back as flattened slabs (superellipse power 4).
BRUTE = dict(
    name="brute",
    label="Brute",
    height=2.4,
    nseg=12,
    stations=34,
    torso=dict(
        region="flesh",
        u_hint=(1.0, 0.0, 0.0),
        ctrl=[(0.0,  0.000, 1.050),
              (0.0,  0.060, 1.280),
              (0.0,  0.040, 1.600),
              (0.0, -0.020, 1.850),
              (0.0, -0.060, 2.000),
              (0.0, -0.020, 2.080),
              (0.0,  0.040, 2.150),
              (0.0,  0.060, 2.240),
              (0.0,  0.030, 2.300)],
        keys=[key(0.00, rx=0.300, ry=0.240, power=2.3),
              key(0.18, rx=0.345, ry=0.300, power=2.2, dv=0.020),
              key(0.43, rx=0.425, ry=0.300, power=2.4),
              key(0.62, rx=0.490, ry=0.300, power=2.6),
              key(0.74, rx=0.525, ry=0.285, power=2.8),
              key(0.81, rx=0.135, ry=0.135, power=2.0),   # the sunken neck
              key(0.88, rx=0.150, ry=0.170, power=2.1),
              key(0.95, rx=0.145, ry=0.160, power=2.2),
              key(1.00, rx=0.060, ry=0.066, power=2.0)],
    ),
    limbs=[
        dict(name="arm.R", region="flesh", mirror=True, steps=11, ease=2,
             seed=dict(stations=(23, 25), segments=(11, 0)),
             ctrl=[(0.500, -0.040, 1.950), (0.780, 0.060, 1.550),
                   (0.880, 0.160, 1.150), (0.920, 0.220, 1.000)],
             # The forearm swells into a broad mitten before the fingers, or the
             # arm just tapers to a spike and the hand reads as a point.
             keys=[key(0.00, rx=0.175, ry=0.175, power=2.4),
                   key(0.35, rx=0.145, ry=0.145, power=2.2),
                   key(0.68, rx=0.112, ry=0.112, power=2.1),
                   key(0.84, rx=0.158, ry=0.126, power=2.8),
                   key(1.00, rx=0.152, ry=0.110, power=3.0)],
             digits=[dict(pick=0, direction=(0.05, 0.72, -0.70), length=0.175,
                          radii=(0.050, 0.030, 0.008), steps=3, region="flesh"),
                     dict(pick=1, direction=(0.30, 0.86, -0.42), length=0.195,
                          radii=(0.052, 0.032, 0.008), steps=3, region="flesh"),
                     dict(pick=2, direction=(0.12, 0.80, 0.56), length=0.160,
                          radii=(0.046, 0.028, 0.008), steps=3, region="flesh")],
             digit_sort_axis=(0.0, 0.0, 1.0)),
        dict(name="leg.R", region="flesh", mirror=True, steps=12, ease=2,
             seed=dict(stations=(1, 3), segments=(11, 0)),
             ctrl=[(0.190, 0.000, 1.050), (0.215, 0.050, 0.620),
                   (0.205, 0.000, 0.145), (0.205, 0.190, 0.060)],
             # Flattened and widened at the end so it is a foot, not a stump,
             # then three toes grown off the sole cap.
             keys=[key(0.00, rx=0.200, ry=0.200, power=2.3),
                   key(0.30, rx=0.170, ry=0.180, power=2.2),
                   key(0.62, rx=0.130, ry=0.140, power=2.1),
                   key(0.86, rx=0.118, ry=0.108, power=2.6),
                   key(1.00, rx=0.140, ry=0.085, power=3.4)],
             digits=[dict(pick=0, direction=(-0.34, 0.92, -0.18), length=0.135,
                          radii=(0.046, 0.028, 0.008), steps=3, region="flesh"),
                     dict(pick=1, direction=(0.00, 0.97, -0.16), length=0.150,
                          radii=(0.048, 0.030, 0.008), steps=3, region="flesh"),
                     dict(pick=2, direction=(0.34, 0.92, -0.18), length=0.135,
                          radii=(0.046, 0.028, 0.008), steps=3, region="flesh")],
             digit_sort_axis=(1.0, 0.0, 0.0)),
        # Armour slabs off the upper back, on segments the arm patch does not use.
        # Seeded low and outboard on rows the arm patch does not touch, then
        # arced OUT and DOWN over the deltoid. Growing them off the upper back
        # and upwards made them read as wings beside the head.
        dict(name="plate.R", region="plates", mirror=True, steps=5, ease=1,
             seed=dict(stations=(21, 23), segments=(10, 11)),
             ctrl=[(0.430, -0.130, 1.895), (0.615, -0.075, 1.955),
                   (0.745, 0.030, 1.900), (0.800, 0.120, 1.775)],
             keys=[key(0.00, rx=0.165, ry=0.075, power=4.0),
                   key(0.40, rx=0.205, ry=0.068, power=4.0),
                   key(0.75, rx=0.185, ry=0.056, power=4.0),
                   key(1.00, rx=0.120, ry=0.042, power=4.0)]),
    ],
    bumps=[dict(center=(0.000,  0.310, 1.640), radius=0.285, offset=(0.0, 0.105, 0.0)),
           dict(center=(0.205,  0.285, 1.690), radius=0.185, offset=(0.045, 0.072, 0.015)),
           dict(center=(-0.205, 0.285, 1.690), radius=0.185, offset=(-0.045, 0.072, 0.015)),
           dict(center=(0.000,  0.300, 1.700), radius=0.100, offset=(0.0, -0.058, 0.0)),   # sternum
           dict(center=(0.000, -0.310, 1.880), radius=0.300, offset=(0.0, -0.110, 0.040)),
           dict(center=(0.000,  0.080, 1.280), radius=0.240, offset=(0.0, 0.075, 0.0)),
           dict(center=(0.000,  0.175, 2.150), radius=0.105, offset=(0.0, 0.078, -0.030)),  # muzzle
           dict(center=(0.000,  0.150, 2.216), radius=0.085, offset=(0.0, 0.055, 0.022)),   # brow
           dict(center=(0.085,  0.120, 2.186), radius=0.060, offset=(0.0, -0.046, 0.0)),
           dict(center=(-0.085, 0.120, 2.186), radius=0.060, offset=(0.0, -0.046, 0.0)),
           # Round 2: the head was a smooth ball with a snout bolted on. A real
           # jaw pushed forward and down under the muzzle, and the existing
           # cheek pulls deepened further into proper sunken sockets, so the
           # head reads even at a distance where the emissive eyes are the only
           # sharp thing left in the silhouette.
           dict(center=(0.000,  0.145, 2.108), radius=0.100, offset=(0.0,  0.048, -0.028)),  # jaw
           dict(center=(0.075,  0.098, 2.192), radius=0.050, offset=(0.010, -0.040, -0.012)),  # eye socket R
           dict(center=(-0.075, 0.098, 2.192), radius=0.050, offset=(-0.010, -0.040, -0.012))],  # eye socket L
    # Round 3: real eye sockets (see the imp's identical note on the
    # mechanism and why seed_rings stays at 1). depth=0.015 measured out at
    # an ACHIEVED depth of ~0.020 m on this mesh (test_headsculpt.py).
    eye_sockets=[dict(name="eye.R", at=(0.075, 0.190, 2.21), rim_radius=0.048,
                      depth=0.015, region="flesh"),
                dict(name="eye.L", at=(-0.075, 0.190, 2.21), rim_radius=0.048,
                      depth=0.015, region="flesh")],
    # Round 3: brow ridges over each new socket, a zygomatic (cheekbone) arch
    # running diagonally toward the nose, a pulled-out-and-down jaw angle at
    # the mandible corner, and a temple hollow (negative offset) between the
    # brow and the ear -- all ellipsoidal pushes (headsculpt.bump_aniso) on
    # the existing surface, no added geometry.
    aniso_bumps=[
        dict(center=(0.075, 0.130, 2.205), radii=(0.060, 0.030, 0.022), offset=(0.0, 0.018, 0.014)),
        dict(center=(-0.075, 0.130, 2.205), radii=(0.060, 0.030, 0.022), offset=(0.0, 0.018, 0.014)),
        dict(center=(0.115, 0.100, 2.175), radii=(0.055, 0.040, 0.020), offset=(0.014, 0.006, 0.0)),
        dict(center=(-0.115, 0.100, 2.175), radii=(0.055, 0.040, 0.020), offset=(-0.014, 0.006, 0.0)),
        dict(center=(0.130, 0.090, 2.095), radii=(0.045, 0.045, 0.030), offset=(0.020, 0.010, -0.016)),
        dict(center=(-0.130, 0.090, 2.095), radii=(0.045, 0.045, 0.030), offset=(-0.020, 0.010, -0.016)),
        dict(center=(0.145, 0.070, 2.220), radii=(0.045, 0.040, 0.030), offset=(-0.014, -0.010, 0.0)),
        dict(center=(-0.145, 0.070, 2.220), radii=(0.045, 0.040, 0.030), offset=(0.014, -0.010, 0.0)),
    ],
    # Round 2: emissive eyes (#FF6A2A) bound to the head bone. Two different
    # measurements gave two different answers here: sampling nearby BMesh
    # vertices directly (diag_face_brute4.py) found one at y ~ -0.08 and a
    # first attempt sat the eye there, invisible from every angle; a ray cast
    # straight down through (x=0.075, z=2.21) against the actual face-
    # interpolated surface (diag_brute_eye_raycast.py, the same method that
    # found and fixed the identical problem on imp) lands at y ~ 0.18-0.21 --
    # a lone vertex near a bump is not the visible surface there, the
    # neighbouring faces are. The eye sits at that measured surface.
    decor=[dict(name="eye.R", bone="head", material="em_eye",
                at=(0.075, 0.190, 2.21), radius=(0.020, 0.015, 0.018)),
           dict(name="eye.L", bone="head", material="em_eye",
                at=(-0.075, 0.190, 2.21), radius=(0.020, 0.015, 0.018))],
    creases=[dict(region="plates", value=0.65)],
    seams=[dict(line=("x", 0.0, 3e-3), side=("y", -1)),
           dict(radius=((0.000, -0.020, 2.080), 0.180)),
           dict(region_border=("flesh", "plates"))],
    bones=[
        dict(name="root", head=(0.0, 0.0, 0.0), tail=(0.0, 0.30, 0.0)),
        dict(name="hips", head=(0.0, 0.000, 1.080), tail=(0.0, 0.050, 1.290), parent="root"),
        dict(name="spine", head=(0.0, 0.050, 1.290), tail=(0.0, 0.030, 1.620), parent="hips", connect=True),
        dict(name="chest", head=(0.0, 0.030, 1.620), tail=(0.0, -0.040, 1.980), parent="spine", connect=True),
        dict(name="neck", head=(0.0, -0.040, 1.980), tail=(0.0, 0.010, 2.090), parent="chest", connect=True),
        dict(name="head", head=(0.0, 0.010, 2.090), tail=(0.0, 0.050, 2.260), parent="neck", connect=True),
        dict(name="plate.R", head=(0.400, -0.120, 1.900), tail=(0.720, -0.005, 1.900),
             parent="chest", mirror=True),
        dict(name="shoulder.R", head=(0.180, -0.030, 1.950), tail=(0.500, -0.040, 1.950),
             parent="chest", mirror=True),
        dict(name="upperarm.R", head=(0.500, -0.040, 1.950), tail=(0.780, 0.060, 1.550),
             parent="shoulder.R", connect=True, mirror=True),
        dict(name="forearm.R", head=(0.780, 0.060, 1.550), tail=(0.880, 0.160, 1.150),
             parent="upperarm.R", connect=True, mirror=True),
        dict(name="hand.R", head=(0.880, 0.160, 1.150), tail=(0.925, 0.230, 0.985),
             parent="forearm.R", connect=True, mirror=True),
        dict(name="thigh.R", head=(0.190, 0.000, 1.060), tail=(0.215, 0.050, 0.620),
             parent="hips", mirror=True),
        dict(name="shin.R", head=(0.215, 0.050, 0.620), tail=(0.205, 0.000, 0.150),
             parent="thigh.R", connect=True, mirror=True),
        dict(name="foot.R", head=(0.205, 0.000, 0.150), tail=(0.205, 0.200, 0.065),
             parent="shin.R", connect=True, mirror=True),
    ],
    materials={"flesh": "brute_flesh", "plates": "plates"},
    poses=[
        ("arm lift", {"upperarm.R": (0, 0, -58), "forearm.R": (0, 0, -34),
                      "shoulder.R": (0, 0, -10)}),
        ("spine twist", {"spine": (0, 30, 0), "chest": (0, 22, 0), "hips": (0, -10, 0)}),
        ("head turn", {"head": (0, 0, 44), "neck": (0, 0, 18), "chest": (0, 0, 8)}),
        ("leg step", {"thigh.R": (0, 0, 36), "shin.R": (0, 0, -48), "foot.R": (0, 0, 20),
                      "thigh.L": (0, 0, -22), "shin.L": (0, 0, 12)}),
    ],
    cloth=None,
)


CHARACTERS = {c["name"]: c for c in (IMP, SOUL, BRUTE)}


def get(name):
    if name not in CHARACTERS:
        raise SystemExit("unknown character %r, have %s" % (name, sorted(CHARACTERS)))
    return CHARACTERS[name]
