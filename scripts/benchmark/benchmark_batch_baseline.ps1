# benchmark_batch_baseline.ps1
param (
    [int]$Iterations = 1
)

# Detect project root (directory where the script is located)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $ProjectRoot

$MainClass = "com.espertech.esper.example.IOT.JavaBatchBaseline"
$FeaturesDir = "$ProjectRoot\Datasets\EmbedFeature"
# Full dataset: all 9 cameras for final benchmark
$Cameras = "0001,0002,0011,0017,0019,0021,0025,0027,0030"
$OutputDir = "$ProjectRoot\output\benchmark_batch"

if (!(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir }

$Results = @()

function Run-Iteration($IterNum, $LogFile) {
    Write-Host "`n[Iteration $IterNum] Starting Java Batch Baseline..." -ForegroundColor Cyan
    
    # Reduced dataset: 10 windows (300 frames) to avoid memory issues while getting meaningful data
    $env:MAX_WINDOWS = "10"
    
    $Args = "--scene 2 --features_dir $FeaturesDir --camera '$Cameras' --output_dir $OutputDir"
    
    # Use Maven exec plugin with increased memory
    $Process = Start-Process mvn -ArgumentList "exec:java -Dexec.mainClass=`"$MainClass`" `"-Dexec.args=$Args`" -Dcheckstyle.skip=true -Dexec.classpathScope=compile -Dexec.maxMemory=4g" -PassThru -NoNewWindow -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"
    $Process.WaitForExit()

    # Extract timing metrics from log
    $Content = Get-Content $LogFile -Raw
    
    $Metrics = [PSCustomObject]@{
        Iteration = $IterNum
        MatrixGen = 0
        Clustering = 0
        CoreProcessing = 0
        TotalBatch = 0
    }
    
    if ($Content -match "Stage 4: Matrix Gen \(Raw\):\s+([\d\.]+)\s+ms") {
        $Metrics.MatrixGen = [double]$Matches[1]
    }
    if ($Content -match "Stage 7: Clustering \(HC\):\s+([\d\.]+)\s+ms") {
        $Metrics.Clustering = [double]$Matches[1]
    }
    if ($Content -match "Total Core Processing Time:\s+([\d\.]+)\s+ms") {
        $Metrics.CoreProcessing = [double]$Matches[1]
    }
    if ($Content -match "Total Batch Execution Time:\s+([\d\.]+)\s+ms") {
        $Metrics.TotalBatch = [double]$Matches[1]
    }
    
    return $Metrics
}

for ($i = 1; $i -le $Iterations; $i++) {
    $LogFile = "$OutputDir/log_batch_iter$i.txt"
    $Metrics = Run-Iteration $i $LogFile
    $Results += $Metrics
}

# Final Analysis
$AvgMatrixGen = ($Results.MatrixGen | Measure-Object -Average).Average
$AvgClustering = ($Results.Clustering | Measure-Object -Average).Average
$AvgCoreProcessing = ($Results.CoreProcessing | Measure-Object -Average).Average
$AvgTotalBatch = ($Results.TotalBatch | Measure-Object -Average).Average

Write-Host "`n" + ("=" * 60) -ForegroundColor Green
Write-Host "JAVA BATCH BASELINE BENCHMARK RESULTS ($Iterations Iterations)" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "Stage 4: Matrix Gen (Raw) - Average: $([Math]::Round($AvgMatrixGen, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 7: Clustering (HC) - Average: $([Math]::Round($AvgClustering, 2)) ms" -ForegroundColor Cyan
Write-Host "Total Core Processing Time - Average: $([Math]::Round($AvgCoreProcessing, 2)) ms" -ForegroundColor Cyan
Write-Host "Total Batch Execution Time - Average: $([Math]::Round($AvgTotalBatch, 2)) ms" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Green
