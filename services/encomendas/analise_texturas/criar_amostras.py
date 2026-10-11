"""Projetos de demonstração controlados; não são entregas de alunos."""
import bpy
from pathlib import Path
import sys
out=Path(sys.argv[sys.argv.index('--')+1])
out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh=bpy.data.meshes.new('Duas partes')
mesh.from_pydata([(-1,0,-1),(0,0,-1),(0,0,1),(-1,0,1),(0,0,-1),(1,0,-1),(1,0,1),(0,0,1)],[],[(0,1,2,3),(4,5,6,7)])
obj=bpy.data.objects.new('Escudo',mesh)
bpy.context.scene.collection.objects.link(obj)
uv=mesh.uv_layers.new(name='Mapa de textura')
left=[(0,0),(.5,0),(.5,1),(0,1)]
right=[(.5,0),(1,0),(1,1),(.5,1)]
for i,point in enumerate(left+left):uv.data[i].uv=point
image=bpy.data.images.new('Textura incluída',width=32,height=32)
image.generated_color=(.4,.2,.08,1)
image.pack()
mat=bpy.data.materials.new('Madeira')
mat.use_nodes=True
tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
tex.image=image
mat.node_tree.links.new(tex.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
mesh.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'uv-repetida.blend'))
for i,point in enumerate(left+right):uv.data[i].uv=point
bpy.ops.wm.save_as_mainfile(filepath=str(out/'uv-separada.blend'))
copy=obj.copy()
copy.data=obj.data.copy()
copy.name='Escudo.001'
bpy.context.scene.collection.objects.link(copy)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'peca-duplicada.blend'))
bpy.data.objects.remove(copy,do_unlink=True)
tex.image=None
bpy.ops.wm.save_as_mainfile(filepath=str(out/'imagem-ausente.blend'))
unused=mat.node_tree.nodes.new('ShaderNodeTexImage')
unused.name='Nó não ligado'
tex.image=image
bpy.ops.wm.save_as_mainfile(filepath=str(out/'no-nao-usado.blend'))
mesh.uv_layers.remove(uv)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'sem-uv.blend'))
(out/'invalido.blend').write_bytes(b'Este arquivo de teste nao e um projeto do Blender.')
