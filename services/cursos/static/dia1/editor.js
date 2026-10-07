import * as THREE from '../praticas-3d/bibliotecas/three-0.170.0/three.module.js';
import {OrbitControls} from '../praticas-3d/bibliotecas/three-0.170.0/OrbitControls.js';
import {criarFone,criarOrelhaEditavel} from './fone-gato.js?v=1';

// The same local Three.js runtime as the existing course practices.
export function criar(host,estado,onChange,onAction){
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));
 renderer.setClearColor('#343434');renderer.outputColorSpace=THREE.SRGBColorSpace;
 host.replaceChildren(renderer.domElement);
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.1,100);
 const controls=new OrbitControls(camera,renderer.domElement);controls.enablePan=false;controls.minDistance=3;controls.maxDistance=14;controls.minPolarAngle=.2;controls.maxPolarAngle=Math.PI*.9;
 controls.target.set(0,1.8,0);
 scene.add(new THREE.HemisphereLight(0xffffff,0x454351,2));const light=new THREE.DirectionalLight(0xffffff,3);light.position.set(3,6,5);scene.add(light);
 const grid=new THREE.GridHelper(14,28,0x697a71,0x494949);scene.add(grid);
 const axes=new THREE.AxesHelper(2);scene.add(axes);
 const base=criarFone({orelhas:false}),referencia=criarFone();referencia.visible=false;scene.add(base,referencia);
 const editavel=criarOrelhaEditavel(),mesh=editavel.corpo,outline=editavel.contorno;scene.add(editavel.grupo);
 let tool='girar',selected=true,drag=null,changed=false,silent=false;
 const render=()=>renderer.render(scene,camera);
 function vista(){const s=new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));return [s.theta,Math.PI/2-s.phi,s.radius];}
 function setVista(v){silent=true;const s=new THREE.Spherical(v[2],Math.PI/2-v[1],v[0]);camera.position.copy(new THREE.Vector3().setFromSpherical(s).add(controls.target));controls.update();silent=false;render();}
 function aplicar(o){
  editavel.aplicar(o);outline.visible=selected;render();
 }
 controls.addEventListener('change',()=>{render();if(!silent){estado.vista=vista();onChange();}});
 let startVista=null;
 controls.addEventListener('start',()=>{startVista=vista();});
 controls.addEventListener('end',()=>{if(!referencia.visible&&tool==='girar'&&startVista&&vista().some((v,i)=>Math.abs(v-startVista[i])>.01))onAction('girar');startVista=null;});
 const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();
 function hit(e){const r=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,camera);return ray.intersectObject(mesh).length>0;}
 renderer.domElement.addEventListener('pointerdown',e=>{
  if(tool==='girar'||referencia.visible)return;
  if(!hit(e))return;
  selected=true;outline.visible=true;
  drag={x:e.clientX,y:e.clientY,obj:structuredClone(estado.objeto),pointer:e.pointerId};changed=false;
  renderer.domElement.setPointerCapture(e.pointerId);render();
 });
 renderer.domElement.addEventListener('pointermove',e=>{
  if(!drag||drag.pointer!==e.pointerId)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y,unit=5/host.clientHeight,o={...drag.obj};
  if(tool==='esticar')o.altura=THREE.MathUtils.clamp(drag.obj.altura-dy*unit,.5,3);
  if(tool==='afinar')o.ponta=THREE.MathUtils.clamp(drag.obj.ponta+dx*unit,.03,1.5);
  if(tool==='mover'){o.x=THREE.MathUtils.clamp(drag.obj.x+dx*unit,-2.5,2.5);o.y=THREE.MathUtils.clamp(drag.obj.y-dy*unit,.3,3.5);}
  if(Math.abs(dx)+Math.abs(dy)<3)return;
  if(!changed){estado.historico.push(drag.obj);estado.historico=estado.historico.slice(-30);changed=true;}
  estado.objeto=o;aplicar(o);onChange(false);
 });
 function finish(e){if(!drag||drag.pointer!==e.pointerId)return;if(changed){onAction(tool);onChange();}drag=null;}
 renderer.domElement.addEventListener('pointerup',finish);renderer.domElement.addEventListener('pointercancel',finish);
 renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();host.setAttribute('aria-label','A vista 3D foi interrompida. Guarde e recarregue a aula para recuperar.');onChange();});
 const observer=new ResizeObserver(()=>{if(!host.clientWidth||!host.clientHeight)return;renderer.setSize(host.clientWidth,host.clientHeight,false);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();render();});observer.observe(host);
 setVista(estado.vista);aplicar(estado.objeto);
 return {aplicar,setReference(ativa){referencia.visible=ativa;base.visible=!ativa;editavel.grupo.visible=!ativa;controls.enabled=ativa||tool==='girar';renderer.domElement.style.cursor=ativa?'grab':tool==='girar'?'grab':tool==='mover'?'move':'ns-resize';render();},setTool(t){referencia.visible=false;base.visible=true;editavel.grupo.visible=true;tool=t;controls.enabled=t==='girar';renderer.domElement.style.cursor=t==='girar'?'grab':t==='mover'?'move':'ns-resize';},
  select(){selected=true;outline.visible=true;render();},front(){estado.vista=[0,.18,7];setVista(estado.vista);onChange();},
  rotate(delta){estado.vista[0]+=delta;setVista(estado.vista);onAction('girar');onChange();},
  show(){observer.disconnect();observer.observe(host);render();},
  dispose(){observer.disconnect();controls.dispose();renderer.dispose();renderer.forceContextLoss();scene.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});}
 };
}
