@echo off
set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set FEATURES_DIR=.\Datasets\EmbedFeature

echo Running Java Topology-aware Grouping (1 Window benchmark)...
mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" "-Dexec.args=--scene 2 --features_dir %FEATURES_DIR% --camera all --camera_groups 0001,0011;0013,0017 --turbo --output_dir ./output/bench_topo" -Dcheckstyle.skip=true
