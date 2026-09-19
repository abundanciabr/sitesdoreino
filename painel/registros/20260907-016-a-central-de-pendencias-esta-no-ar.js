(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-016-a-central-de-pendencias-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "A Central de Pendencias esta no ar: abra meshcraft.top/admin/pendencias/",
  detalhe: "O veredito do deploy que faltava. A tela ja esta publicada e voce pode abrir agora.\n\nO PRIMEIRO DEPLOY REPROVOU, e nao foi defeito do codigo: a porta 22 da VPS recusou a conexao tres vezes (o soluco de rede da armadilhas/127). O deploy seguinte, que carrega o mesmo codigo, passou em 31s com 'deploy (admin): success'.\n\nNADA DEPENDE DE VOCE. So abra a tela quando quiser.",
  autoridade: "sessao",
  evidencia: "gh run view 34076923248 --json status,conclusion,jobs: completed/success, com detectar/portao-de-deploy/deploy (admin) todos success. O run reprovado foi o 34076549573 (completed/failure, 8min28s, no passo 'Medir a porta 22 depois da 2a recusa'); conferido por git merge-base que o merge 0e90b459 do PR 1270 e ancestral do 9f180e0a que o run verde publicou. De fora, na internet publica: /admin/healthz 200, /admin/pendencias/ 302 para /entrar/google?next=/admin/pendencias/.",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: "20260907-014-a-central-de-pendencias-no-ar",
  gravidade: "verde",
  frente: "fabrica"
});})();
