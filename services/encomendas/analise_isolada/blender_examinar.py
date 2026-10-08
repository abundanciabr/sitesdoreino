"""Script próprio; autoexec do arquivo enviado permanece desabilitado."""
import bpy
import json
from mathutils import Vector
from pathlib import Path
import sys

source, prefix = sys.argv[sys.argv.index('--') + 1:]
out = Path('/saida')
if source.lower().endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=source, load_ui=False, use_scripts=False)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # O importador glTF do Blender 3.4 usa o alias retirado no NumPy 1.24.
    import numpy as np
    if 'bool' not in np.__dict__:
        np.bool = np.bool_
    bpy.ops.import_scene.gltf(filepath=source)

original = bpy.context.scene
objects = [o for o in original.objects if o.type == 'MESH']
details, points = [], []
for obj in objects:
    # Malha armazenada, sem executar drivers ou modificadores do projeto.
    mesh = obj.data
    mesh.calc_loop_triangles()
    uv = []
    for layer in mesh.uv_layers:
        values = [loop.uv[:] for loop in layer.data]
        uv.append({'nome': layer.name, 'coordenadas': len(values),
                   'min': [min(v[i] for v in values) for i in range(2)] if values else None,
                   'max': [max(v[i] for v in values) for i in range(2)] if values else None})
    pts = [obj.matrix_world @ v.co for v in mesh.vertices]
    points.extend(pts)
    details.append({'objeto': obj.name, 'vertices': len(mesh.vertices), 'arestas': len(mesh.edges),
                    'faces': len(mesh.polygons), 'triangulos': len(mesh.loop_triangles),
                    'materiais': [m.name if m else '' for m in mesh.materials], 'uv': uv,
                    'modificadores_nao_aplicados': [m.type for m in obj.modifiers]})
if not points:
    raise ValueError('Nenhuma geometria de malha foi encontrada.')
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
center = (lo + hi) / 2
extent = max(hi - lo)
extent = max(extent, .01)
measures = {'objetos': details, 'triangulos_total': sum(o['triangulos'] for o in details),
            'dimensoes_mundo': list(hi - lo), 'min_mundo': list(lo), 'max_mundo': list(hi),
            'unidade': original.unit_settings.system, 'escala_unidade': original.unit_settings.scale_length,
            'metodo': 'Malha armazenada e transformações dos objetos; modificadores e drivers não aplicados.',
            'texturas': [{'nome': i.name, 'dimensoes_px': list(i.size), 'embutida': bool(i.packed_file),
                          'disponivel': bool(i.has_data)} for i in bpy.data.images if i.type == 'IMAGE']}
# Cena nova: remove câmera, mundo, compositor e configurações de render do arquivo.
scene = bpy.data.scenes.new('Analise isolada')
bpy.context.window.scene = scene
for obj in objects:
    clean = bpy.data.objects.new(obj.name, obj.data.copy())
    clean.matrix_world = obj.matrix_world.copy()
    scene.collection.objects.link(clean)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 8
scene.cycles.device = 'CPU'
scene.cycles.use_denoising = False
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
world = bpy.data.worlds.new('Fundo neutro')
world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.65, .65, .65, 1)
scene.world = world
for direction in [(2, -3, 4), (-3, -1, 2)]:
    lamp = bpy.data.lights.new('Luz de análise', 'AREA')
    lamp.energy = 500
    lamp.shape = 'DISK'
    lamp.size = extent * 2
    obj = bpy.data.objects.new('Luz de análise', lamp)
    scene.collection.objects.link(obj)
    obj.location = center + Vector(direction) * extent
    obj.rotation_euler = (center - obj.location).to_track_quat('-Z', 'Y').to_euler()
camera = bpy.data.cameras.new('Camera de análise')
camera.type = 'ORTHO'
camera.ortho_scale = extent * 1.7
cam = bpy.data.objects.new('Camera de análise', camera)
scene.collection.objects.link(cam)
scene.camera = cam
images = []
(out / (prefix + '.json')).write_text(json.dumps({'medidas': measures, 'imagens': [],
    'aviso': 'Medidas extraídas; vistas ainda não geradas.'}, ensure_ascii=False))
for view, direction in [('frontal', (0, -1, 0)), ('lateral', (1, 0, 0)), ('perspectiva', (1, -1.5, 1))]:
    cam.location = center + Vector(direction).normalized() * extent * 3
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    filename = prefix + '-' + view + '.png'
    scene.render.filepath = str(out / filename)
    bpy.ops.render.render(write_still=True)
    images.append({'arquivo': filename, 'vista': view})
(out / (prefix + '.json')).write_text(json.dumps({'medidas': measures, 'imagens': images}, ensure_ascii=False))
