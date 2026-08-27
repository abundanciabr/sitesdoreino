(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-001-a-vps-recusou-o-robo-de-novo-e-resolveu-sozinho",
  tipo: "incidente",
  quando: "2026-08-27",
  titulo: "O deploy do PR 264 falhou na conexão com o servidor — repeti e subiu normal, site no ar o tempo todo",
  detalhe: "Mesma falha já vista nos registros 030 e 042: a conexão do robô da nuvem com o servidor expirou bem na hora de enviar a versão nova. O PR 264 só tinha acréscimo de registros no livro (nenhum código mudou), mas toda mudança em painel/ dispara um deploy da célula admin — e foi esse deploy que caiu.\n\nRepeti a etapa que falhou, sem mergear nada de novo, e desta vez completou normal. Conferi de fora, antes e depois: tanto o site público quanto a área administrativa responderam 200 o tempo todo — a versão nova simplesmente não tinha subido ainda; nada saiu do ar.\n\nEsbarrei nisto enquanto investigava um aviso de painel quebrado que você colou no chat (registro 20260827-002) — os dois assuntos são independentes, mas encontrei um enquanto procurava o outro.",
  autoridade: "github",
  evidencia: "run 33034032429 (PR #264) — 'deploy (admin)' falhou com 'dial tcp ***:22: i/o timeout'; repetido com gh run rerun 33034032429 --failed, concluiu completed/success com 'painel embutido: 60 registros' no log (batendo com manifesto.js); https://meshcraft.top/ e https://meshcraft.top/admin/healthz responderam 200 durante e depois da falha",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
