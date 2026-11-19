# ==============================================================================
# AW Pivot Snapper
# Author: Ashwath Jain
# Description: Quick bounding-box pivot alignment tool with multi-engine axis 
#              support (Unity/Unreal), LOD/collider pivot matching, and FBX export.
# ==============================================================================

import os
import maya.cmds as cmds

WINDOW_NAME = "aw_pivot_snapper_window"
WINDOW_TITLE = "AW Pivot Snapper"
SAVED_PATH_KEY = "aw_pivot_snapper_export_dir"

# Stored in memory when copying pivot between assets
copied_pivot = None

BTN_H = 32


def get_selection():
    """Helper to return current transform selection with a friendly warning."""
    sel = cmds.ls(selection=True, type="transform")
    if not sel:
        cmds.warning("Please select at least one object.")
        return []
    return sel


def get_current_axes():
    """Reads the active Up and Front axis from UI dropdowns."""
    up = "Y"
    front = "Z"
    
    if cmds.optionMenu("up_axis_menu", exists=True):
        up = cmds.optionMenu("up_axis_menu", query=True, value=True).strip()[0]
    if cmds.optionMenu("front_axis_menu", exists=True):
        front = cmds.optionMenu("front_axis_menu", query=True, value=True).strip()[0]
    
    # Whatever axis isn't Up or Front must be Side (X, Y, or Z)
    leftover = [ax for ax in ["X", "Y", "Z"] if ax != up and ax != front]
    side = leftover[0] if leftover else ("X" if up != "X" else "Y")
    
    return up, front, side


def apply_pivot(obj, piv):
    """Applies pivot in world space. For group/parent nodes with children, moves translation 
    while preserving child world positions so game engines (Unity/Unreal) read the pivot correctly."""
    children = cmds.listRelatives(obj, children=True, type="transform", fullPath=True) or []
    if children:
        unparented = cmds.parent(children, world=True)
        try:
            cmds.xform(obj, worldSpace=True, translation=piv)
            cmds.xform(obj, worldSpace=True, rotatePivot=piv, scalePivot=piv)
        finally:
            cmds.parent(unparented, obj)
    else:
        cmds.xform(obj, worldSpace=True, rotatePivot=piv, scalePivot=piv)


def snap_pivot(pos="bottom"):
    """Snaps pivot of selected objects to bounding box extremes based on active axes."""
    objs = get_selection()
    if not objs:
        return

    up_axis, front_axis, side_axis = get_current_axes()

    cmds.undoInfo(openChunk=True)
    try:
        for obj in objs:
            bbox = cmds.exactWorldBoundingBox(obj)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox

            center = {
                "X": (xmin + xmax) * 0.5,
                "Y": (ymin + ymax) * 0.5,
                "Z": (zmin + zmax) * 0.5
            }
            min_bounds = {"X": xmin, "Y": ymin, "Z": zmin}
            max_bounds = {"X": xmax, "Y": ymax, "Z": zmax}

            target = dict(center)

            if pos == "top":
                target[up_axis] = max_bounds[up_axis]
            elif pos == "bottom":
                target[up_axis] = min_bounds[up_axis]
            elif pos == "front":
                target[front_axis] = max_bounds[front_axis]
            elif pos == "back":
                target[front_axis] = min_bounds[front_axis]
            elif pos == "left":
                target[side_axis] = min_bounds[side_axis]
            elif pos == "right":
                target[side_axis] = max_bounds[side_axis]
            elif pos == "lb":
                target[up_axis] = min_bounds[up_axis]
                target[side_axis] = min_bounds[side_axis]
                target[front_axis] = min_bounds[front_axis]
            elif pos == "rb":
                target[up_axis] = min_bounds[up_axis]
                target[side_axis] = max_bounds[side_axis]
                target[front_axis] = min_bounds[front_axis]

            piv = [target["X"], target["Y"], target["Z"]]
            apply_pivot(obj, piv)

        print(f"Pivot snapped to {pos.upper()} on {len(objs)} object(s).")
    finally:
        cmds.undoInfo(closeChunk=True)


def copy_source_pivot():
    """Stores the world-space pivot of the first selected object."""
    global copied_pivot
    sel = cmds.ls(selection=True, type="transform")
    if not sel:
        cmds.warning("Select an object to copy its pivot from.")
        return

    source = sel[0]
    copied_pivot = {
        "name": source.split("|")[-1],
        "rp": cmds.xform(source, query=True, worldSpace=True, rotatePivot=True),
        "sp": cmds.xform(source, query=True, worldSpace=True, scalePivot=True)
    }

    if cmds.text("copy_status_lbl", exists=True):
        cmds.text("copy_status_lbl", edit=True, label=f"Copied: {copied_pivot['name']}")
    
    print(f"Copied pivot from '{copied_pivot['name']}'.")


