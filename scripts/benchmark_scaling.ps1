param(
    [int]$startWindow = 1,
    [int]$endWindow = 2
)

$outBase = ".\output\benchmarking\AIC-Dataset"

Write-Host "Rebuilding Java project once for the benchmark..."
cd "."
mvn clean compile

for ($w = $startWindow; $w -le $endWindow; $w++) {
    Write-Host "`n==============================================="
    Write-Host " Running Benchmark for $w Window(s)"
    Write-Host "==============================================="
    
    $env:MAX_WINDOWS = $w

    # Clean intermediate output paths to avoid crashes or dirty runs
    Remove-Item -Path "output\scene2" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\OURs\Thesis\AIC24_Track1_YACHIYO_RIIPS\Tracking\scene_002" -Recurse -Force -ErrorAction SilentlyContinue

    # # Java Run (Standard - All Pairs)
    # Write-Host "Running Java (Standard - All Pairs)..."
    # cd "."
    # $javaAllLog = "$outBase\Java_All\windows_$w.txt"
    # New-Item -ItemType Directory -Force -Path "$outBase\Java_All" | Out-Null
    # $argsAll = "--scene 2 --features_dir C:\OURs\Thesis\AIC24_Track1_YACHIYO_RIIPS\EmbedFeature --camera all --camera_groups all --turbo --exec_all"
    # cmd.exe /c "mvn exec:java -Dexec.mainClass=com.espertech.esper.example.IOT.IotMain -Dexec.args=`"$argsAll`" > `"$javaAllLog`" 2>&1"

    # # Java Run (Optimized - Grouped)
    # Write-Host "Running Java (Optimized - Grouped: [1,11][13,17])..."
    # $javaGroupLog = "$outBase\Java_Grouped\windows_$w.txt"
    # New-Item -ItemType Directory -Force -Path "$outBase\Java_Grouped" | Out-Null
    # $argsGroup = "--scene 2 --features_dir C:\OURs\Thesis\AIC24_Track1_YACHIYO_RIIPS\EmbedFeature --camera 0001,0011,0013,0017 --camera_groups 0001,0011;0013,0017 --turbo --exec_all"
    # cmd.exe /c "mvn exec:java -Dexec.mainClass=com.espertech.esper.example.IOT.IotMain -Dexec.args=`"$argsGroup`" > `"$javaGroupLog`" 2>&1"

    # Python Run (Batch)
    Write-Host "Running Python (Batch)..."
    cd "C:\OURs\Thesis\AIC24_Track1_YACHIYO_RIIPS"
    $pythonOutDir = "$outBase\Python"
    New-Item -ItemType Directory -Force -Path $pythonOutDir | Out-Null
    
    # Passing MAX_WINDOWS explicitly into WSL
    $bashCmd = "export MAX_WINDOWS=$w && cd /mnt/c/OURs/Thesis/AIC24_Track1_YACHIYO_RIIPS && source /home/mahmoud-tayee/thesis-venv/bin/activate && sh /mnt/c/OURs/Thesis/AIC24_Track1_YACHIYO_RIIPS/scripts/tracking.sh 2 > /mnt/c/OURs/Thesis/Real-Time_Multi-Camera_People_Tracking_using_Event_Stream_Processing/output/benchmarking/AIC-Dataset/Python/windows_$w.txt 2>&1"
    
    wsl -d Ubuntu -- bash -c $bashCmd
    
    Write-Host "Finished $w window(s)."
}

Write-Host "`nAll benchmarks from $startWindow to $endWindow completed."
Write-Host "Results saved to: $outBase"
