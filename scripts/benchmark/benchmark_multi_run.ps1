# benchmark_multi_run.ps1
param (
    [int]$Iterations = 1,
    [int]$MaxWindows = 1
)

# Detect project root (directory where the script is located)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $ProjectRoot

$MainClass = "com.espertech.esper.example.IOT.IotMain"
$FeaturesDir = "$ProjectRoot\Datasets\EmbedFeature"
$Cameras = "0001,0002,0011,0017,0019,0021,0025,0027,0030"
$TopologyGroups = "2,17;1,11;19,27;21,25,30"
$OutputDir = "$ProjectRoot\output\benchmark_multi"

if (!(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir }

$GlobalResults = @()
$TopologyResults = @()

function Run-Iteration($IterNum, $GroupName, $CameraGroups, $LogFile) {
    Write-Host "`n[Iteration $IterNum] Starting $GroupName..." -ForegroundColor Cyan
    
    # Kill lingering processes
    Get-NetTCPConnection -LocalPort 9999 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    
    # Set environment variable for window limit
    $env:MAX_WINDOWS = $MaxWindows
    
    $Args = "--scene 2 --features_dir $FeaturesDir --camera '$Cameras' --camera_groups '$CameraGroups' --turbo --output_dir $OutputDir"
    
    # Run Maven and wait for completion
    $Process = Start-Process mvn -ArgumentList "exec:java -Dexec.mainClass=`"$MainClass`" `"-Dexec.args=$Args`" -Dcheckstyle.skip=true" -PassThru -NoNewWindow -RedirectStandardOutput $LogFile
    $Process.WaitForExit()

    # Extract latencies from log using a more reliable split method
    $Latencies = Get-Content $LogFile | Select-String "Total MCPT Time:" | ForEach-Object { 
        $line = $_.ToString()
        if ($line -match "Total MCPT Time:\s+([\d\.]+)\s+ms") {
            [double]$Matches[1]
        }
    }
    return $Latencies
}

for ($i = 1; $i -le $Iterations; $i++) {
    $GlobalLog = "$OutputDir/log_global_iter$i.txt"
    $TopologyLog = "$OutputDir/log_topo_iter$i.txt"

    # 1. Global Run
    $gLats = Run-Iteration $i "Global Baseline" $Cameras $GlobalLog
    $GlobalResults += $gLats

    # 2. Topology Run
    $tLats = Run-Iteration $i "Topology-Aware" $TopologyGroups $TopologyLog
    $TopologyResults += $tLats
}

# Final Analysis
$gAvg = ($GlobalResults | Measure-Object -Average).Average
$tAvg = ($TopologyResults | Measure-Object -Average).Average
$speedup = if ($tAvg -gt 0) { $gAvg / $tAvg } else { 0 }

Write-Host "`n" + ("=" * 50) -ForegroundColor Green
Write-Host "FINAL AGGREGATED RESULTS ($Iterations Iterations, $MaxWindows Windows)" -ForegroundColor Green
Write-Host ("=" * 50) -ForegroundColor Green
Write-Host "Global Average:   $([Math]::Round($gAvg, 2)) ms (Total $($GlobalResults.Count) data points)"
Write-Host "Topology Average: $([Math]::Round($tAvg, 2)) ms (Total $($TopologyResults.Count) data points)"
Write-Host "AVERAGE SPEEDUP:  $([Math]::Round($speedup, 2))x" -ForegroundColor Yellow
Write-Host ("=" * 50) -ForegroundColor Green
