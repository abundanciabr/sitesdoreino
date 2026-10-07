import * as THREE from '../praticas-3d/bibliotecas/three-0.170.0/three.module.js';

// Geometria real, sem textura: cada cor pertence a uma peça do fone.
const cores={magenta:0xd82cd9,roxo:0x962493,rosa:0xf345ed,amarelo:0xffd83a,branco:0xf8f5fa};
function material(cor){return new THREE.MeshStandardMaterial({color:cor,roughness:.7,metalness:0,flatShading:true});}
function peca(geo,mat,pai,nome,x=0,y=0,z=0){const m=new THREE.Mesh(geo,mat);m.name=nome;m.position.set(x,y,z);pai.add(m);return m;}

function arco(raio,largura,profundidade,z,mat,pai,nome){
 const pos=[],indices=[],faces=24;
 for(let i=0;i<=faces;i++){
  const a=Math.PI*i/faces;
  for(const r of [raio-largura/2,raio+largura/2])for(const d of [-profundidade/2,profundidade/2])pos.push(r*Math.cos(a),1.1+r*Math.sin(a),z+d);
 }
 for(let i=0;i<faces;i++){
  const a=i*4,b=a+4;
  for(const [p,q,r,s] of [[a,a+1,b+1,b],[a+2,b+2,b+3,a+3],[a,b,b+2,a+2],[a+1,a+3,b+3,b+1]])indices.push(p,q,r,p,r,s);
 }
 indices.push(0,2,3,0,3,1);const e=faces*4;indices.push(e,e+1,e+3,e,e+3,e+2);
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));geo.setIndex(indices);geo.computeVertexNormals();
 return peca(geo,mat,pai,nome);
}

function perfilOrelha(){const s=new THREE.Shape();s.moveTo(-.46,0);s.lineTo(-.45,.65);s.lineTo(-.32,1.06);s.lineTo(-.16,.99);s.lineTo(.12,.65);s.lineTo(.46,0);s.closePath();return s;}
export function orelhaPronta(lado=-1){
 const grupo=new THREE.Group();grupo.name=lado<0?'Orelha esquerda':'Orelha direita';
 const s=perfilOrelha();
 peca(new THREE.ExtrudeGeometry(s,{depth:.22,bevelEnabled:true,bevelThickness:.035,bevelSize:.035,bevelSegments:1,curveSegments:1}),[material(cores.magenta),material(cores.roxo)],grupo,'Borda magenta da orelha',0,0,-.11);
 const face=peca(new THREE.ShapeGeometry(s),material(cores.rosa),grupo,'Face rosa da orelha',0,.045,.148);face.scale.set(.84,.88,1);
 const centro=new THREE.Shape();centro.moveTo(-.26,.12);centro.lineTo(-.25,.5);centro.lineTo(-.17,.76);centro.lineTo(.02,.55);centro.lineTo(.24,.12);centro.closePath();
 peca(new THREE.ShapeGeometry(centro),material(cores.amarelo),grupo,'Interior amarelo da orelha',0,0,.154);
 if(lado>0)grupo.scale.x=-1;
 grupo.position.set(lado*.94,1.1+Math.sqrt(2.25-.94**2),0);return grupo;
}

export function criarFone({orelhas=true}={}){
 const fone=new THREE.Group();fone.name='Fone de gato colorido low poly';
 const magenta=material(cores.magenta),roxo=material(cores.roxo),rosa=material(cores.rosa),amarelo=material(cores.amarelo),branco=material(cores.branco);
 arco(1.5,.17,.39,.02,magenta,fone,'Arco magenta');
 arco(1.49,.095,.1,-.38,roxo,fone,'Arco posterior');
 for(const lado of [-1,1]){
  const concha=new THREE.Group();concha.name=lado<0?'Concha esquerda':'Concha direita';concha.position.set(lado*1.52,.77,.02);concha.rotation.y=lado<0?Math.PI/2-.55:-Math.PI/2;concha.rotation.x=lado*.08;fone.add(concha);
  // Local +Z aponta para a cabeça: almofada branca e centro rosa.
  const corpo=peca(new THREE.CylinderGeometry(.49,.49,.3,20,1),magenta,concha,'Concha magenta',0,0,-.13);corpo.rotation.x=Math.PI/2;corpo.scale.set(1,1,1.28);
  const borda=peca(new THREE.TorusGeometry(.43,.105,6,20),branco,concha,'Almofada branca',0,0,.08);borda.scale.set(.96,1.27,1);
  const miolo=peca(new THREE.CircleGeometry(.34,20),rosa,concha,'Centro rosa da almofada',0,0,.057);miolo.scale.set(.96,1.27,1);
  const tampa=peca(new THREE.CircleGeometry(.47,20),roxo,concha,'Tampa externa roxa',0,0,-.284);tampa.rotation.y=Math.PI;tampa.scale.set(1,1.28,1);
  const anel=peca(new THREE.TorusGeometry(.35,.058,4,20),amarelo,concha,'Aro amarelo externo',0,0,-.313);anel.scale.set(1,1.28,1);
  const detalhe=new THREE.Shape();detalhe.moveTo(-.16,-.22);detalhe.lineTo(.15,-.22);detalhe.lineTo(.03,.22);detalhe.lineTo(-.16,-.22);
  const emblema=peca(new THREE.ShapeGeometry(detalhe),amarelo,concha,'Detalhe amarelo triangular',0,0,-.319);emblema.rotation.y=Math.PI;
  const haste=peca(new THREE.BoxGeometry(.13,.42,.27),magenta,fone,'Encaixe do arco',lado*1.5,1.15,.02);haste.rotation.z=-lado*.12;
 }
 if(orelhas){fone.add(orelhaPronta(-1));fone.add(orelhaPronta(1));}
 return fone;
}

export function criarOrelhaEditavel(){
 const orelha=new THREE.Group();orelha.name='Sua primeira orelha';
 const corpo=peca(new THREE.BoxGeometry(.92,1,.24),[material(cores.roxo),material(cores.roxo),material(cores.magenta),material(cores.magenta),material(cores.rosa),material(cores.roxo)],orelha,'Forma editável');
 const miolo=peca(new THREE.BufferGeometry(),material(cores.amarelo),orelha,'Interior amarelo',0,0,.126);
 const contorno=new THREE.LineSegments(new THREE.EdgesGeometry(corpo.geometry),new THREE.LineBasicMaterial({color:0xffb05f}));corpo.add(contorno);
 function aplicar(o){
  const h=o.altura*.92,geo=new THREE.BoxGeometry(.92,h,.24),p=geo.attributes.position;
  for(let i=0;i<p.count;i++)if(p.getY(i)>0){p.setX(i,p.getX(i)*o.ponta);p.setZ(i,p.getZ(i)*o.ponta);}
  geo.computeVertexNormals();corpo.geometry.dispose();corpo.geometry=geo;
  contorno.geometry.dispose();contorno.geometry=new THREE.EdgesGeometry(geo);
  miolo.geometry.dispose();const inner=new THREE.BufferGeometry();
  inner.setAttribute('position',new THREE.Float32BufferAttribute([-.29,-h*.35,0,.29,-h*.35,0,Math.max(-.1,Math.min(.1,o.x*.02)),h*.32,0],3));inner.computeVertexNormals();miolo.geometry=inner;miolo.visible=o.ponta<.5;
  orelha.position.set(o.x,o.y+1.1+h/2,0);
 }
 return {grupo:orelha,corpo,contorno,aplicar};
}
