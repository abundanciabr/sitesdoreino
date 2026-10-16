"""Read export facts before a Blender/trimesh loader can repair geometry."""
import base64
import io
import json
import math
from pathlib import Path
import struct


IDENTITY = (1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)


def product(a,b):
    return tuple(sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4))


def transform(node):
    if 'matrix' in node:
        value = node['matrix']
        if len(value) != 16 or not all(math.isfinite(x) for x in value):
            raise ValueError('invalid_transform')
        return value
    x,y,z,w = node.get('rotation',[0,0,0,1])
    sx,sy,sz = node.get('scale',[1,1,1])
    tx,ty,tz = node.get('translation',[0,0,0])
    return ((1-2*y*y-2*z*z)*sx,(2*x*y+2*z*w)*sx,(2*x*z-2*y*w)*sx,0,
            (2*x*y-2*z*w)*sy,(1-2*x*x-2*z*z)*sy,(2*y*z+2*x*w)*sy,0,
            (2*x*z+2*y*w)*sz,(2*y*z-2*x*w)*sz,(1-2*x*x-2*y*y)*sz,0,tx,ty,tz,1)


def image_size(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data)>=24 and data[12:16]==b'IHDR':
        return list(struct.unpack('>II',data[16:24]))
    if data.startswith(b'\xff\xd8'):
        offset = 2
        while offset+4 <= len(data):
            if data[offset] != 255:
                raise ValueError('invalid_jpeg')
            while offset<len(data) and data[offset]==255:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in {0xD8,0xD9}:
                continue
            length = struct.unpack('>H',data[offset:offset+2])[0]
            if length < 2 or offset+length > len(data):
                raise ValueError('invalid_jpeg')
            if marker in {0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF}:
                height,width = struct.unpack('>HH',data[offset+3:offset+7])
                return [width,height]
            offset += length
    raise ValueError('unsupported_image')


def read(path):
    raw = Path(path).read_bytes()
    if len(raw)>50_000_000 or len(raw)<20 or struct.unpack('<4sII',raw[:12]) != (b'glTF',2,len(raw)):
        raise ValueError('invalid_glb')
    offset, manifest, binary = 12, None, None
    while offset < len(raw):
        size,kind = struct.unpack('<II',raw[offset:offset+8])
        offset += 8
        if size%4 or offset+size>len(raw):
            raise ValueError('invalid_chunk')
        chunk = raw[offset:offset+size]
        if kind == 0x4E4F534A:
            if manifest is not None or size>2_000_000:
                raise ValueError('invalid_manifest')
            manifest = json.loads(chunk)
        elif kind == 0x004E4942:
            if binary is not None:
                raise ValueError('invalid_binary')
            binary = chunk
        offset += size
    if not manifest or binary is None or manifest.get('extensionsRequired'):
        raise ValueError('unsupported_glb')
    buffers = manifest.get('buffers',[])
    if len(buffers)!=1 or buffers[0].get('uri') or buffers[0]['byteLength']>len(binary):
        raise ValueError('external_buffer')

    def view(index):
        item = manifest['bufferViews'][index]
        start,size = item.get('byteOffset',0),item['byteLength']
        if item.get('buffer') != 0 or min(start,size)<0 or start+size>buffers[0]['byteLength']:
            raise ValueError('invalid_view')
        return item,binary[start:start+size]

    def accessor(index,position=False):
        item = manifest['accessors'][index]
        if item.get('sparse') or item.get('normalized'):
            raise ValueError('unsupported_accessor')
        count = item['count']
        if type(count) is not int or not 0<=count<=600000:
            raise ValueError('accessor_budget')
        formats = {5121:'B',5123:'H',5125:'I',5126:'f'}
        kind = formats[item['componentType']]
        columns = 3 if position else 1
        if item['type'] != ('VEC3' if position else 'SCALAR') or (position and kind!='f'):
            raise ValueError('invalid_accessor')
        fmt = '<'+kind*columns
        width = struct.calcsize(fmt)
        info,data = view(item['bufferView'])
        stride,start = info.get('byteStride',width),item.get('byteOffset',0)
        if stride<width or stride>252 or start<0 or (count and start+(count-1)*stride+width>len(data)):
            raise ValueError('invalid_stride')
        return [struct.unpack_from(fmt,data,start+i*stride) for i in range(count)]

    def texture_info(material):
        result = []
        refs = [material.get('pbrMetallicRoughness',{}).get('baseColorTexture'),
                material.get('pbrMetallicRoughness',{}).get('metallicRoughnessTexture'),
                material.get('normalTexture'),material.get('occlusionTexture'),material.get('emissiveTexture')]
        for ref in filter(None,refs):
            image = manifest['images'][manifest['textures'][ref['index']]['source']]
            uri = image.get('uri')
            if uri and not uri.startswith('data:'):
                result.append({'size':[0,0],'missing':True})
                continue
            if uri:
                header,body = uri.split(',',1)
                if ';base64' not in header or len(body)>50_000_000:
                    raise ValueError('invalid_image_uri')
                data = base64.b64decode(body,validate=True)
            else:
                _,data = view(image['bufferView'])
            result.append({'size':image_size(data),'missing':False})
        return result

    nodes = manifest.get('nodes',[])
    scenes = manifest.get('scenes',[])
    roots = scenes[manifest.get('scene',0)]['nodes'] if scenes else [i for i in range(len(nodes)) if not any(i in n.get('children',[]) for n in nodes)]
    output, stack = [],[(i,IDENTITY,frozenset()) for i in roots]
    while stack:
        index,parent,ancestors = stack.pop()
        if type(index) is not int or not 0<=index<len(nodes) or index in ancestors or len(ancestors)>128:
            raise ValueError('invalid_node')
        node = nodes[index]
        if 'skin' in node or node.get('extensions'):
            raise ValueError('unsupported_node')
        world = product(parent,transform(node))
        if not all(math.isfinite(x) for x in world):
            raise ValueError('invalid_transform')
        stack += [(i,world,ancestors|{index}) for i in node.get('children',[])]
        if 'mesh' not in node:
            continue
        if len(output)>=256:
            raise ValueError('mesh_budget')
        source = manifest['meshes'][node['mesh']]
        vertices,faces,materials,textures = [],[],set(),[]
        for primitive in source['primitives']:
            if primitive.get('mode',4)!=4 or primitive.get('extensions') or primitive.get('targets'):
                raise ValueError('unsupported_primitive')
            points = accessor(primitive['attributes']['POSITION'],True)
            indices = [i[0] for i in accessor(primitive['indices'])] if 'indices' in primitive else list(range(len(points)))
            if len(indices)%3 or any(type(i) is not int or not 0<=i<len(points) for i in indices):
                raise ValueError('invalid_indices')
            first = len(vertices)
            vertices += [[world[0]*x+world[4]*y+world[8]*z+world[12],
                          world[1]*x+world[5]*y+world[9]*z+world[13],
                          world[2]*x+world[6]*y+world[10]*z+world[14]] for x,y,z in points]
            faces += [[first+i for i in indices[j:j+3]] for j in range(0,len(indices),3)]
            if len(vertices)>300000 or len(faces)>200000:
                raise ValueError('geometry_budget')
            if 'material' in primitive and primitive['material'] not in materials:
                material = manifest['materials'][primitive['material']]
                materials.add(primitive['material'])
                textures += texture_info(material)
        output.append({'name':node.get('name',source.get('name','Mesh')), 'vertices':vertices,
                       'faces':faces,'materials':sorted(materials),'textures':textures})
    return {'meshes':output,'author_polygons_preserved':False,'format':'.glb'}
