<#.SYNOPSIS
    Recursively extract .bz2 files to one folder (parallel, no Python).

.DESCRIPTION
    When **7-Zip** is installed, uses ``7z.exe`` first (best for plain ``.bz2`` / bzip2 streams).
    If that fails or 7-Zip is missing, falls back to Windows ``tar.exe`` (``.tar.bz2`` and other tar layouts).

    By default removes each archive after a successful extract. Use -KeepSourceArchive to keep files.

.PARAMETER ThrottleLimit
    Max concurrent jobs. 0 = auto: min(32, max(1, [int](ceil(cores * 1.5)))).

.PARAMETER ProgressInterval
    Progress line every N completions. Default 200.

.PARAMETER KeepSourceArchive
    Do not delete the .bz2 after a successful extract.
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $SourceRoot,

    [Parameter(Mandatory = $true)]
    [string] $DestRoot,

    [Parameter(Mandatory = $false)]
    [int] $ThrottleLimit = 0,

    [Parameter(Mandatory = $false)]
    [int] $ProgressInterval = 200,

    [Parameter(Mandatory = $false)]
    [switch] $KeepSourceArchive
)

$ErrorActionPreference = 'Continue'

function Resolve-7ZipExe {
    foreach ($p in @(
            (Join-Path ${env:ProgramFiles} '7-Zip\7z.exe'),
            (Join-Path ${env:ProgramFiles(x86)} '7-Zip\7z.exe')
        )) {
        if ($p -and (Test-Path -LiteralPath $p)) {
            return $p
        }
    }
    $cmd = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    return $null
}

# Tar fallback after 7-Zip: plain .bz2 is not tar, so discard tar stdout/stderr (exit code still checked).
function Invoke-TarExtract {
    param(
        [string] $ArchivePath,
        [string] $DestDir,
        [string] $TarExe = 'tar.exe'
    )
    $nullSink = '\\.\NUL'
    $p = Start-Process -FilePath $TarExe -ArgumentList @('-xf', $ArchivePath, '-C', $DestDir) -Wait -NoNewWindow -PassThru -RedirectStandardOutput $nullSink -RedirectStandardError $nullSink
    return $p.ExitCode
}

function Invoke-7zExtract {
    param([string] $SevenZ, [string] $ArchivePath, [string] $DestDir)
    $p = Start-Process -FilePath $SevenZ -ArgumentList @(
        'x', $ArchivePath, "-o$DestDir", '-y', '-bd', '-mmt=on',
        '-bso0', '-bse0', '-bsp0'
    ) -Wait -NoNewWindow -PassThru
    return $p.ExitCode
}

