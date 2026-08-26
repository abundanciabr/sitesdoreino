// =============================================================================
// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.
// Para regenerar: node painel/gerar_manifesto.js
// A página confere REGISTROS.length === MANIFESTO.length ao abrir: registro
// que não carregar é detectado, nunca ignorado (fail-closed).
// =============================================================================
var MANIFESTO = [
  "20260823-001-h15-porta-lateral-do-servidor",
  "20260826-001-reforma-dos-paineis-aprovada"
];
if (typeof document !== "undefined") {
  MANIFESTO.forEach(function (n) {
    document.write('<script src="registros/' + n + '.js"><\/script>');
  });
}