def paste_target_pivot():
    """Applies the copied pivot to all selected objects."""
    global copied_pivot
    if not copied_pivot:
        cmds.warning("No pivot copied yet. Select a mesh and hit Copy Pivot first.")
        return

    targets = get_selection()
    if not targets:
        return

    cmds.undoInfo(openChunk=True)
    try:
        for item in targets:
            apply_pivot(item, copied_pivot["rp"])
        print(f"Pasted pivot to {len(targets)} object(s).")
    finally:
        cmds.undoInfo(closeChunk=True)


def group_over_selection():
    """Puts all selected objects into a clean new group with centered pivot."""
    sel = get_selection()
    if not sel:
        return

    cmds.undoInfo(openChunk=True)
    try:
        # Default group name based on first selected item
        lead_name = sel[0].split("|")[-1]
        clean_prefix = lead_name.split("_")[0]
        grp_name = f"{clean_prefix}_GRP"

        new_group = cmds.group(sel, name=grp_name)
        bbox = cmds.exactWorldBoundingBox(new_group)
        center_piv = [
            (bbox[0] + bbox[3]) * 0.5,
            (bbox[1] + bbox[4]) * 0.5,
            (bbox[2] + bbox[5]) * 0.5
        ]
        apply_pivot(new_group, center_piv)
        cmds.select(new_group)

        print(f"Created group '{new_group}' with centered pivot.")
    finally:
        cmds.undoInfo(closeChunk=True)


def move_to_origin():
    """Drops selected objects so their pivot rests at world origin (0, 0, 0)."""
    objs = get_selection()
    if not objs:
        return

    cmds.undoInfo(openChunk=True)
    try:
        for obj in objs:
            rp = cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)
            cmds.xform(obj, relative=True, translation=[-rp[0], -rp[1], -rp[2]])
        print(f"Moved {len(objs)} object(s) to world origin.")
    finally:
        cmds.undoInfo(closeChunk=True)


def freeze_transforms():
    """Standard freeze transforms on selected meshes."""
    objs = get_selection()
    if not objs:
        return

    cmds.undoInfo(openChunk=True)
    try:
        for obj in objs:
            cmds.makeIdentity(obj, apply=True, translate=True, rotate=True, scale=True, normal=False)
        print(f"Froze transforms on {len(objs)} object(s).")
    finally:
        cmds.undoInfo(closeChunk=True)


def reset_to_center():
    """Resets pivot back to geometry center."""
    snap_pivot("center")


def browse_folder():
    """Folder browser dialog."""
    res = cmds.fileDialog2(fileMode=3, caption="Choose Export Directory")
    if res:
        cmds.textField("export_dir_field", edit=True, text=res[0])


def save_folder():
    """Saves directory into Maya optionVar so it persists across sessions."""
    path = cmds.textField("export_dir_field", query=True, text=True)
    if path and os.path.isdir(path):
        cmds.optionVar(stringValue=(SAVED_PATH_KEY, path))
        print(f"Default export directory saved: {path}")
    else:
        cmds.warning("Please choose a valid existing folder first.")


def export_fbx():
    """Batch exports selected objects as clean FBX files."""
    sel = get_selection()
    if not sel:
        return

    out_dir = cmds.textField("export_dir_field", query=True, text=True)
    if not out_dir or not os.path.exists(out_dir):
        browse_folder()
        out_dir = cmds.textField("export_dir_field", query=True, text=True)
        if not out_dir:
            cmds.warning("Export cancelled - no directory specified.")
            return

    # Check for fbx plugin
    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
        try:
            cmds.loadPlugin("fbxmaya")
        except Exception as err:
            cmds.error(f"Failed to load Maya FBX plugin: {err}")
            return

    exported_count = 0
    for node in sel:
        short_name = node.split("|")[-1]
        out_file = os.path.join(out_dir, f"{short_name}.fbx").replace("\\", "/")

        cmds.select(node)
        try:
            cmds.file(out_file, force=True, options="v=0;", type="FBX export", exportSelected=True)
            exported_count += 1
            print(f"Exported: {out_file}")
        except Exception as e:
            cmds.warning(f"Could not export '{short_name}': {e}")

    cmds.select(sel)
    print(f"Export complete. {exported_count} FBX file(s) saved to '{out_dir}'.")


