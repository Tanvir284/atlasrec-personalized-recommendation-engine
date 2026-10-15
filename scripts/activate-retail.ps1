param([switch]$AlreadyBuilt)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $projectRoot
function Invoke-Docker([string[]]$Arguments) {
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Docker operation failed: '+($Arguments -join ' ')) }
}
$reportPath = Join-Path $projectRoot 'docs\evidence\retail-benchmark.json'
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$datasetId = $report.manifest.dataset_id
if ($report.manifest.synthetic -ne $false -or $report.manifest.profile -ne 'research' -or $datasetId -notmatch '^[a-f0-9]{16}$') { throw 'A verified real dataset report is required' }
$datasetPath = Join-Path $projectRoot ('data\'+$datasetId+'.json')
if (-not (Test-Path -LiteralPath $datasetPath -PathType Leaf)) { throw 'The report dataset file is missing' }
$completed = @($report.runs | Where-Object { $_.status -eq 'completed' })
if ($completed.Count -lt 2) { throw 'Train the real-data baseline and personalized model first' }
foreach ($run in $completed) {
    if ($run.id -notmatch '^[a-z_]+-[a-f0-9]{12}$') { throw 'Invalid model version' }
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ('artifacts\'+$run.id+'\manifest.json')))) { throw 'A trained bundle is missing' }
}
if (-not $AlreadyBuilt) { Invoke-Docker -Arguments @('compose','-p','atlasrec','build','api','worker','web') }
Invoke-Docker -Arguments @('compose','-p','atlasrec','up','-d','--no-build','--wait','--wait-timeout','300','api','web')
Invoke-Docker -Arguments @('compose','-p','atlasrec','cp',$datasetPath,('api:/app/data/'+$datasetId+'.json'))
Invoke-Docker -Arguments @('compose','-p','atlasrec','exec','-T','--user','root','api','chown','atlasrec:atlasrec',('/app/data/'+$datasetId+'.json'))
Invoke-Docker -Arguments @('compose','-p','atlasrec','cp',$reportPath,'api:/app/artifacts/retail-benchmark.json')
foreach ($run in $completed) {
    Invoke-Docker -Arguments @('compose','-p','atlasrec','cp',(Join-Path $projectRoot ('artifacts\'+$run.id)),('api:/app/artifacts/'+$run.id))
}
$installed = & docker compose -p atlasrec exec -T -e ATLASREC_PROFILE=research -e ('RESEARCH_DATASET_ID='+$datasetId) api python scripts/install_retail.py --dataset ('/app/data/'+$datasetId+'.json') --report /app/artifacts/retail-benchmark.json
if ($LASTEXITCODE -ne 0) { throw 'Real catalog installation failed; the existing profile remains configured' }
$result = ($installed -join [Environment]::NewLine) | ConvertFrom-Json
$envPath = Join-Path $projectRoot '.env'
$previous = [IO.File]::ReadAllText($envPath)
$updated = [regex]::Replace($previous,'(?m)^ATLASREC_PROFILE=.*$','ATLASREC_PROFILE=research')
if ($updated -match '(?m)^RESEARCH_DATASET_ID=') {
    $updated = [regex]::Replace($updated,'(?m)^RESEARCH_DATASET_ID=.*$',('RESEARCH_DATASET_ID='+$datasetId))
} else { $updated += [Environment]::NewLine+'RESEARCH_DATASET_ID='+$datasetId+[Environment]::NewLine }
[IO.File]::WriteAllText($envPath,$updated,[Text.UTF8Encoding]::new($false))
try {
    Invoke-Docker -Arguments @('compose','-p','atlasrec','up','-d','--no-build','--wait','--wait-timeout','300','api','worker','web')
} catch {
    [IO.File]::WriteAllText($envPath,$previous,[Text.UTF8Encoding]::new($false))
    Invoke-Docker -Arguments @('compose','-p','atlasrec','up','-d','--no-build','--wait','--wait-timeout','300','api','worker','web')
    throw
}
$result | Add-Member -NotePropertyName installed_at -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
[IO.File]::WriteAllText((Join-Path $projectRoot 'docs\evidence\retail-install.json'),($result|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
$result | ConvertTo-Json -Depth 10
