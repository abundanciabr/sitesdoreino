const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/funil/sw.js'), 'utf8');
function worker(fetch, inicio = '/') {
  const events = {}; let cachesOpened = 0;
  const home = {html: 'COPIA_ANTIGA_DA_HOME'};
  const context = vm.createContext({URL, Request, Response, fetch,
    self: {location: {href: 'https://meshcraft.top/sw.js?inicio='+encodeURIComponent(inicio), origin: 'https://meshcraft.top'},
      addEventListener: (name, callback) => events[name] = callback, skipWaiting() {}},
    caches: {open: async () => {cachesOpened++; return {match: async () => home};}}
  });
  vm.runInContext(source, context);
  return {navigate(url) {let response; events.fetch({request: {url, method: 'GET', mode: 'navigate'},
    respondWith(value) {response = value;}}); return response;}, opened: () => cachesOpened, home};
}
test('admin passa diretamente ao navegador, inclusive sem rede e com filtros', () => {
  let fetches = 0; const w = worker(async () => {fetches++; throw Error('sem rede');});
  for (const url of ['https://meshcraft.top/admin', 'https://meshcraft.top/admin/',
    'https://meshcraft.top/admin/crm/conversas/?canal=whatsapp']) {
    assert.equal(w.navigate(url), undefined);
  }
  assert.equal(fetches, 0); assert.equal(w.opened(), 0);
});
test('403 do servidor nao e trocado pela pagina inicial', async () => {
  const forbidden = new Response('Acesso restrito a administradores', {status: 403});
  const w = worker(async () => forbidden);
  const response = await w.navigate('https://meshcraft.top/');
  assert.equal(response, forbidden); assert.equal(response.status, 403); assert.equal(w.opened(), 0);
});
test('home conserva o recurso offline no proprio endereco', async () => {
  const w = worker(async () => {throw Error('sem rede');});
  assert.equal(await w.navigate('https://meshcraft.top/'), w.home);
});

for (const destino of ['/docs/', '/forms/sugestoes/', '/trilha/', '/forum/', '/login', '/?outra=pagina']) {
  test('nao substitui por home a navegacao para '+destino, () => {
    let fetches = 0;
    const w = worker(async () => {fetches++; throw Error('sem rede');});
    assert.equal(w.navigate('https://meshcraft.top'+destino), undefined);
    assert.equal(fetches, 0); assert.equal(w.opened(), 0);
  });
}
test('home de outro idioma nao substitui documentos nem a home de outro idioma',async()=>{
  const w = worker(async () => {throw Error('sem rede');}, '/en/');
  assert.equal(w.navigate('https://meshcraft.top/docs/'), undefined);
  assert.equal(w.navigate('https://meshcraft.top/'), undefined);
  assert.equal(await w.navigate('https://meshcraft.top/en/'), w.home);
});