def show_ui():
    """Builds the main tool interface."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    win = cmds.window(
        WINDOW_NAME,
        title=WINDOW_TITLE,
        widthHeight=(320, 590),
        sizeable=True
    )

    main = cmds.columnLayout(adjustableColumn=True, rowSpacing=6, columnOffset=("both", 12))

    # --- Header ---
    cmds.separator(height=8, style="none")
    cmds.text(label="AW PIVOT SNAPPER", font="boldLabelFont", height=20)
    cmds.text(label="Mobile Asset Prep for Unity & Unreal", font="smallPlainLabelFont")
    cmds.separator(height=10, style="in")

    # --- Axis Selection ---
    cmds.text(label="Axis Orientation:", align="left", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(146, 146))
    cmds.optionMenu("up_axis_menu", label="Up:     ", height=26)
    cmds.menuItem(label="Y  (Maya / Unity)")
    cmds.menuItem(label="Z  (Unreal)")
    cmds.menuItem(label="X")

    cmds.optionMenu("front_axis_menu", label="Front: ", height=26)
    cmds.menuItem(label="Z  (Maya / Unity)")
    cmds.menuItem(label="X  (Unreal)")
    cmds.menuItem(label="Y")
    cmds.setParent(main)

    cmds.separator(height=8, style="none")

    # --- Directional Pad ---
    # Top
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(96, 96, 96))
    cmds.text(label="")
    cmds.button(label="Top", height=BTN_H, width=96, command=lambda *_: snap_pivot("top"))
    cmds.text(label="")
    cmds.setParent(main)

    # Left / Center / Right
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(96, 96, 96))
    cmds.button(label="Left", height=BTN_H, width=96, command=lambda *_: snap_pivot("left"))
    cmds.button(label="Center", height=BTN_H, width=96, command=lambda *_: snap_pivot("center"))
    cmds.button(label="Right", height=BTN_H, width=96, command=lambda *_: snap_pivot("right"))
    cmds.setParent(main)

    # LB / Bottom / RB
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(96, 96, 96))
    cmds.button(label="LB", height=BTN_H, width=96, command=lambda *_: snap_pivot("lb"))
    cmds.button(label="Bottom", height=BTN_H, width=96, command=lambda *_: snap_pivot("bottom"))
    cmds.button(label="RB", height=BTN_H, width=96, command=lambda *_: snap_pivot("rb"))
    cmds.setParent(main)

    # Front / Back
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(146, 146))
    cmds.button(label="Front", height=BTN_H, width=146, command=lambda *_: snap_pivot("front"))
    cmds.button(label="Back", height=BTN_H, width=146, command=lambda *_: snap_pivot("back"))
    cmds.setParent(main)

    cmds.separator(height=10, style="shelf")

    # --- LOD / Collider Pivot Copy ---
    cmds.text(label="LOD & Collider Pivot Matcher:", align="left", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(146, 146))
    cmds.button(label="Copy Pivot", height=BTN_H, width=146, command=lambda *_: copy_source_pivot())
    cmds.button(label="Paste Pivot", height=BTN_H, width=146, command=lambda *_: paste_target_pivot())
    cmds.setParent(main)
    cmds.text("copy_status_lbl", label="No pivot copied yet", align="center", font="smallPlainLabelFont")

    cmds.separator(height=10, style="shelf")

    # --- Scene Prep Actions ---
    cmds.text(label="Asset Prep Actions:", align="left", font="smallBoldLabelFont")
    cmds.button(label="Create Group Over Selected", height=BTN_H, command=lambda *_: group_over_selection())
    cmds.button(label="Snap to Origin (0,0,0)", height=BTN_H, command=lambda *_: move_to_origin())

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(146, 146))
    cmds.button(label="Freeze Transforms", height=BTN_H, width=146, command=lambda *_: freeze_transforms())
    cmds.button(label="Reset Pivot", height=BTN_H, width=146, command=lambda *_: reset_to_center())
    cmds.setParent(main)

    cmds.separator(height=10, style="shelf")

    # --- Export Section ---
    cmds.text(label="Game Engine FBX Export:", align="left", font="smallBoldLabelFont")

    # Pre-fill with saved directory if available
    initial_path = ""
    if cmds.optionVar(exists=SAVED_PATH_KEY):
        initial_path = cmds.optionVar(query=SAVED_PATH_KEY)

    cmds.textField("export_dir_field", text=initial_path, height=BTN_H, placeholderText="Export Directory Path...")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(146, 146))
    cmds.button(label="Browse", height=BTN_H, width=146, command=lambda *_: browse_folder())
    cmds.button(label="Save Path", height=BTN_H, width=146, command=lambda *_: save_folder())
    cmds.setParent(main)

    cmds.button(label="Export Selected (FBX)", height=BTN_H, command=lambda *_: export_fbx())

    cmds.separator(height=8, style="none")
    cmds.showWindow(win)


if __name__ == "__main__":
    show_ui()
