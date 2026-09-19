# Referência Git inexistente parece igualdade

`git diff` contra uma referência inexistente pode devolver vazio e parecer
igualdade. Antes de concluir que algo já está na `main`, confirme que a
referência resolve com `git rev-parse` e compare o ramo real, não
`origin/pulls/N`.
