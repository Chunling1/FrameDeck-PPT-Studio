param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
$src=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (Test-Path -LiteralPath $Destination) {throw 'Refusing to overwrite an existing directory'}
$approved=@('.gitignore','LICENSE','README.md','requirements.txt','package.json','package-lock.json','ui.tsx','PromptReview.tsx','launch.cmd','studio.py','app.py','models.py','providers.py','tasks.py','approvals.py','agent_backend.py','gateway.py','art_direction.py','engine.py','render.py','visual_anchors.py','rebuild.py','static','scripts','skill','tests','docs\guide.md','docs\workspace.png')
$files=@(foreach($name in $approved){
    $p=Get-Item -LiteralPath (Join-Path $src $name)
    if ($p.PSIsContainer) {Get-ChildItem -LiteralPath $p.FullName -Recurse -File | Where-Object {$_.FullName -notmatch '__pycache__' -and $_.Extension -ne '.pyc'}} else {$p}
})
foreach ($f in $files){
    if ($f.Name -match '^\.env|^config\.json$|\.(db|pem|key|pt|pth)$' -or $f.FullName -match 'dmit_ssh|label_tool[\\/]samples\.json') {throw "Blocked sensitive file: $($f.Name)"}
    if ($f.Extension -ne '.png' -and (Select-String -LiteralPath $f.FullName -Quiet -Pattern 'sk-[A-Za-z0-9_-]{24,}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[0-9A-Za-z]{28,}|-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----')) {throw "Possible credential: $($f.Name)"}
}
New-Item -ItemType Directory -Path $Destination | Out-Null
foreach($f in $files){
    $relative=$f.FullName.Substring($src.Length+1)
    $dest=Join-Path $Destination $relative
    New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
    Copy-Item -LiteralPath $f.FullName -Destination $dest
    if ((Get-FileHash -LiteralPath $dest).Hash -ne (Get-FileHash -LiteralPath $f.FullName).Hash){throw "Copy mismatch: $relative"}
}
Write-Output "Verified $($files.Count) source files: $Destination"
