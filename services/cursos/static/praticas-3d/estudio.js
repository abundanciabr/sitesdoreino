import * as THREE from './bibliotecas/three-0.170.0/three.module.js';
import {OrbitControls} from './bibliotecas/three-0.170.0/OrbitControls.js';
import {GLTFLoader} from './bibliotecas/three-0.170.0/GLTFLoader.js';

export async function criar(host,modelo,receita,onVista,onFalha){
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
 renderer.setPixelRatio(Math.min(2,Math.max(1.5,devicePixelRatio)));renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.10;
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 const scene=new THREE.Scene();scene.background=new THREE.Color(modelo.apresentacao?.fundo||'#e5ebef');
 const camera=new THREE.PerspectiveCamera(36,1,.01,100),controls=new OrbitControls(camera,renderer.domElement);
 controls.enableDamping=false;controls.minDistance=1.1;controls.maxDistance=16;controls.maxPolarAngle=Math.PI*.92;
 renderer.domElement.style.touchAction='pan-y';controls.enabled=!matchMedia('(pointer:coarse)').matches;
 // Broad studio reflections reveal the authored finishes without an external HDR dependency.
 const studio=new THREE.Scene();studio.background=new THREE.Color('#758396');
 const wall=new THREE.Mesh(new THREE.BoxGeometry(14,10,14),new THREE.MeshStandardMaterial({color:'#a9b3bc',side:THREE.BackSide,roughness:1}));studio.add(wall);
 for(const [pos,scale,power,color] of [[[-4,4,2],[3,5,.1],8,'#eef6ff'],[[4,2,1],[2,5,.1],5,'#ffe5c3'],[[0,4,-4],[6,2,.1],7,'#cce5ff']]){
  const panel=new THREE.Mesh(new THREE.BoxGeometry(...scale),new THREE.MeshBasicMaterial({color:new THREE.Color(color).multiplyScalar(power)}));panel.position.fromArray(pos);panel.lookAt(0,0,0);studio.add(panel);
 }
 const pmrem=new THREE.PMREMGenerator(renderer),environment=pmrem.fromScene(studio,.045);scene.environment=environment.texture;pmrem.dispose();
 studio.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});scene.add(new THREE.HemisphereLight(0xeaf5ff,0x647681,.8));
 const key=new THREE.DirectionalLight(0xfff0dc,3.3);key.position.set(-3,6,5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-4;key.shadow.camera.right=4;key.shadow.camera.top=4;key.shadow.camera.bottom=-4;key.shadow.normalBias=.028;key.shadow.bias=-.0002;scene.add(key);
 const fill=new THREE.DirectionalLight(0xccedff,1.4);fill.position.set(4,3,-4);scene.add(fill);
 let item;
 try{item=(await new GLTFLoader().loadAsync(modelo.url)).scene;}catch(e){environment.dispose();renderer.dispose();renderer.forceContextLoss();controls.dispose();throw e;}
 const box=new THREE.Box3().setFromObject(item),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
 const framing=3.8/Math.max(size.x,size.y,size.z),group=new THREE.Group();group.add(item);item.position.sub(center);group.scale.setScalar(framing);scene.add(group);
 item.traverse(o=>{if(!o.isMesh)return;o.castShadow=true;o.receiveShadow=false;o.userData.baseScale=o.scale.clone();o.material=o.material.clone();o.userData.parte=o.userData.parte||o.material.name;o.userData.tom=Number(o.userData.tom)||1;o.userData.emissivo=o.material.emissiveIntensity>0&&o.material.emissive?.getHex()>0;});
 const floorY=-size.y*framing/2-.015;
 const floor=new THREE.Mesh(new THREE.PlaneGeometry(200,200),new THREE.ShadowMaterial({opacity:.065}));floor.rotation.x=-Math.PI/2;floor.position.y=floorY;floor.receiveShadow=true;scene.add(floor);
 const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d'),g=ctx.createRadialGradient(64,64,5,64,64,62);g.addColorStop(0,'rgba(46,66,79,.20)');g.addColorStop(1,'rgba(46,66,79,0)');ctx.fillStyle=g;ctx.fillRect(0,0,128,128);
 const shadowTex=new THREE.CanvasTexture(c),contact=new THREE.Mesh(new THREE.PlaneGeometry(Math.max(.8,size.x*framing*1.35),Math.max(.7,size.z*framing*1.45)),new THREE.MeshBasicMaterial({map:shadowTex,transparent:true,depthWrite:false}));contact.rotation.x=-Math.PI/2;contact.position.y=floorY+.002;scene.add(contact);
 host.replaceChildren(renderer.domElement);
 let disposed=false,autoFit=false,wireframe=false;
 const render=()=>{if(!disposed)renderer.render(scene,camera);};
 const defaultDirection=new THREE.Vector3(...(modelo.apresentacao?.direcao||[3.5,1.8,7])).normalize();
 group.updateMatrixWorld(true);const fitPoints=[];
 item.traverse(o=>{if(!o.isMesh)return;const points=o.geometry.getAttribute('position'),step=Math.max(1,Math.floor(points.count/500));for(let i=0;i<points.count;i+=step)fitPoints.push(new THREE.Vector3().fromBufferAttribute(points,i).applyMatrix4(o.matrixWorld));});
 const currentVista=()=>({posicao:camera.position.toArray(),alvo:controls.target.toArray()});
 function fitted(direction=defaultDirection){
  const target=new THREE.Vector3(0,.02,0),right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),direction).normalize(),up=new THREE.Vector3().crossVectors(direction,right).normalize();
  let distance=1.5;
  const vfov=Math.tan(THREE.MathUtils.degToRad(camera.fov/2)),aspect=camera.aspect||1;
  for(const point of fitPoints){const p=point.clone().sub(target);distance=Math.max(distance,p.dot(direction)+Math.abs(p.dot(up))/(vfov*.86),p.dot(direction)+Math.abs(p.dot(right))/(vfov*aspect*.86));}
  return {posicao:direction.clone().multiplyScalar(distance).add(target).toArray(),alvo:target.toArray()};
 }
 function setVista(v){camera.position.fromArray(v.posicao);controls.target.fromArray(v.alvo);controls.update();render();}
 const resize=()=>{if(!host.clientWidth||disposed)return;renderer.setSize(host.clientWidth,host.clientHeight,false);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();if(autoFit)setVista(fitted());else render();};
 const observer=new ResizeObserver(resize);observer.observe(host);
 function aplicar(r){item.traverse(o=>{if(!o.isMesh)return;const k=o.userData.parte;if(r.cores[k]){o.material.color.set(r.cores[k]).multiplyScalar(o.userData.tom);if(o.userData.emissivo)o.material.emissive.set(r.cores[k]).multiplyScalar(o.userData.tom);}o.scale.copy(o.userData.baseScale);if(k===modelo.forma.parte)o.scale[modelo.forma.eixo]*=r.proporcao;});render();}
 function mover(acao){
  autoFit=false;
  if(['reset','frente','lado','costas'].includes(acao)){const dir=acao==='reset'?defaultDirection:acao==='frente'?new THREE.Vector3(0,.03,1).normalize():acao==='lado'?new THREE.Vector3(1,.03,0).normalize():new THREE.Vector3(0,.03,-1).normalize();setVista(fitted(dir));onVista(currentVista());return;}
  const offset=camera.position.clone().sub(controls.target);
  if(acao==='esquerda'||acao==='direita'){offset.applyAxisAngle(new THREE.Vector3(0,1,0),acao==='esquerda'?-.3:.3);camera.position.copy(controls.target).add(offset);}
  if(acao==='aproximar'||acao==='afastar'){offset.multiplyScalar(acao==='aproximar'?.85:1.15);offset.clampLength(1.1,16);camera.position.copy(controls.target).add(offset);}
  if(acao.startsWith('mover-')){const v=new THREE.Vector3(acao==='mover-esquerda'?-.2:acao==='mover-direita'?.2:0,acao==='mover-cima'?.2:acao==='mover-baixo'?-.2:0,0);v.applyQuaternion(camera.quaternion);camera.position.add(v);controls.target.add(v);}
  controls.update();render();onVista(currentVista());
 }
 const defaultRecipe=!receita.vista||JSON.stringify(receita.vista)===JSON.stringify({posicao:[3.5,1.8,7],alvo:[0,0,0]});autoFit=defaultRecipe;
 camera.aspect=(host.clientWidth||960)/(host.clientHeight||600);camera.updateProjectionMatrix();setVista(defaultRecipe?fitted():receita.vista);aplicar(receita);resize();
 controls.addEventListener('start',()=>{autoFit=false;});controls.addEventListener('change',()=>{render();onVista(currentVista());});
 const lost=e=>{e.preventDefault();if(!disposed){onVista(currentVista());onFalha();}};renderer.domElement.addEventListener('webglcontextlost',lost);
 return {aplicar,mover,vista:currentVista,
  malha(){wireframe=!wireframe;item.traverse(o=>{if(o.isMesh)o.material.wireframe=wireframe;});render();return wireframe;},
  toque(){controls.enabled=!controls.enabled;renderer.domElement.style.touchAction=controls.enabled?'none':'pan-y';return controls.enabled;},
  async imagem(){render();return new Promise((res,rej)=>renderer.domElement.toBlob(b=>b?res(b):rej(new Error('Captura indisponível.')),'image/png'));},
  async glb(){const {GLTFExporter}=await import('./bibliotecas/three-0.170.0/GLTFExporter.js');const result=await new GLTFExporter().parseAsync(item,{binary:true});return new Blob([result],{type:'model/gltf-binary'});},
  dispose(){if(disposed)return;disposed=true;observer.disconnect();controls.dispose();renderer.domElement.removeEventListener('webglcontextlost',lost);item.traverse(o=>{if(o.isMesh){o.geometry.dispose();for(const v of Object.values(o.material))if(v?.isTexture)v.dispose();o.material.dispose();}});environment.dispose();floor.geometry.dispose();floor.material.dispose();contact.geometry.dispose();contact.material.dispose();shadowTex.dispose();key.shadow.map?.dispose();renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();}
 };
}
