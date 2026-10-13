const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const net=require('node:net');
test('execução sem root, segredos, Docker, banco ou escrita no código',()=>{
 assert.equal(process.getuid(),65534);
 assert.match(fs.readFileSync('/proc/self/status','utf8'),/CapEff:\s+0000000000000000/);
 for(const p of ['/run/docker.sock','/opt/plataforma/env','/run/previa-env','/root/.ssh'])assert.equal(fs.existsSync(p),false);
 assert.equal(Object.keys(process.env).some(k=>/PASSWORD|SECRET|TOKEN|API_KEY|DATABASE_URL/.test(k)),false);
 assert.throws(()=>fs.writeFileSync('/work/index.html','changed'));
 assert.match(fs.readFileSync('/work/index.html','utf8'),/Prévia isolada funcionando/);
});
test('rede externa indisponível',async()=>{
 await new Promise((resolve,reject)=>{const s=net.connect({host:'1.1.1.1',port:443});s.on('connect',()=>{s.destroy();reject(Error('network available'));});s.on('error',()=>resolve());s.setTimeout(1000,()=>{s.destroy();resolve();});});
});
test('operação sobrevive ao fim da conexão SSH',async()=>{
 await new Promise(resolve=>setTimeout(resolve,10000));
});
