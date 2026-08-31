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

// ---------------------------------------------------------------------------
// O AVISO na tela do aparelho (Fase 7, 31/08/2026)
// ---------------------------------------------------------------------------
// O que chega no `push` é DADO, nunca frase pronta (`DECISAO-notificacoes`
// §5.1): assunto e parâmetros. A frase nasce aqui, com os textos que a view de
// `/sw.js` injetou no idioma de quem instalou — é literalmente "a frase nasce
// na leitura", agora no aparelho da pessoa.
//
// `self.AVISOS_DO_SITE` é posto por essa view ANTES deste arquivo. O valor
// abaixo é só a rede de segurança para o dia em que este arquivo for servido
// cru: sem ele, um `undefined` faria o aviso não aparecer, e o navegador
// mostraria no lugar dele a mensagem genérica dele ("Este site foi atualizado
// em segundo plano"), que é pior que qualquer texto nosso.
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
    // Conteúdo que não é o nosso JSON. Não é motivo para ficar calado: o
    // aviso genérico ainda leva a pessoa à página certa.
    carta = {};
  }
  const texto = AVISOS.textos[carta.assunto] || AVISOS.generico;
  evento.waitUntil(
    self.registration.showNotification(texto.titulo, {
      body: texto.corpo,
      icon: "/static/funil/pwa/icone-192.png",
      badge: "/static/funil/pwa/icone-192.png",
      // Um aviso por assunto na tela: sem esta etiqueta, dez novidades viram
      // dez cartazes empilhados no celular de quem só queria saber que tem
      // coisa nova. O último substitui o anterior.
      tag: carta.assunto || "meshcraft",
      data: { caminho: AVISOS.caminho },
    })
  );
});

self.addEventListener("notificationclick", (evento) => {
  evento.notification.close();
  const destino = (evento.notification.data && evento.notification.data.caminho) || "/";
  evento.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((abas) => {
      // Se o app já está aberto, leva ELE ao destino em vez de abrir uma
      // segunda janela: duas cópias do mesmo app abertas é o jeito mais rápido
      // de a pessoa achar que o aviso quebrou alguma coisa.
      for (const aba of abas) {
        if ("focus" in aba && "navigate" in aba) {
          return aba.navigate(destino).then((focada) => (focada || aba).focus());
        }
      }
      return self.clients.openWindow(destino);
    })
  );
});
