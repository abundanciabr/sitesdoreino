"""Generate real GLB files; exported FBX fixtures use Blender's own exporter."""
import json
import struct


VERTICES = [(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
FACES = [(0,2,1),(0,1,3),(1,2,3),(2,0,3)]


def mesh(faces=None, vertices=None, **extra):
    return {'name':'Example', 'vertices':list(vertices or VERTICES), 'faces':list(FACES if faces is None else faces),
            'materials':[], 'textures':[], **extra}


def glb(path, vertices=VERTICES, faces=FACES):
    positions = b''.join(struct.pack('<3f',*v) for v in vertices)
    indices = b''.join(struct.pack('<H',i) for f in faces for i in f)
    binary = positions+indices
    binary += b'\0'*(-len(binary)%4)
    manifest = {'asset':{'version':'2.0'}, 'scene':0, 'scenes':[{'nodes':[0]}],
        'nodes':[{'mesh':0}], 'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
        'buffers':[{'byteLength':len(binary)}],
        'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':len(positions)},
                       {'buffer':0,'byteOffset':len(positions),'byteLength':len(indices)}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':len(vertices),'type':'VEC3',
                      'min':[min(v[i] for v in vertices) for i in range(3)],'max':[max(v[i] for v in vertices) for i in range(3)]},
                     {'bufferView':1,'componentType':5123,'count':sum(map(len,faces)),'type':'SCALAR'}]}
    doc = json.dumps(manifest).encode()
    doc += b' '*(-len(doc)%4)
    body = struct.pack('<II',len(doc),0x4e4f534a)+doc+struct.pack('<II',len(binary),0x004e4942)+binary
    path.write_bytes(struct.pack('<4sII',b'glTF',2,len(body)+12)+body)


def export_fbx_examples(directory):
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    data = bpy.data.meshes.new('Pentagon')
    data.from_pydata([(0,0,0),(1,0,0),(2,1,0),(1,2,0),(0,1,0)], [], [(0,1,2,3,4)])
    obj = bpy.data.objects.new('Pentagon',data)
    bpy.context.collection.objects.link(obj)
    bpy.ops.export_scene.fbx(filepath=str(directory/'ngon.fbx'), use_triangles=False)
    bpy.ops.export_scene.fbx(filepath=str(directory/'triangulated.fbx'), use_triangles=True)
