param(
    [Parameter(Mandatory = $true)]
    [string]$Node,
    [Parameter(Mandatory = $true)]
    [string]$RemoteRunDir,
    [Parameter(Mandatory = $true)]
    [string]$LocalRunDir,
    [string]$DoneMarker = "results.csv",
    [int]$PollSeconds = 60,
    [int]$MaxWaitMinutes = 720
)

$ErrorActionPreference = "Stop"

function Test-RemoteMarker {
    param(
        [string]$NodeName,
        [string]$RemoteDir,
        [string]$Marker
    )
    $cmd = "bash -lc 'test -f ""$RemoteDir/$Marker"" && echo READY || echo WAIT'"
    $output = ssh -o BatchMode=yes $NodeName $cmd
    return ($output.Trim() -eq "READY")
}

function Fetch-RemoteDir {
    param(
        [string]$NodeName,
        [string]$RemoteDir,
        [string]$LocalDir
    )
    New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
    scp -r "${NodeName}:${RemoteDir}/." $LocalDir
}

$deadline = (Get-Date).AddMinutes($MaxWaitMinutes)
while ((Get-Date) -lt $deadline) {
    if (Test-RemoteMarker -NodeName $Node -RemoteDir $RemoteRunDir -Marker $DoneMarker) {
        Fetch-RemoteDir -NodeName $Node -RemoteDir $RemoteRunDir -LocalDir $LocalRunDir
        Write-Host "FETCHED $RemoteRunDir -> $LocalRunDir"
        exit 0
    }
    Start-Sleep -Seconds $PollSeconds
}

Write-Error "Timed out waiting for $DoneMarker under $RemoteRunDir on $Node."
exit 1
