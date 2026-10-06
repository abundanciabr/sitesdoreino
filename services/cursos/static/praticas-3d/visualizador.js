import * as THREE from './bibliotecas/three-0.170.0/three.module.js';
import {OrbitControls} from './bibliotecas/three-0.170.0/OrbitControls.js';
import {GLTFLoader} from './bibliotecas/three-0.170.0/GLTFLoader.js';

export async function criar(host,modelo,receita,onVista,onFalha){
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.6));renderer.outputColorSpace=THREE.SRGBColorSpace;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#182635');
 const camera=new THREE.PerspectiveCamera(38,1,.01,100);const controls=new OrbitControls(camera,renderer.domElement);
 controls.enableDamping=false;controls.minDistance=1.2;controls.maxDistance=15;
 // One finger scrolls the course on touch devices until the student explicitly activates gestures.
 renderer.domElement.style.touchAction='pan-y';controls.enabled=!matchMedia('(pointer:coarse)').matches;
 scene.add(new THREE.HemisphereLight(0xffffff,0x51647c,2.8));
 const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(4,6,7);scene.add(light);
 const rim=new THREE.DirectionalLight(0xbbe4ff,2);rim.position.set(-4,2,-4);scene.add(rim);
 let item;try{item=(await new GLTFLoader().loadAsync(modelo.url)).scene;}catch(e){renderer.dispose();controls.dispose();throw e;}
 const box=new THREE.Box3().setFromObject(item);const center=box.getCenter(new THREE.Vector3());const size=box.getSize(new THREE.Vector3());
 const framing=3.6/Math.max(size.x,size.y,size.z);const group=new THREE.Group();group.add(item);item.position.sub(center);group.scale.setScalar(framing);scene.add(group);
 item.traverse(o=>{if(o.isMesh){o.userData.baseScale=o.scale.clone();o.material=o.material.clone();o.userData.parte=o.material.name;}});
 host.replaceChildren(renderer.domElement);
 const render=()=>renderer.render(scene,camera);
 const resize=()=>{if(!host.clientWidth)return;renderer.setSize(host.clientWidth,host.clientHeight,false);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();render();};
 const observer=new ResizeObserver(resize);observer.observe(host);
 const defaultVista={posicao:[3.5,1.8,7],alvo:[0,0,0]};
 function vista(v){camera.position.fromArray(v.posicao);controls.target.fromArray(v.alvo);controls.update();render();}
 const currentVista=()=>({posicao:camera.position.toArray(),alvo:controls.target.toArray()});
 controls.addEventListener('change',()=>{render();onVista(currentVista());});
 function aplicar(r){item.traverse(o=>{if(!o.isMesh)return;const k=o.userData.parte;if(r.cores[k])o.material.color.set(r.cores[k]);o.scale.copy(o.userData.baseScale);if(k===modelo.forma.parte)o.scale[modelo.forma.eixo]*=r.proporcao;});render();}
 function mover(acao){
  if(acao==='reset'){vista(defaultVista);return;}
  const offset=camera.position.clone().sub(controls.target);
  if(acao==='esquerda'||acao==='direita'){offset.applyAxisAngle(new THREE.Vector3(0,1,0),acao==='esquerda'?-.3:.3);camera.position.copy(controls.target).add(offset);}
  if(acao==='aproximar'||acao==='afastar'){offset.multiplyScalar(acao==='aproximar'?.85:1.15);offset.clampLength(1.2,15);camera.position.copy(controls.target).add(offset);}
  if(acao.startsWith('mover-')){const v=new THREE.Vector3(acao==='mover-esquerda'?-.2:acao==='mover-direita'?.2:0,acao==='mover-cima'?.2:acao==='mover-baixo'?-.2:0,0);v.applyQuaternion(camera.quaternion);camera.position.add(v);controls.target.add(v);}
  controls.update();render();onVista(currentVista());
 }
 vista(receita.vista||defaultVista);aplicar(receita);resize();
 renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();onVista(currentVista());onFalha();});
 return {aplicar,mover,vista:currentVista,toque(){controls.enabled=!controls.enabled;renderer.domElement.style.touchAction=controls.enabled?'none':'pan-y';return controls.enabled;},async imagem(){render();return new Promise((res,rej)=>renderer.domElement.toBlob(b=>b?res(b):rej(new Error('Captura indisponível.')),'image/png'));},async glb(){const {GLTFExporter}=await import('./bibliotecas/three-0.170.0/GLTFExporter.js');const result=await new GLTFExporter().parseAsync(item,{binary:true});return new Blob([result],{type:'model/gltf-binary'});},dispose(){observer.disconnect();controls.dispose();item.traverse(o=>{if(o.isMesh){o.geometry.dispose();o.material.dispose();}});renderer.dispose();renderer.domElement.remove();}};
}

