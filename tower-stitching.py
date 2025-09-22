import subprocess
import os
import sys
import shutil

# -------------------------------
# Helper: run system commands
# -------------------------------
def run_cmd(cmd):
    print(f"\n>>> Running: {' '.join(cmd)}")
    colmap_platforms = r"C:\Users\Saikiran Eppa\Downloads\colmap-x64-windows-nocuda\plugins\platforms"
    env = os.environ.copy()
    env["QT_QPA_PLATFORM_PLUGIN_PATH"] = colmap_platforms
    # Replace 'colmap' with full path if present
    if cmd[0] == "colmap":
        cmd[0] = r"C:\Users\Saikiran Eppa\Downloads\colmap-x64-windows-nocuda\bin\colmap.exe"
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    for line in process.stdout:
        print(line, end="")
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

# -------------------------------
# Reconstruction Pipeline
# -------------------------------
def reconstruct_tower(images_dir, output_dir):
    db_path = os.path.join(output_dir, "database.db")
    sparse_dir = os.path.join(output_dir, "sparse")
    dense_dir = os.path.join(output_dir, "dense")
    mvs_dir = os.path.join(output_dir, "mvs")

    os.makedirs(sparse_dir, exist_ok=True)
    os.makedirs(dense_dir, exist_ok=True)
    os.makedirs(mvs_dir, exist_ok=True)

    # Step 1: Feature extraction
    run_cmd(["colmap", "feature_extractor", "--database_path", db_path, "--image_path", images_dir])

    # Step 2: Feature matching
    run_cmd(["colmap", "exhaustive_matcher", "--database_path", db_path])

    # Step 3: Sparse reconstruction
    run_cmd(["colmap", "mapper", "--database_path", db_path, "--image_path", images_dir, "--output_path", sparse_dir])

    # Step 4: Dense reconstruction
    run_cmd([
        "colmap", "image_undistorter",
        "--image_path", images_dir,
        "--input_path", os.path.join(sparse_dir, "0"),
        "--output_path", dense_dir,
        "--output_type", "COLMAP"
    ])
    run_cmd(["colmap", "patch_match_stereo", "--workspace_path", dense_dir,
             "--workspace_format", "COLMAP", "--PatchMatchStereo.geom_consistency", "true"])
    run_cmd([
        "colmap", "stereo_fusion",
        "--workspace_path", dense_dir,
        "--workspace_format", "COLMAP",
        "--input_type", "geometric",
        "--output_path", os.path.join(dense_dir, "fused.ply")
    ])

    # Step 5: Convert to MVS
    run_cmd(["InterfaceCOLMAP", "-i", dense_dir, "-o", os.path.join(mvs_dir, "scene.mvs")])

    # Step 6: Dense point cloud
    run_cmd(["DensifyPointCloud", os.path.join(mvs_dir, "scene.mvs")])

    # Step 7: Mesh reconstruction
    run_cmd(["ReconstructMesh", os.path.join(mvs_dir, "scene_dense.mvs")])

    # Step 8: Mesh texturing
    run_cmd(["TextureMesh", os.path.join(mvs_dir, "scene_dense_mesh.mvs")])

    mesh_path = os.path.join(mvs_dir, "scene_dense_mesh_texture.ply")
    print(f"\n✅ Reconstruction complete for {images_dir}!\nMesh: {mesh_path}")
    return mesh_path

# -------------------------------
# Blender Rendering Script Writer
# -------------------------------
def write_blender_script(script_path, mesh_path, output_image):
    blender_py = f"""
import bpy
import sys

# Clear scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import mesh
bpy.ops.import_mesh.ply(filepath=r"{mesh_path}")
obj = bpy.context.selected_objects[0]

# Center & scale
bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN', center='BOUNDS')
bpy.context.view_layer.objects.active = obj
bpy.ops.object.location_clear()
bpy.ops.object.rotation_clear()

# Auto-align tallest axis (make Z up)
dims = obj.dimensions
if dims[2] < max(dims[0], dims[1]):  # if Z not tallest
    if dims[0] > dims[1]:
        obj.rotation_euler[1] = 1.5708  # rotate 90° around Y
    else:
        obj.rotation_euler[0] = 1.5708  # rotate 90° around X

# Add camera (front view)
bpy.ops.object.camera_add(location=(0, -max(obj.dimensions)*3, max(obj.dimensions)))
camera = bpy.context.object
bpy.context.scene.camera = camera

# Add light
bpy.ops.object.light_add(type='SUN', location=(0, -5, 10))

# Render settings
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.filepath = r"{output_image}"

# Render
bpy.ops.render.render(write_still=True)
print("✅ Render saved:", r"{output_image}")
"""
    with open(script_path, "w") as f:
        f.write(blender_py)

# -------------------------------
# Batch Processor
# -------------------------------
def batch_process(parent_dir, output_parent):
    for folder_name in os.listdir(parent_dir):
        images_path = os.path.join(parent_dir, folder_name)
        if os.path.isdir(images_path):
            tower_out = os.path.join(output_parent, folder_name)
            os.makedirs(tower_out, exist_ok=True)

            print(f"\n=== Processing tower: {folder_name} ===")
            mesh_path = reconstruct_tower(images_path, tower_out)

            # Blender rendering
            render_img = os.path.join(tower_out, "final_tower.png")
            blender_script = os.path.join(tower_out, "render_tower.py")
            write_blender_script(blender_script, mesh_path, render_img)

            run_cmd([
                "blender", "-b", "-P", blender_script
            ])

            print(f"🎯 Final tower image ready: {render_img}")

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    parent_dir = "C:\\Users\\Saikiran Eppa\\OneDrive - Tectoro\\Desktop\\Drogo_projects\\Transmission power lines\\Tower-stitching\\Towers"   # parent folder with subfolders of images
    output_parent = "./tower_output"       # output results
    os.makedirs(output_parent, exist_ok=True)
    batch_process(parent_dir, output_parent)
