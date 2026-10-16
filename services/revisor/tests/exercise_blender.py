"""Trusted generated corpus; invoke Blender headless, never an HTTP server."""
import json
from pathlib import Path
import sys
import tempfile
import time

args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root/'tests')]
if args:
    sys.path.insert(0,args[0])  # Test dependency directory, supplied by the operator.

import bpy
from revisor.engine import inspect
from revisor.importer_blender import extract, validate_envelope
from fixtures import FACES, glb, export_fbx_examples


def main():
    proofs = []
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        variants = {'clean':FACES, 'open':FACES[:-1], 'inverted':[f[::-1] for f in FACES],
                    'winding':[FACES[0][::-1],*FACES[1:]], 'duplicate':[*FACES,FACES[0]]}
        for name,faces in variants.items():
            path = directory/(name+'.glb')
            glb(path,faces=faces)
            start = time.monotonic()
            report = inspect(extract(path),'game')
            codes = {f['code'] for f in report['findings']}
            required = {'open':{'open_edges'},'inverted':{'inverted_component'},
                        'winding':{'winding'},'duplicate':{'duplicate_faces','non_manifold'}}.get(name,set())
            assert required <= codes,(name,codes)
            assert report['triangles'] == len(faces)
            assert not report['coverage_complete']
            proofs.append({'file':path.name,'triangles':report['triangles'],'codes':sorted(codes),
                           'seconds':round(time.monotonic()-start,3)})
        export_fbx_examples(directory)
        preserved = inspect(extract(directory/'ngon.fbx'),'game')
        assert any(c['code']=='ngons' and c['state']=='fail' for c in preserved['checks'])
        triangulated = inspect(extract(directory/'triangulated.fbx'),'game')
        assert any(c['code']=='ngons' and c['state']=='unverifiable' for c in triangulated['checks'])
        proofs += [{'file':'ngon.fbx','ngon_detected':True},{'file':'triangulated.fbx','original_topology_unknown':True}]
        bad = directory/'corrupted.glb'
        bad.write_bytes(b'not a model')
        try:
            validate_envelope(bad)
            raise AssertionError('corrupted accepted')
        except ValueError:
            proofs.append({'file':bad.name,'rejected':True})
        giant = directory/'giant.glb'
        with giant.open('wb') as output:
            output.seek(50_000_000)
            output.write(b'x')
        try:
            validate_envelope(giant)
            raise AssertionError('giant accepted')
        except ValueError:
            proofs.append({'file':giant.name,'rejected_before_read':True})
    print('REVISOR_PROOF='+json.dumps({'blender':bpy.app.version_string,'proofs':proofs,'temporary_deleted':True}))


if __name__ == '__main__':
    main()
