// =============================================================================
// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.
// Para regenerar: node painel/gerar_manifesto.js
// A página confere REGISTROS.length === MANIFESTO.length ao abrir: registro
// que não carregar é detectado, nunca ignorado (fail-closed).
// =============================================================================
var MANIFESTO = [
  "20260819-001-h3-trava-de-merge-nativa",
  "20260819-002-h4-docker-junto-com-windows",
  "20260821-001-h7-rito-de-contrato-do-502",
  "20260822-001-h8-cartao-de-teste-no-cofre",
  "20260822-002-frente-vender-pausada",
  "20260823-001-h15-porta-lateral-do-servidor",
  "20260823-002-retrotraducao-chave-paga",
  "20260825-001-frente-site-no-ar",
  "20260825-002-frente-comunidade-caixa-no-ar",
  "20260825-003-frente-curso-e-sua",
  "20260825-004-frente-fabrica-onda1-auditada",
  "20260825-005-decisao-sininho-3-respostas",
  "20260826-001-reforma-dos-paineis-aprovada",
  "20260826-002-nota-fila-dos-robos",
  "20260826-003-nota-o-que-a-obra-deixou-de-fora",
  "20260826-004-obra-da-reforma-concluida",
  "20260826-005-auditoria-achou-documentos-com-o-mapa-velho",
  "20260826-006-auditoria-da-obra-veredito",
  "20260826-007-evidencias-que-apontavam-para-a-lapide",
  "20260826-008-auditoria-de-fora-quatro-consertos",
  "20260826-009-decisao-a-vista-meu-mapa-nao-foi-construida",
  "20260826-010-rumo-fabrica-tres-pecas",
  "20260826-011-rumo-site-fuso-horario",
  "20260826-012-rumo-comunidade-sininho-e-apresentacao",
  "20260826-013-rumo-curso-o-capitulo-do-dono",
  "20260826-014-rumo-vender-comeca-do-meio",
  "20260826-015-resposta-pode-construir-o-meu-mapa"
];
if (typeof document !== "undefined") {
  MANIFESTO.forEach(function (n) {
    document.write('<script src="registros/' + n + '.js"><\/script>');
  });
}
