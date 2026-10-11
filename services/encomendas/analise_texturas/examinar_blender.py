"""Leitura real no Blender isolado, com autoexec desativado; nunca salva a entrada."""
import bpy
import json
import math
from mathutils import Vector
from pathlib import Path
import sys
from xml.sax.saxutils import escape
sys.path.insert(0,str(Path(__file__).resolve().parent))
from geometria_uv import assinatura_geometria,sobreposicoes
source,target=sys.argv[sys.argv.index('--')+1:]
out=Path(target)
out.mkdir(parents=True,exist_ok=True)
report={'versao':1,'estado':'concluida','blender':bpy.app.version_string,'achados':[],'objetos':[],'imagens':[],'limites':[],
        'metodo':'Arquivo aberto pelo Blender, com scripts desativados. Geometria avaliada sem salvar alterações.'}


def save():
    temp=out/'resultado.parcial'
    temp.write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    temp.replace(out/'resultado.json')


def finding(code,title,evidence,steps,obj='',level='conferir',image=''):
    report['achados'].append({'codigo':code,'titulo':title,'evidencia':evidence,'passos':steps,'objeto':obj,'nivel':level,'imagem':image,'chave':code+':'+obj})


def images_used(material):
    images,maps,unknown=[],set(),False
    if not material.use_nodes or not material.node_tree:
        return images,maps,unknown
    def walk(tree,roots,depth=0):
        nonlocal unknown
        if depth>8:
            unknown=True
            return
        pending,seen=list(roots),set()
        while pending:
            node=pending.pop()
            if node.as_pointer() in seen:
                continue
            seen.add(node.as_pointer())
            if node.type=='TEX_IMAGE':
                vector=node.inputs.get('Vector')
                uv_based=not vector or not vector.is_linked
                if vector and vector.is_linked:
                    parent=vector.links[0].from_node
                    if parent.type=='UVMAP':
                        maps.add(parent.uv_map)
                        uv_based=True
                    elif parent.type=='TEX_COORD':
                        uv_based=vector.links[0].from_socket.name=='UV'
                    else:
                        unknown=True
                images.append((node,uv_based))
            if node.type=='GROUP' and node.node_tree:
                unknown=True
                walk(node.node_tree,[n for n in node.node_tree.nodes if n.type=='GROUP_OUTPUT'],depth+1)
            for socket in node.inputs:
                pending.extend(link.from_node for link in socket.links)
    walk(material.node_tree,[n for n in material.node_tree.nodes if n.type=='OUTPUT_MATERIAL' and getattr(n,'is_active_output',True)])
    return images,maps,unknown


def available(image):
    if image.source=='GENERATED' or image.packed_file:
        return True
    if image.source!='FILE':
        return None
    return Path(bpy.path.abspath(image.filepath,library=image.library)).is_file()


def uv_diagram(index,layer,triangles,hits):
    points=[p for _,tri in triangles for p in tri]
    if not points:
        return ''
    lo=[min(p[i] for p in points) for i in range(2)]
    side=max(max(p[i] for p in points)-lo[i] for i in range(2)) or 1
    def xy(p):return (42+(p[0]-lo[0])/side*640,704-(p[1]-lo[1])/side*640)
    paths=[]
    for face,tri in triangles[:4000]:
        coords=' '.join('%.2f,%.2f'%xy(p) for p in tri)
        color='#f97316' if face in hits else '#70b8cf'
        paths.append('<polygon points="%s" fill="%s" fill-opacity=".08" stroke="%s" stroke-width="1.3"/>'%(coords,color,color))
    name='uv-%d.svg'%index
    svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 744 760"><rect width="744" height="760" fill="#171a24"/><text x="30" y="28" fill="#f1f5f9" font-family="sans-serif" font-size="18">Mapa UV: %s</text>%s<text x="30" y="743" fill="#f1f5f9" font-family="sans-serif" font-size="14">Laranja: faces com áreas compartilhadas. Azul: outras faces.</text></svg>'%(escape(layer.name[:70]),''.join(paths))
    (out/name).write_text(svg,encoding='utf-8')
    return name


