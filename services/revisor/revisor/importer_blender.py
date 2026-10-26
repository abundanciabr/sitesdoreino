"""Runs only inside the isolated parser; produces a report, not stored geometry."""
import json
from pathlib import Path
import struct
import sys


MAX_UPLOAD = 50_000_000


def validate_envelope(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {'.fbx', '.glb'}:
        raise ValueError('unsupported_type')
    if path.stat().st_size > MAX_UPLOAD:
        raise ValueError('too_large')
    if suffix == '.glb':
        with path.open('rb') as stream:
            header = stream.read(12)
            if len(header) != 12 or struct.unpack('<4sII', header) != (b'glTF', 2, path.stat().st_size):
                raise ValueError('invalid_glb')
            chunk = stream.read(8)
            if len(chunk) != 8:
                raise ValueError('invalid_glb')
            size, kind = struct.unpack('<II', chunk)
            if kind != 0x4E4F534A or size > 2_000_000:
                raise ValueError('invalid_glb')
            manifest = json.loads(stream.read(size))
        if any(x.get('uri') for x in manifest.get('buffers', [])):
            raise ValueError('external_geometry')
        if manifest.get('extensionsRequired'):
            raise ValueError('unsupported_extension')
    else:
        with path.open('rb') as stream:
            if stream.read(23) != b'Kaydara FBX Binary  \x00\x1a\x00':
                raise ValueError('invalid_fbx')
    return suffix


def extract(path):
    suffix = validate_envelope(path)
    if suffix == '.glb':
        from revisor.glb import read
        return read(path)
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        mesh = obj.data
        if len(mesh.vertices) > 300000 or len(mesh.polygons) > 200000:
            raise ValueError('geometry_budget')
        # Do not merge, remove doubles, validate/repair or evaluate modifiers.
        vertices = [list(obj.matrix_world @ v.co) for v in mesh.vertices]
        faces = [list(p.vertices) for p in mesh.polygons]
        materials = [m.name for m in mesh.materials if m is not None]
        textures = []
        seen = set()
        for material in mesh.materials:
            if not material or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None or node.image.name in seen:
                    continue
                image = node.image
                seen.add(image.name)
                size = list(image.size)
                # Only metadata goes into the report. No pixel or path output.
                textures.append({'size':size, 'missing':not all(size)})
        meshes.append({'name':obj.name, 'vertices':vertices, 'faces':faces,
                       'materials':materials, 'textures':textures})
    if not meshes:
        raise ValueError('empty_file')
    # FBX can preserve n-gons, but a file consisting only of triangles cannot
    # prove that the exporter did not destroy author polygons.
    preserved = suffix == '.fbx' and any(len(f)>3 for m in meshes for f in m['faces'])
    return {'meshes':meshes, 'author_polygons_preserved':preserved, 'format':suffix}


def main():
    args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    source, request_path, result_path = map(Path, args)
    from revisor.engine import inspect
    request = json.loads(request_path.read_text('utf-8'))
    try:
        report = inspect(extract(source), request['profile'], request.get('studs_per_unit'))
        result = {'state':'completed', 'report':report}
    except Exception:
        # Blender's input names/paths and raw exceptions never reach students/logs.
        result = {'state':'unreadable', 'reason':'cannot_read_file'}
    result_path.write_text(json.dumps(result, allow_nan=False, ensure_ascii=False), 'utf-8')


if __name__ == '__main__':
    main()
