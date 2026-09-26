# Execução automática no Windows

## Sintoma

O robô devolve comandos para serem colados no PowerShell ou falha ao abrir a
sessão com mensagens como `python não é reconhecido` e `py não é reconhecido`.

## Causa

O projeto chama `python`, mas o Windows desta máquina não possui esse nome no
`PATH`. O Codex já fornece um Python compatível em um caminho próprio, porém
esse runtime só era usado por um hook específico. Os demais hooks, o Makefile
e os portões procuravam um executável que não existia.

## Solução definitiva

O projeto possui um único launcher:

```text
ci/python.cmd
```

Ele procura nesta ordem:

1. Python 3.11 ou superior empacotado pelo Codex.
2. `python.exe` ou `python3.exe` disponível no `PATH`.
3. Uma mensagem de parada com a causa e a ação necessária.

Hooks do Claude usam esse launcher. O Makefile também escolhe o runtime do
Codex antes de procurar Python no sistema.

## Diagnóstico rápido

Na raiz da bancada, execute apenas este teste:

```powershell
.\ci\python.cmd -c "import sys; print(sys.executable); print(sys.version)"
```

Resultado esperado: o caminho contém
`codex-runtimes\codex-primary-runtime\dependencies\python\python.exe` e a
versão exibida é 3.11 ou superior.

Se aparecer `Python 3.11+ indisponivel`, o runtime do Codex não está instalado
ou o caminho foi removido. Nesse caso, o problema é do ambiente do agente, não
do código da tarefa. O agente deve restaurar o runtime ou usar uma máquina que
o forneça. O mantenedor não precisa instalar Python nem montar comandos.

## Regra para novas automações

No Windows, scripts do projeto devem ser chamados pelo launcher:

```text
ci/python.cmd ci/arquivo.py
```

Código Python que chama outro Python deve usar `sys.executable`, nunca o texto
fixo `python`. Assim o processo filho mantém o mesmo runtime que iniciou a
tarefa.

## Verificação

O launcher precisa ser validado antes de declarar a sessão pronta:

```powershell
.\ci\python.cmd -c "import sys; assert sys.version_info >= (3, 11); print('runtime Python válido')"
```

Se esse comando passar, a ausência de `python` no `PATH` não impede a execução
do projeto.
