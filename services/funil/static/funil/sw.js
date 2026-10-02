// static/funil/sw.js — service worker do app instalado, servido em `/sw.js`.
// Guarda a página inicial para abrir sem rede; navegação vai à rede e cai na cópia se falhar.

const CACHE = "meshcraft-inicio-v1";
// A página inicial vem de `?inicio=` no endereço do registro.
const INICIO = new URL(self.location.href).searchParams.get("inicio") || "/";

self.addEventListener("install", (evento) => {
  // `skipWaiting`: uma versão nova assume no próximo carregamento.
  self.skipWaiting();
  evento.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.add(new Request(INICIO, { cache: "reload" })))
      // Falha ao guardar a cópia não cancela a instalação.
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
  // Só navegação GET; o resto passa direto para a rede.
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
        // Sem rede e sem cópia: devolve o erro de rede, e o navegador mostra a própria tela.
        return Response.error();
      })
  );
});

// O aviso na tela do aparelho: o `push` traz assunto e parâmetros; os textos vêm de
// `self.AVISOS_DO_SITE`, posto pela view `/sw.js` (o padrão cobre o arquivo servido cru).
const AVISOS = self.AVISOS_DO_SITE || {
  caminho: "/",
  textos: {},
  generico: { titulo: "Meshcraft", corpo: "Você tem um aviso novo." },
};

self.addEventListener("push", (evento) => {
  let carta = {};
  try {
    carta = evento.data ? evento.data.json() : {};
  } catch (e) {
    // Conteúdo que não é o nosso JSON: cai no aviso genérico.
    carta = {};
  }
  const texto = AVISOS.textos[carta.assunto] || AVISOS.generico;
  // O toque leva ao mesmo link do cartão da página; sem link, à lista de avisos.
  const parametros = carta.parametros || {};
  const idDaIdeia = String(parametros.suggestion_id || "");
  let caminho = (AVISOS.links || {})[carta.assunto] || AVISOS.caminho;
  if (caminho.includes("{suggestion_id}")) {
    caminho = /^\d+$/.test(idDaIdeia)
      ? caminho.replace("{suggestion_id}", idDaIdeia)
      : AVISOS.caminho;
  }
  evento.waitUntil(
    self.registration.showNotification(texto.titulo, {
      body: texto.corpo,
      icon: "/static/funil/pwa/icone-192.png",
      badge: "/static/funil/pwa/icone-192.png",
      // Uma etiqueta por assunto: o último aviso substitui o anterior.
      tag: carta.assunto || "meshcraft",
      data: { caminho: caminho },
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const destino = (evento.notification.data && evento.notification.data.caminho) || "/";
  evento.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((abas) => {
      // Se o app já está aberto, leva ele ao destino em vez de abrir outra janela.
      for (const aba of abas) {
        if ("focus" in aba && "navigate" in aba) {
          return aba.navigate(destino).then((focada) => (focada || aba).focus());
        }
      }
      return self.clients.openWindow(destino);
    })
  );
});
