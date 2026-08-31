// static/funil/sw.js — o trabalhador de fundo do app instalado.
//
// Ele é servido em `/sw.js` (rota própria em config/urls.py, view
// `service_worker`), e NÃO em `/static/funil/sw.js`: o escopo de um service
// worker é a pasta de onde ele foi baixado, e de dentro de `/static/` ele só
// mandaria em `/static/`. O app precisa do escopo da raiz.
//
// O que ele faz, e só isto:
//
//   1. guarda uma cópia da página inicial, para que o app abra alguma coisa
//      quando o celular estiver sem rede;
//   2. atende navegação pedindo à REDE primeiro, sempre — a cópia só entra em
//      cena quando a rede falha.
//
// A ordem do item 2 é o ponto todo. Servir do cache primeiro deixaria o app
// mostrando uma página velha para quem está online, que é o modo clássico de
// um site instalado mentir sobre o próprio conteúdo. Aqui o cache é rede de
// segurança, nunca fonte de verdade.
//
// A página inicial chega pelo endereço deste arquivo (`/sw.js?inicio=/pt-br/`),
// posto por `static/funil/instalar.js`: o site é multilíngue e a home de quem
// instalou em espanhol não é a mesma de quem instalou em português. Endereço
// diferente é registro diferente, então trocar de idioma troca o trabalhador.

const CACHE = "meshcraft-inicio-v1";
const INICIO = new URL(self.location.href).searchParams.get("inicio") || "/";

self.addEventListener("install", (evento) => {
  // `skipWaiting` para que uma versão nova deste arquivo assuma no próximo
  // carregamento, em vez de esperar todas as abas fecharem.
  self.skipWaiting();
  evento.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.add(new Request(INICIO, { cache: "reload" })))
      // Falha ao guardar a cópia NÃO cancela a instalação: o app sem rede de
      // segurança ainda é um app que funciona online. Cancelar deixaria a
      // pessoa sem service worker nenhum por causa de uma falha de rede no
      // segundo em que ela instalou.
      .catch(() => undefined)
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nomes) =>
        Promise.all(nomes.filter((n) => n !== CACHE).map((n) => caches.delete(n)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  // Só navegação, e só GET. Tudo o mais (imagem, script, formulário postado,
  // chamada de API) passa direto para a rede, sem este arquivo no meio: um
  // service worker que intercepta tudo é um servidor extra para depurar no dia
  // em que algo der errado.
  if (pedido.method !== "GET" || pedido.mode !== "navigate") {
    return;
  }
  evento.respondWith(
    fetch(pedido)
      .then((resposta) => {
        if (resposta && resposta.ok && pedido.url === new URL(INICIO, self.location.origin).href) {
          const copia = resposta.clone();
          caches.open(CACHE).then((cache) => cache.put(INICIO, copia));
        }
        return resposta;
      })
      .catch(async () => {
        const cache = await caches.open(CACHE);
        const guardada = (await cache.match(pedido)) || (await cache.match(INICIO));
        if (guardada) {
          return guardada;
        }
        // Sem rede e sem cópia: devolver o erro de rede é honesto, e o
        // navegador mostra a própria tela de "sem conexão", que a pessoa já
        // conhece. Inventar uma página aqui seria uma tela a mais para
        // traduzir e manter.
        return Response.error();
      })
  );
});
