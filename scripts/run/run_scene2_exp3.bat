@echo off
REM Run script for Esper IOT Example - Experiment 3 (Scene 2, Topology Grouping)

echo Cleaning up port 9999...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :9999 ^| findstr LISTENING') do taskkill /f /pid %%a

set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set "ARGS=--scene 2 --features_dir .\Datasets\EmbedFeature --camera all --camera_groups ""0001,0011;0013,0017"" --output_dir ./output/scene2_exp3"

echo Starting Python Table Listener in a new window...
start "Python Table Listener" cmd /k "python scriptsisten_to_table.py"

mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" -Dexec.args="%ARGS%" -Dcheckstyle.skip
