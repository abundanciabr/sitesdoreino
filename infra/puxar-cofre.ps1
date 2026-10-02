# Traz para este PC as cópias de segurança da VPS: o cofre fora da VPS.
#
# Copia só o que é novo ou mudou e NUNCA apaga nada aqui. Não traz env/ nem .env (senhas).
# Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File puxar-cofre.ps1
# A tarefa agendada "Cofre sitesdoreino" roda uma cópia deste arquivo que fica no próprio cofre.
# Guia: infra/COMO-RESTAURAR.md.
param(
  [string]$Cofre = "$env:USERPROFILE\Cofre-sitesdoreino",
  [string]$Vps = "sitesdoreino-vps"
)
$ErrorActionPreference = "Stop"
# Uma copia por vez: a de logon e a diaria podem se encontrar.
$umaPorVez = New-Object System.Threading.Mutex($false, "Local\CofreSitesdoreino")
if (-not $umaPorVez.WaitOne(0)) { Write-Output "Outra copia ja esta rodando."; exit 0 }
$ssh = "$env:WINDIR\System32\OpenSSH\ssh.exe"
$tar = "$env:WINDIR\System32\tar.exe"
$utf8 = New-Object System.Text.UTF8Encoding $false
$relatorio = @("Ultima copia: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (hora deste PC)", "")
$tudoIgual = $true

# Pastas que mudam: traz arquivo novo ou de tamanho diferente.
foreach ($pasta in @("backups-de-banco", "admin-midia", "backups-coordenacao")) {
  $local = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $local | Out-Null
  $remota = & $ssh -o BatchMode=yes $Vps "cd /opt/plataforma/$pasta 2>/dev/null && find . -type f ! -name '*.parcial' -printf '%P\t%s\n'"
  if ($LASTEXITCODE -ne 0) { throw "a VPS nao respondeu ao listar $pasta" }
  $faltam = @()
  $bytes = [int64]0
  foreach ($linha in @($remota)) {
    if (-not $linha) { continue }
    $rel, $tamanho = $linha -split "`t"
    $bytes += [int64]$tamanho
    $arquivo = Join-Path $local ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $arquivo) -or (Get-Item -LiteralPath $arquivo).Length -ne [int64]$tamanho) {
      $faltam += $rel
    }
  }
  if ($faltam.Count -gt 0) {
    $lista = Join-Path $env:TEMP "cofre-$pasta.txt"
    [System.IO.File]::WriteAllText($lista, ($faltam -join "`n") + "`n", $utf8)
    cmd /c "$ssh -o BatchMode=yes $Vps tar cf - -C /opt/plataforma/$pasta -T - < $lista | $tar xf - -C $local"
    if ($LASTEXITCODE -ne 0) { throw "a copia de $pasta falhou no meio; rode de novo" }
    Remove-Item $lista
  }
  # Conferencia: todo arquivo da VPS existe aqui com o mesmo tamanho.
  $iguais = 0
  foreach ($linha in @($remota)) {
    if (-not $linha) { continue }
    $rel, $tamanho = $linha -split "`t"
    $arquivo = Join-Path $local ($rel -replace '/', '\')
    if ((Test-Path -LiteralPath $arquivo) -and (Get-Item -LiteralPath $arquivo).Length -eq [int64]$tamanho) { $iguais++ }
  }
  $total = @($remota | Where-Object { $_ }).Count
  if ($iguais -ne $total) { $tudoIgual = $false }
  $relatorio += "{0}: VPS {1} arquivos / {2:N0} bytes; aqui {3} iguais; trazidos agora {4}" -f $pasta, $total, $bytes, $iguais, $faltam.Count
}

# admin-dados e admin-dados.new: fotos da fila antiga, que nao mudam mais. Vem uma vez, compactada.
foreach ($pasta in @("admin-dados", "admin-dados.new")) {
  $dados = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $dados | Out-Null
  $pacote = Join-Path $dados "$pasta.tar.gz"
  if (-not (Test-Path $pacote)) {
    cmd /c "$ssh -o BatchMode=yes $Vps nice -n 19 tar czf - -C /opt/plataforma $pasta > $pacote.parcial"
    if ($LASTEXITCODE -ne 0) { Remove-Item -ErrorAction SilentlyContinue "$pacote.parcial"; throw "a copia de $pasta falhou" }
    Move-Item "$pacote.parcial" $pacote
  }
  $relatorio += "{0}: pacote unico de {1:N0} bytes" -f $pasta, (Get-Item $pacote).Length
}

# O guia mais novo, da main que a VPS recebeu.
$guia = Join-Path $Cofre "COMO-RESTAURAR.md"
cmd /c "$ssh -o BatchMode=yes $Vps cat /opt/plataforma/codigo/ferramentas/atual/infra/COMO-RESTAURAR.md > $guia.parcial"
if ($LASTEXITCODE -eq 0 -and (Get-Item "$guia.parcial").Length -gt 0) { Move-Item -Force "$guia.parcial" $guia }
else { Remove-Item -ErrorAction SilentlyContinue "$guia.parcial" }

# O backup mais novo e as contagens dele.
$ultimo = Get-ChildItem (Join-Path $Cofre "backups-de-banco") -Filter "*.contagens.tsv" |
  Sort-Object Name | Select-Object -Last 1
if ($ultimo) {
  $linhas = Get-Content $ultimo.FullName | ForEach-Object { [int64](($_ -split "`t")[2]) } | Measure-Object -Sum
  $relatorio += ""
  $relatorio += "Backup mais novo: {0} ({1} tabelas, {2:N0} linhas no total)" -f ($ultimo.Name -replace '\.contagens\.tsv$', ''), $linhas.Count, $linhas.Sum
}
$relatorio += ""
$relatorio += $(if ($tudoIgual) { "Os dois lados tem os mesmos arquivos com os mesmos tamanhos." } else { "ATENCAO: algum arquivo da VPS nao bateu; rode de novo." })
[System.IO.File]::WriteAllLines((Join-Path $Cofre "ultima-copia.txt"), $relatorio, $utf8)
$relatorio | ForEach-Object { Write-Output $_ }
if (-not $tudoIgual) { exit 1 }
