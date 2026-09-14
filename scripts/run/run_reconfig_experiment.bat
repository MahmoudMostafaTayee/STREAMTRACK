@echo off
REM Run script for Esper IOT Example - Reconfigurable Camera Topology Experiment (Scene 2)
REM Triggers a dynamic topology change at frame 180 (after window 2) and runs 6 windows total.

echo Cleaning up port 9999...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9999 ^| findstr LISTENING') do taskkill /f /pid %%a 2>nul

set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set MAX_WINDOWS=6
set "ARGS=--scene 2 --features_dir .\Datasets\EmbedFeature --camera 0001,0002,0011,0017,0019,0021,0025,0027,0030 --camera_groups ""2,17;1,11;19,27;21,25,30"" --turbo --output_dir ./output/reconfig_experiment --reconfig"

if not exist "output\reconfig_experiment" mkdir "output\reconfig_experiment"

echo Starting Maven for Reconfig Experiment (MAX_WINDOWS=%MAX_WINDOWS%)...
echo Output will be logged to output\reconfig_experiment\experiment.log
mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" -Dexec.args="%ARGS%" -Dcheckstyle.skip > output\reconfig_experiment\experiment.log 2>&1

echo Done. Check output\reconfig_experiment\experiment.log for results.
