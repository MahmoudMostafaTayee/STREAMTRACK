# benchmark_topology.ps1

$MainClass = "com.espertech.esper.example.IOT.IotMain"
$FeaturesDir = ".\Datasets\EmbedFeature"
$Cameras = "0001,0002,0011,0017,0019,0021,0025,0027,0030"
$OutputDir = "./output/benchmark"

if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir
}

function Run-Benchmark($GroupName, $CameraGroups, $LogFile) {
    Write-Host "Cleaning up port 9999..."
    Get-NetTCPConnection -LocalPort 9999 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2

    Write-Host "Starting Benchmark: $GroupName" -ForegroundColor Cyan
    Write-Host "Groups: $CameraGroups" -ForegroundColor Gray
    
    $Args = "--scene 2 --features_dir $FeaturesDir --camera '$Cameras' --camera_groups '$CameraGroups' --turbo --output_dir $OutputDir"
    
    # Start Maven in the background
    $Process = Start-Process mvn -ArgumentList "exec:java -Dexec.mainClass=`"$MainClass`" `"-Dexec.args=$Args`" -Dcheckstyle.skip=true" -PassThru -NoNewWindow -RedirectStandardOutput $LogFile
    
    # Wait for the process to finish (processes 50 windows)
    $Process.WaitForExit()
    
    # Stop the process
    Write-Host "Stopping process..."
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    
    # Kill any child Java processes that might be lingering
    Get-Process java -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt $Process.StartTime } | Stop-Process -Force -ErrorAction SilentlyContinue
}

$GlobalLog = "$OutputDir/log_global.txt"
$TopologyLog = "$OutputDir/log_topology.txt"

# 1. Run Global Baseline
Run-Benchmark "Global Baseline" $Cameras $GlobalLog

# 2. Run Topology-Aware
Run-Benchmark "Topology-Aware" "2,17;1,11;19,27;21,25,30" $TopologyLog

Write-Host "`nBenchmark Complete. Analyzing results...`n" -ForegroundColor Green

function Analyze-Log($LogFile) {
    if (!(Test-Path $LogFile)) {
        Write-Host "Log file not found: $LogFile" -ForegroundColor Red
        return $null
    }
    
    $Content = Get-Content $LogFile
    $Times = $Content | Where-Object { $_ -match "Total MCPT Time:\s+([\d\.]+)\s+ms" } | ForEach-Object {
        if ($_ -match "Total MCPT Time:\s+([\d\.]+)\s+ms") {
            [double]$Matches[1]
        }
    }
    
    if ($Times.Count -eq 0) {
        Write-Host "No timing data found in $LogFile" -ForegroundColor Yellow
        return $null
    }
    
    # Skip the first 2 windows to allow for JVM warmup/caching
    $RelevantTimes = $Times | Select-Object -Skip 2
    if ($RelevantTimes.Count -eq 0) { $RelevantTimes = $Times }
    
    $AvgTime = ($RelevantTimes | Measure-Object -Average).Average
    $MinTime = ($RelevantTimes | Measure-Object -Minimum).Minimum
    $MaxTime = ($RelevantTimes | Measure-Object -Maximum).Maximum
    
    return @{
        Avg = $AvgTime
        Min = $MinTime
        Max = $MaxTime
        Count = $RelevantTimes.Count
    }
}

$GlobalStats = Analyze-Log $GlobalLog
$TopologyStats = Analyze-Log $TopologyLog

if ($GlobalStats -and $TopologyStats) {
    $Speedup = $GlobalStats.Avg / $TopologyStats.Avg
    
    Write-Host "==================================================" -ForegroundColor White
    Write-Host "PERFORMANCE COMPARISON REPORT" -ForegroundColor Cyan
    Write-Host "==================================================" -ForegroundColor White
    Write-Host "Global Baseline (1 Group):"
    Write-Host "  Average Latency:  $([Math]::Round($GlobalStats.Avg, 2)) ms"
    Write-Host "  Min/Max:          $([Math]::Round($GlobalStats.Min, 2)) / $([Math]::Round($GlobalStats.Max, 2)) ms"
    Write-Host "  Windows Captured: $($GlobalStats.Count)"
    Write-Host "--------------------------------------------------"
    Write-Host "Topology-Aware (4 Groups):"
    Write-Host "  Average Latency:  $([Math]::Round($TopologyStats.Avg, 2)) ms"
    Write-Host "  Min/Max:          $([Math]::Round($TopologyStats.Min, 2)) / $([Math]::Round($TopologyStats.Max, 2)) ms"
    Write-Host "  Windows Captured: $($TopologyStats.Count)"
    Write-Host "==================================================" -ForegroundColor White
    Write-Host "SPEEDUP FACTOR:     $([Math]::Round($Speedup, 2))x" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor White
    
    # Output to CSV for easy parsing later
    "Metric,Global,Topology,Speedup" | Out-File "$OutputDir/results.csv"
    "AvgLatency,$($GlobalStats.Avg),$($TopologyStats.Avg),$Speedup" | Out-File "$OutputDir/results.csv" -Append
}
