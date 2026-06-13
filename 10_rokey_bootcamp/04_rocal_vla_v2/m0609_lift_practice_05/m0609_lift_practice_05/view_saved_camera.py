import numpy as np
from PIL import Image

rgb = np.load("/tmp/wrist_camera_rgb.npy")

if rgb.shape[-1] == 4:
    rgb = rgb[..., :3]

if rgb.max() <= 1.0:
    rgb = (rgb * 255).astype(np.uint8)
else:
    rgb = rgb.astype(np.uint8)

Image.fromarray(rgb).save("/tmp/wrist_camera_rgb.png")
print("saved /tmp/wrist_camera_rgb.png")

depth = np.load("/tmp/wrist_camera_depth.npy")
depth = np.squeeze(depth)

valid = np.isfinite(depth)
d = depth.copy()
d[~valid] = 0

if d.max() > d.min():
    d_norm = (d - d.min()) / (d.max() - d.min())
else:
    d_norm = d

d_img = (d_norm * 255).astype(np.uint8)
Image.fromarray(d_img).save("/tmp/wrist_camera_depth.png")
print("saved /tmp/wrist_camera_depth.png")
