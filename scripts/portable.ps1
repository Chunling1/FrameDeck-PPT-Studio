$ErrorActionPreference = 'Stop'
$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$out = Join-Path $src ('release\PPT-GPT-Studio-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$rt = Join-Path $out 'runtime'
New-Item -ItemType Directory -Path $rt -Force | Out-Null
$zip = Join-Path $out 'python-runtime.zip'
$version = '3.12.10'
Invoke-WebRequest "https://www.python.org/ftp/python/$version/python-$version-embed-amd64.zip" -OutFile $zip -UseBasicParsing
Expand-Archive -LiteralPath $zip -DestinationPath $rt
$signature = Get-AuthenticodeSignature -LiteralPath (Join-Path $rt 'python.exe')
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Python runtime signature verification failed' }
Remove-Item -LiteralPath $zip
$site = Join-Path $rt 'Lib\site-packages'
python -m pip install --disable-pip-version-check --only-binary=:all: --platform win_amd64 --implementation cp --python-version 3.12 --abi cp312 --target $site -r (Join-Path $src 'requirements.txt') --index-url https://pypi.org/simple
if ($LASTEXITCODE) { throw 'Dependency installation failed' }
@('python312.zip','.','..','Lib\site-packages','import site') | Set-Content -Encoding ascii -LiteralPath (Join-Path $rt 'python312._pth')
foreach ($name in @('studio.py','app.py','providers.py','tasks.py','approvals.py','agent_backend.py','gateway.py','art_direction.py','engine.py','models.py','render.py','rebuild.py','launch.cmd','LICENSE','README.md','requirements.txt','static','skill')) {
    Copy-Item -LiteralPath (Join-Path $src $name) -Destination $out -Recurse
}
$docs = New-Item -ItemType Directory -Path (Join-Path $out 'docs')
foreach ($name in @('guide.md','workspace.png')) {
    Copy-Item -LiteralPath (Join-Path $src "docs\$name") -Destination $docs.FullName
}
& (Join-Path $rt 'python.exe') -c "import app,pypdf,openpyxl; print('portable runtime OK')"
if ($LASTEXITCODE) {throw 'Portable runtime smoke test failed'}
Write-Output $out