try:
    bpy.ops.wm.open_mainfile(filepath=source,load_ui=False,use_scripts=False)
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if not objects:
        raise ValueError('Sem malhas')
    depsgraph=bpy.context.evaluated_depsgraph_get()
    signatures,previews,points={},[],[]
    total=0
    for index,obj in enumerate(objects[:100]):
        evaluated=obj.evaluated_get(depsgraph)
        mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            total+=len(mesh.loop_triangles)
            if total>200000:
                report['limites'].append('A leitura detalhada parou após 200 mil triângulos. Objetos restantes não foram verificados.')
                break
            world=[obj.matrix_world@v.co for v in mesh.vertices]
            if any(not all(math.isfinite(c) for c in p) for p in world):
                raise ValueError('Coordenadas inválidas')
            points.extend(world)
            tris3d=[[world[v] for v in t.vertices] for t in mesh.loop_triangles]
            if tris3d:
                signature=assinatura_geometria(tris3d)
                if signature in signatures:
                    other=signatures[signature]
                    finding('geometria_sobreposta','Duas peças ocupam o mesmo lugar',f'As superfícies de “{other}” e “{obj.name}” coincidem na leitura da geometria, com precisão de seis casas decimais.',
                        [f'Na lista de objetos do Blender, procure “{obj.name}” e “{other}”.','Em uma cópia do projeto, oculte uma dessas peças pelo ícone do olho e compare a aparência.','Se a cópia for intencional, mantenha-a. Se causar o problema, ajuste essa cópia e salve outro arquivo para conferir.'],obj.name)
                else:signatures[signature]=obj.name
            missing=sum(1 for p in mesh.polygons if p.material_index>=len(mesh.materials) or not mesh.materials[p.material_index])
            if missing:
                finding('faces_sem_material','Esta parte não tem material atribuído',f'“{obj.name}” tem {missing} faces sem material.',
                    [f'Selecione “{obj.name}” e abra Material Properties (ícone de esfera).','Em Edit Mode, selecione as faces, escolha o material correto e use Assign.','Confira em Material Preview e salve uma cópia para reenviar.'],obj.name,'encontrado')
            needs_uv,uncertain,used_images,map_names=False,False,[],set()
            material_uv_images={}
            for mid in sorted({p.material_index for p in mesh.polygons}):
                if mid>=len(mesh.materials) or not mesh.materials[mid]:continue
                material=mesh.materials[mid]
                nodes,names,unknown=images_used(material)
                uncertain|=unknown
                map_names.update(n for n in names if n)
                for node,uv_based in nodes:
                    needs_uv|=uv_based
                    image=node.image
                    if uv_based and image:
                        material_uv_images.setdefault(mid,set()).add(image.name)
                    present=available(image) if image else False
                    used_images.append({'material':material.name,'imagem':image.name if image else '', 'disponivel':present})
                    if present is False:
                        evidence=f'O material “{material.name}”, usado em “{obj.name}”, tem um nó Image Texture sem imagem.' if not image else f'A imagem “{image.name}”, ligada ao material “{material.name}” de “{obj.name}”, não está disponível junto deste arquivo.'
                        finding('imagem_indisponivel','Uma imagem usada na textura não está disponível',evidence,
                            [f'Abra “{material.name}” no Shader Editor e localize o nó Image Texture.','Se a imagem aparece no seu computador, use File → External Data → Pack Resources e salve uma cópia.','Se também estiver faltando no seu Blender, localize a imagem original e use Open nesse nó antes de salvar.','Envie a cópia com a imagem incluída para uma nova análise.'],obj.name,'encontrado')
                    elif present is None:report['limites'].append(f'Uma imagem de “{material.name}” usa sequência, vídeo ou outro tipo não conferido nesta versão.')
            layers=[layer for layer in mesh.uv_layers if layer.name in map_names]
            if needs_uv and not layers:
                active=next((layer for layer in mesh.uv_layers if layer.active_render),mesh.uv_layers.active)
                if active:layers=[active]
            for name in map_names:
                if name not in mesh.uv_layers:
                    finding('mapa_uv_ausente','O material aponta para um mapa que não existe',f'Um nó UV Map usado em “{obj.name}” referencia “{name}”, mas a malha não tem esse mapa.',
                        [f'Abra Object Data Properties → UV Maps de “{obj.name}” e confira os nomes.','No Shader Editor, selecione no nó UV Map o mapa que você realmente usa.','Confira em Material Preview e salve uma cópia.'],obj.name,'encontrado')
            if needs_uv and not mesh.uv_layers:
                finding('sem_uv','A imagem não tem um mapa de encaixe nesta malha',f'“{obj.name}” usa uma imagem com coordenadas UV, mas não tem mapa UV.',
                    [f'Selecione “{obj.name}”, abra UV Editing e entre em Edit Mode.','Selecione as faces que receberão a imagem e use UV → Unwrap conforme o formato do objeto.','Confira como as faces ficam sobre a imagem. Salve uma cópia e envie novamente.'],obj.name,'encontrado')
            stats=[]
            for layer_index,layer in enumerate(layers):
                triangles=[(int(t.polygon_index),[tuple(layer.data[i].uv) for i in t.loops]) for t in mesh.loop_triangles]
                if any(not all(math.isfinite(c) for c in p) for _,tri in triangles for p in tri):
                    report['limites'].append(f'Não foi possível ler o mapa “{layer.name}” de “{obj.name}”.')
                    continue
                groups={int(p.index):material_uv_images.get(p.material_index,set()) for p in mesh.polygons}
                overlap=sobreposicoes(triangles,groups=groups)
                diagram=uv_diagram(index*100+layer_index,layer,triangles,set(overlap['faces']))
                stats.append({'nome':layer.name,'faces_sobrepostas':len(overlap['faces']),'faces_sem_area':len(overlap['degeneradas']),'completa':overlap['completa'],'imagem':diagram,'exemplos_faces':[[a+1,b+1] for a,b in overlap['exemplos']]})
                if not overlap['completa']:report['limites'].append(f'A busca de sobreposições em “{obj.name}” foi parcial devido à complexidade da malha.')
                if len(triangles)>4000:report['limites'].append(f'O desenho UV de “{obj.name}” mostra apenas os primeiros 4 mil triângulos; a medida usa a leitura detalhada indicada acima.')
                if overlap['faces']:
                    finding('uv_compartilhada','Partes do objeto usam a mesma região da imagem',f'No mapa “{layer.name}” de “{obj.name}”, {len(overlap["faces"])} faces têm áreas UV sobrepostas. Pintar nessa região pode aparecer em mais de uma parte.',
                        [f'Selecione “{obj.name}”, abra UV Editing e entre em Edit Mode.','No UV Editor, use Select → Select Overlap (em algumas versões: Select All by Trait → Overlap).','Se deseja pinturas diferentes, selecione apenas as faces da parte que quer mudar e mova sua região UV para uma área adequada da textura.','Se o Mirror ainda gera a segunda parte, faça uma cópia e torne essa parte editável antes de reorganizar o mapa. Aplicar o Mirror sozinho não separa as UVs.','Se a repetição for intencional, mantenha esse encaixe. Caso ajuste, salve uma cópia e reenvie.'],obj.name,image=diagram)
                if overlap['degeneradas']:
                    finding('uv_sem_area','Há faces espremidas em um ponto ou linha da textura',f'O mapa “{layer.name}” de “{obj.name}” tem {len(overlap["degeneradas"])} faces com triângulos UV sem área.',
                        [f'No UV Editing, selecione as faces de “{obj.name}” que apresentam a textura esticada.','Confira se o desenho dessas faces virou uma linha ou ponto. Refaça o encaixe dessas faces em UV → Unwrap.','Salve uma cópia e envie novamente.'],obj.name,'encontrado',diagram)
            mirrors=[m.name for m in obj.modifiers if m.type=='MIRROR' and m.show_viewport]
            if mirrors:
                finding('mirror_presente','Este objeto usa espelhamento',f'“{obj.name}” usa Mirror: {", ".join(mirrors)}. A presença dele, sozinha, não indica erro.',
                    [f'Abra os modificadores de “{obj.name}” e confira qual parte o Mirror produz.','Se deseja a mesma pintura dos dois lados, o espelhamento pode estar correto.','Se deseja pinturas diferentes, confira as áreas UV das duas partes. Preserve o original antes de torná-las editáveis.'],obj.name,'informacao')
            if uncertain:report['limites'].append(f'“{obj.name}” usa grupos de nós ou transformações de coordenadas: a relação entre imagens e mapas UV precisa de conferência no Shader Editor.')
            report['objetos'].append({'nome':obj.name,'faces':len(mesh.polygons),'triangulos':len(mesh.loop_triangles),'mapas_uv':stats,'materiais':[m.name for m in mesh.materials if m],'imagens_usadas':used_images})
            clean=bpy.data.objects.new(obj.name,mesh.copy())
            clean.matrix_world=obj.matrix_world.copy()
            previews.append(clean)
        finally:evaluated.to_mesh_clear()
    if len(objects)>100:report['limites'].append('Esta leitura examinou os primeiros 100 objetos; há outros objetos no projeto.')
    report['achados']=list({(a['chave'],a['evidencia']):a for a in report['achados']}.values())
    report['limites']=list(dict.fromkeys(report['limites']))
    report['triangulos_examinados']=sum(o['triangulos'] for o in report['objetos'])
    save()
    if points and previews:
        scene=bpy.data.scenes.new('Diagnostico de textura')
        bpy.context.window.scene=scene
        for obj in previews:scene.collection.objects.link(obj)
        scene.render.engine='CYCLES'
        scene.cycles.samples=8
        scene.cycles.use_denoising=False
        scene.render.resolution_x=720
        scene.render.resolution_y=720
        scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG'
        world=bpy.data.worlds.new('Fundo da leitura')
        world.use_nodes=True
        world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.35,.35,1)
        scene.world=world
        lo=Vector([min(p[i] for p in points) for i in range(3)])
        hi=Vector([max(p[i] for p in points) for i in range(3)])
        center,extent=(lo+hi)/2,max(max(hi-lo),.01)
        for direction in [(2,-3,4),(-2,-1,2)]:
            data=bpy.data.lights.new('Luz de leitura','AREA')
            data.energy,data.size=500,extent*2
            lamp=bpy.data.objects.new('Luz de leitura',data)
            scene.collection.objects.link(lamp)
            lamp.location=center+Vector(direction)*extent
            lamp.rotation_euler=(center-lamp.location).to_track_quat('-Z','Y').to_euler()
        camera=bpy.data.cameras.new('Camera de leitura')
        camera.type,camera.ortho_scale='ORTHO',extent*1.55
        cam=bpy.data.objects.new('Camera de leitura',camera)
        scene.collection.objects.link(cam)
        scene.camera=cam
        for name,direction in [('frontal',(0,-1,0)),('perspectiva',(1,-1.5,1))]:
            cam.location=center+Vector(direction).normalized()*extent*3
            cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str(out/(name+'.png'))
            bpy.ops.render.render(write_still=True)
            report['imagens'].append({'arquivo':name+'.png','vista':name})
            save()
except Exception:
    if (out/'resultado.json').exists():
        report['limites'].append('As medidas foram extraídas, mas uma parte das vistas não pôde ser gerada.')
        save()
    else:
        report.update(estado='falha',achados=[],objetos=[],imagens=[],falha='Não consegui abrir o projeto ou examinar sua geometria. O original foi preservado. Confira a versão do Blender e tente uma cópia com as imagens incluídas.')
        save()
        sys.exit(2)
