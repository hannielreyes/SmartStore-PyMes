import inspect
import flet_camera as fc
print('flet_camera version:', getattr(fc, '__version__', 'no-version'))
Camera = fc.Camera
print('Camera public members:')
members = [name for name in dir(Camera) if not name.startswith('_')]
for m in members:
    print(m)
