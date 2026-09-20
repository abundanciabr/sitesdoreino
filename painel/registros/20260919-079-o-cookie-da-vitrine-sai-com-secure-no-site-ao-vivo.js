(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260919-079-o-cookie-da-vitrine-sai-com-secure-no-site-ao-vivo",
  tipo: "medicao",
  quando: "2026-09-19",
  titulo: "O cookie da vitrine sai com Secure no site ao vivo",
  detalhe: "Os dois recibos da entrega dizem integracao e publicacao nao verificadas. Agora estao, e medidas.\n\nO deploy-celula do commit de merge terminou success em 3min52s. Depois dele, uma requisicao a https://meshcraft.top/ devolve Set-Cookie meshcraft_visitante com HttpOnly, SameSite=Lax e Secure. Esse cookie e gravado com request.is_secure(), entao o Secure na resposta prova que is_secure() responde True em producao atras do Traefik: e a causa que a entrega consertou, medida de fora. O cookie de ver_como le a mesma chamada. A borda http devolve 301 antes de gravar cookie nenhum.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1779, integrado por abundanciabr no commit 7a3d31eecf2fb0270c18bab8411e1c2890c36ba7, conferido por gh pr view --json state,mergedBy,mergeCommit. Publicacao: deploy-celula run 35470240171 completed/success. Prova de fora: curl -sS -D - https://meshcraft.top/.",
  verificado_em: "2026-09-19",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  area: "funil",
  vence_em_dias: null,
  porque_so_voce: null,
  proximo_passo: null
}); })();