$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$DestRoot = $DestRoot.TrimEnd('\', '/')

if (-not (Test-Path -LiteralPath $DestRoot)) {
    New-Item -ItemType Directory -Path $DestRoot | Out-Null
}
$DestRootResolved = (Resolve-Path -LiteralPath $DestRoot).Path

$archives = @(Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Filter *.bz2 -ErrorAction SilentlyContinue)
if ($archives.Count -eq 0) {
    Write-Host "No .bz2 files found under: $SourceRoot"
    exit 0
}

$total = $archives.Count
if ($ProgressInterval -lt 1) {
    $ProgressInterval = 200
}

$sevenZ = Resolve-7ZipExe
$deleteSources = -not $KeepSourceArchive.IsPresent
if ($deleteSources) {
    Write-Host "Found $total .bz2 file(s) -> $DestRootResolved (7z then tar if needed; success removes source)."
}
else {
    Write-Host "Found $total .bz2 file(s) -> $DestRootResolved (-KeepSourceArchive: sources kept)."
}
if (-not $sevenZ) {
    Write-Host "Note: 7-Zip (7z.exe) not found. Using tar only; plain .bz2 may fail (install 7-Zip for those)."
}

$cpu = [Environment]::ProcessorCount
if ($ThrottleLimit -lt 1) {
    $ThrottleLimit = [Math]::Min(32, [Math]::Max(1, [int][Math]::Ceiling($cpu * 1.5)))
}
$throttle = [Math]::Min($ThrottleLimit, $archives.Count)

$tarExe = (Get-Command tar.exe -ErrorAction SilentlyContinue).Source
if (-not $tarExe) {
    $tarExe = 'tar.exe'
}

$progressState = [hashtable]::Synchronized(@{
    Done     = 0
    Total    = $total
    Interval = $ProgressInterval
    Failed   = 0
})

function Update-ExtractProgress {
    param([hashtable] $State)
    [void][System.Threading.Monitor]::Enter($State.SyncRoot)
    try {
        $State.Done = [int]$State.Done + 1
        $d = [int]$State.Done
        $t = [int]$State.Total
        $i = [int]$State.Interval
    }
    finally {
        [System.Threading.Monitor]::Exit($State.SyncRoot)
    }
    if ($t -le 0) { return }
    if ($d -eq $t) {
        Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
    }
    elseif ($i -gt 0 -and ($d % $i) -eq 0) {
        Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
    }
}

function Invoke-OneExtract {
    param(
        [string] $ArchivePath,
        [string] $OutDir,
        [string] $SevenZPath,
        [bool] $DoDelete,
        [hashtable] $Progress
    )
    try {
        $code = 1
        if ($SevenZPath) {
            $code = Invoke-7zExtract -SevenZ $SevenZPath -ArchivePath $ArchivePath -DestDir $OutDir
        }
        if ($code -ne 0) {
            $code = Invoke-TarExtract -ArchivePath $ArchivePath -DestDir $OutDir -TarExe $tarExe
        }
        if ($code -ne 0) {
            [void][System.Threading.Monitor]::Enter($Progress.SyncRoot)
            try {
                $Progress.Failed = [int]$Progress.Failed + 1
            }
            finally {
                [System.Threading.Monitor]::Exit($Progress.SyncRoot)
            }
            Write-Warning "Failed: $ArchivePath (exit $code). For plain .bz2 install 7-Zip."
        }
        elseif ($DoDelete) {
            try {
                Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction Stop
            }
            catch {
                [void][System.Threading.Monitor]::Enter($Progress.SyncRoot)
                try {
                    $Progress.Failed = [int]$Progress.Failed + 1
                }
                finally {
                    [System.Threading.Monitor]::Exit($Progress.SyncRoot)
                }
                Write-Warning "Extracted OK but could not delete: $ArchivePath - $($_.Exception.Message)"
            }
        }
    }
    finally {
        Update-ExtractProgress -State $Progress
    }
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()

if ($throttle -le 1 -or $archives.Count -eq 1) {
    foreach ($f in $archives) {
        Invoke-OneExtract -ArchivePath $f.FullName -OutDir $DestRootResolved -SevenZPath $sevenZ -DoDelete $deleteSources -Progress $progressState
    }
}
elseif ($PSVersionTable.PSVersion.Major -ge 7) {
    Write-Host "Parallel extract: $total file(s), throttle=$throttle (PowerShell 7+)"
    $archives | ForEach-Object -ThrottleLimit $throttle -Parallel {
        $archive = $_
        $dest = $using:DestRootResolved
        $sz = $using:sevenZ
        $del = $using:deleteSources
        $prog = $using:progressState
        $tx = $using:tarExe
        try {
            function Invoke-7zExtract {
                param([string] $SevenZ, [string] $ArchivePath, [string] $DestDir)
                $p = Start-Process -FilePath $SevenZ -ArgumentList @(
                    'x', $ArchivePath, "-o$DestDir", '-y', '-bd', '-mmt=on',
                    '-bso0', '-bse0', '-bsp0'
                ) -Wait -NoNewWindow -PassThru
                return $p.ExitCode
            }

            $code = 1
            if ($sz) {
                $code = Invoke-7zExtract -SevenZ $sz -ArchivePath $archive.FullName -DestDir $dest
            }
            if ($code -ne 0) {
                $sink = '\\.\NUL'
                $p0 = Start-Process -FilePath $tx -ArgumentList @('-xf', $archive.FullName, '-C', $dest) -Wait -NoNewWindow -PassThru -RedirectStandardOutput $sink -RedirectStandardError $sink
                $code = $p0.ExitCode
            }
            if ($code -ne 0) {
                [void][System.Threading.Monitor]::Enter($prog.SyncRoot)
                try {
                    $prog.Failed = [int]$prog.Failed + 1
                }
                finally {
                    [System.Threading.Monitor]::Exit($prog.SyncRoot)
                }
                Write-Warning "Failed: $($archive.FullName)"
            }
            elseif ($del) {
                try {
                    Remove-Item -LiteralPath $archive.FullName -Force -ErrorAction Stop
                }
                catch {
                    [void][System.Threading.Monitor]::Enter($prog.SyncRoot)
                    try {
                        $prog.Failed = [int]$prog.Failed + 1
                    }
                    finally {
                        [System.Threading.Monitor]::Exit($prog.SyncRoot)
                    }
                    Write-Warning "Could not delete: $($archive.FullName)"
                }
            }
        }
        finally {
            [void][System.Threading.Monitor]::Enter($prog.SyncRoot)
            try {
                $prog.Done = [int]$prog.Done + 1
                $d = [int]$prog.Done
                $t = [int]$prog.Total
                $iv = [int]$prog.Interval
            }
            finally {
                [System.Threading.Monitor]::Exit($prog.SyncRoot)
            }
            if ($t -gt 0) {
                if ($d -eq $t) {
                    Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
                }
                elseif ($iv -gt 0 -and ($d % $iv) -eq 0) {
                    Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
                }
            }
        }
    }
}
else {
    Write-Host "Parallel extract: $total file(s), throttle=$throttle (runspace pool)"
    $pool = [runspacefactory]::CreateRunspacePool(1, $throttle)
    $pool.Open()
    $powershells = @()
    foreach ($f in $archives) {
        $ps = [powershell]::Create()
        $ps.RunspacePool = $pool
        [void]$ps.AddScript({
                param($ArchivePath, $OutDir, $SevenZPath, $DoDelete, $Prog, $TarExePath)
                $code = 1
                if ($SevenZPath) {
                    $p7 = Start-Process -FilePath $SevenZPath -ArgumentList @(
                        'x', $ArchivePath, "-o$OutDir", '-y', '-bd', '-mmt=on',
                        '-bso0', '-bse0', '-bsp0'
                    ) -Wait -NoNewWindow -PassThru
                    $code = $p7.ExitCode
                }
                if ($code -ne 0) {
                    $sink = '\\.\NUL'
                    $p = Start-Process -FilePath $TarExePath -ArgumentList @('-xf', $ArchivePath, '-C', $OutDir) -Wait -NoNewWindow -PassThru -RedirectStandardOutput $sink -RedirectStandardError $sink
                    $code = $p.ExitCode
                }
                if ($code -ne 0) {
                    [void][System.Threading.Monitor]::Enter($Prog.SyncRoot)
                    try {
                        $Prog.Failed = [int]$Prog.Failed + 1
                    }
                    finally {
                        [System.Threading.Monitor]::Exit($Prog.SyncRoot)
                    }
                    Write-Warning "Failed: $ArchivePath"
                }
                elseif ($DoDelete) {
                    try {
                        Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction Stop
                    }
                    catch {
                        [void][System.Threading.Monitor]::Enter($Prog.SyncRoot)
                        try {
                            $Prog.Failed = [int]$Prog.Failed + 1
                        }
                        finally {
                            [System.Threading.Monitor]::Exit($Prog.SyncRoot)
                        }
                        Write-Warning "Could not delete: $ArchivePath"
                    }
                }
                [void][System.Threading.Monitor]::Enter($Prog.SyncRoot)
                try {
                    $Prog.Done = [int]$Prog.Done + 1
                    $d = [int]$Prog.Done
                    $t = [int]$Prog.Total
                    $iv = [int]$Prog.Interval
                }
                finally {
                    [System.Threading.Monitor]::Exit($Prog.SyncRoot)
                }
                if ($t -gt 0) {
                    if ($d -eq $t) {
                        Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
                    }
                    elseif ($iv -gt 0 -and ($d % $iv) -eq 0) {
                        Write-Host ('[PROGRESS] ' + $d + ' / ' + $t + ' archives processed')
                    }
                }
            }).AddArgument($f.FullName).AddArgument($DestRootResolved).AddArgument($sevenZ).AddArgument($deleteSources).AddArgument($progressState).AddArgument($tarExe)
        $powershells += [PSCustomObject]@{
            PowerShell = $ps
            Handle     = $ps.BeginInvoke()
        }
    }
    foreach ($item in $powershells) {
        $item.PowerShell.EndInvoke($item.Handle)
        $item.PowerShell.Dispose()
    }
    $pool.Close()
    $pool.Dispose()
}

$sw.Stop()
$failed = [int]$progressState.Failed
$elapsedSec = [math]::Round($sw.Elapsed.TotalSeconds, 2)
Write-Host "Done. $total file(s) in ${elapsedSec}s (throttle=$throttle). Failures: $failed"
