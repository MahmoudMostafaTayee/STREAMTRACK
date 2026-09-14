@echo off
cd /d .
set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set CAMERAS=0001,0002,0011,0017,0019,0021,0025,0027,0030

echo Running Global Baseline (9 cameras, all as one group)...
echo.
mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" "-Dexec.args=--scene 2 --features_dir ./Datasets/EmbedFeature --camera %CAMERAS% --camera_groups %CAMERAS% --turbo --output_dir ./output/benchmark" -Dcheckstyle.skip=true
