# Opens the built Windows app the way a customer would and lets it drive its
# own page (cmd/vpncheck-app/smoke.go): passes when the window loaded the
# page and a button's request reached the app. Takes a screenshot meanwhile.
#
#   pwsh packaging/smoke-windows.ps1 -Exe dist/KairaVPN-Check-x64.exe -Shot shot.png
param([Parameter(Mandatory)] [string] $Exe, [Parameter(Mandatory)] [string] $Shot)

$marker = Join-Path ([System.IO.Path]::GetTempPath()) ("vpncheck-smoke-" + [guid]::NewGuid())
$env:VPNCHECK_SMOKE = $marker
$env:VPNCHECK_SMOKE_HOLD = "8s"
$app = Start-Process -FilePath (Resolve-Path $Exe) -PassThru
# Without a handle taken now, ExitCode reads empty after the process ends.
$null = $app.Handle
for ($i = 0; $i -lt 120 -and -not (Test-Path $marker) -and -not $app.HasExited; $i++) { Start-Sleep -Seconds 1 }

try {
    Add-Type -AssemblyName System.Windows.Forms, System.Drawing
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    [System.Drawing.Graphics]::FromImage($bitmap).CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
    $bitmap.Save($Shot)
} catch {
    Write-Host "no screenshot: $_"
}

if (-not $app.WaitForExit(60000)) { $app.Kill(); Write-Host "the app did not close"; exit 1 }
$verdict = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { "none" }
Write-Host "exit $($app.ExitCode), verdict: $verdict"
if ($app.ExitCode -ne 0 -or $verdict -ne "ok") { exit 1 }
