const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/funil/sw.js', 'utf8');

test('avisos ja exibidos abrem a Trilha sem mudar os destinos de sugestoes', async () => {
  const handlers = {}, opened = [];
  vm.runInNewContext(source, {URL, self: {
    location: {href: 'https://meshcraft.top/sw.js', origin: 'https://meshcraft.top'},
    addEventListener: (name, fn) => handlers[name] = fn,
    clients: {matchAll: async () => [], openWindow: async (path) => opened.push(path)},
  }});
  for (const [caminho, esperado] of [
    ['/conquistas/', '/trilha/'],
    ['/conquistas/trilha/medalhas/', '/trilha/'],
    ['https://meshcraft.top/conquistas/', '/trilha/'],
    ['/forms/sugestoes/sugestoes/12', '/forms/sugestoes/sugestoes/12'],
  ]) {
    let pending;
    handlers.notificationclick({notification: {data: {caminho}, close() {}}, waitUntil: (p) => pending = p});
    await pending;
    assert.equal(opened.at(-1), esperado);
  }
});
