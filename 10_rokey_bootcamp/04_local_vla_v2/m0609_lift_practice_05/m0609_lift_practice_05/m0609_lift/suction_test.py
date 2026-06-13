from pxr import UsdGeom, Gf
import omni.usd
import omni.kit.app

stage = omni.usd.get_context().get_stage()

SUCTION_TCP_PATH = "/World/m0609_suction_gripper/suction_tcp"
BOX_PATH = "/World/box"

suction_active = False
_update_sub = None

CONTACT_GAP = 0.002
SUCTION_Z_SIGN = -1

box_size = None


def get_prim(path):
    prim = stage.GetPrimAtPath(path)
    if not prim.IsValid():
        raise RuntimeError(f"Prim not found: {path}")
    return prim


def get_world_tf(path):
    return UsdGeom.Xformable(get_prim(path)).ComputeLocalToWorldTransform(0)


def get_box_gui_size():
    bbox_cache = UsdGeom.BBoxCache(
        0,
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
        useExtentsHint=False
    )
    bound = bbox_cache.ComputeWorldBound(get_prim(BOX_PATH))
    aligned_range = bound.ComputeAlignedRange()
    size = aligned_range.GetSize()
    return Gf.Vec3d(size[0], size[1], size[2])


def set_box_pose(pos, quat, size_vec):
    box = get_prim(BOX_PATH)
    xform = UsdGeom.Xformable(box)

    xform.ClearXformOpOrder()

    t_op = xform.AddTranslateOp(UsdGeom.XformOp.PrecisionDouble)
    q_op = xform.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
    s_op = xform.AddScaleOp(UsdGeom.XformOp.PrecisionDouble)

    t_op.Set(Gf.Vec3d(pos[0], pos[1], pos[2]))
    q_op.Set(quat)
    s_op.Set(Gf.Vec3d(size_vec[0], size_vec[1], size_vec[2]))


def get_target_box_pose():
    global box_size

    tcp_tf = get_world_tf(SUCTION_TCP_PATH)
    tcp_pos = tcp_tf.ExtractTranslation()

    suction_dir = tcp_tf.TransformDir(Gf.Vec3d(0, 0, SUCTION_Z_SIGN))
    suction_dir.Normalize()

    half_extent = (
        abs(suction_dir[0]) * box_size[0] * 0.5 +
        abs(suction_dir[1]) * box_size[1] * 0.5 +
        abs(suction_dir[2]) * box_size[2] * 0.5
    )

    box_center = tcp_pos + suction_dir * (half_extent + CONTACT_GAP)
    tcp_quat = tcp_tf.ExtractRotationQuat()

    return box_center, tcp_quat


def update_suction(event):
    if not suction_active:
        return

    pos, quat = get_target_box_pose()
    set_box_pose(pos, quat, box_size)


def suction_on():
    global suction_active, _update_sub, box_size

    box_size = get_box_gui_size()
    print("Using GUI box size:", box_size)

    suction_active = True

    if _update_sub is None:
        _update_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(update_suction)

    pos, quat = get_target_box_pose()
    set_box_pose(pos, quat, box_size)

    print("Suction ON: box face aligned to suction_tcp.")


def suction_off():
    global suction_active
    suction_active = False
    print("Suction OFF: box released.")


suction_on()