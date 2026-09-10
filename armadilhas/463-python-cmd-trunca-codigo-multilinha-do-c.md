---
schema_version: 2
armadilha: 463
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o comportamento vem do wrapper do runtime local; a proteção aplicável é conferir a saída esperada do comando que inicia o instrumento
sinal:
  - `python -u -c $codigoMultilinha`
  - exit 0 com saída ausente ou incompleta
---

# `python.cmd` trunca código multilinha de `-c` e devolve exit 0

**Sintoma.** No PowerShell do runtime local, `python` pode resolver para um
wrapper `python.cmd`. Um preview foi iniciado com código multilinha passado a
`-c`; o comando terminou com exit 0 sem iniciar o servidor. Numa reprodução
menor, o wrapper executou só a primeira de duas chamadas a `print` e ainda
devolveu 0. A mesma string executada pelo `python.exe` real imprimiu as duas
linhas.

**Causa.** O código multilinha não atravessa intacto a camada do wrapper
`.cmd`. O exit 0 certifica apenas que o wrapper terminou, não que o programa
inteiro foi entregue ao interpretador nem que o serviço esperado iniciou.

**Solução.** Para script multilinha, grave um arquivo `.py` e execute o arquivo,
ou descubra o interpretador real com o `-c` simples `import sys;
print(sys.executable)` e invoque esse executável diretamente. Sempre confira a
saída ou a sonda que prova o efeito esperado. Exit 0 sem essa prova é
falso-verde.

**Prova observada.** `python -u -c $codigoMultilinha` devolveu
`wrapper_exit=0` e somente `MAPA-LINHA-1`; a chamada direta ao executável
devolveu `real_exit=0` e `MAPA-LINHA-1|MAPA-LINHA-2`.
