$ErrorActionPreference = "Stop"

$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $repoDir ".local-run"

foreach ($name in @("backend", "frontend")) {
    $pidFile = Join-Path $runDir "$name.pid"
    $processNameFile = Join-Path $runDir "$name.process-name"
    $startedFile = Join-Path $runDir "$name.started"
    if (-not (Test-Path -LiteralPath $pidFile)) {
        continue
    }

    $processId = [int](Get-Content -Raw -LiteralPath $pidFile)
    $expectedProcessName = if (Test-Path -LiteralPath $processNameFile) {
        (Get-Content -Raw -LiteralPath $processNameFile).Trim()
    } else { "" }
    $expectedStartTicks = if (Test-Path -LiteralPath $startedFile) {
        [long](Get-Content -Raw -LiteralPath $startedFile)
    } else { 0 }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue

    if (
        $process -and
        $process.ProcessName -eq $expectedProcessName -and
        $process.StartTime.ToUniversalTime().Ticks -eq $expectedStartTicks
    ) {
        Stop-Process -Id $processId
        Write-Host "Stopped $name (PID $processId)."
    }

    Remove-Item -LiteralPath $pidFile -Force
    Remove-Item -LiteralPath $processNameFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $startedFile -Force -ErrorAction SilentlyContinue
}
