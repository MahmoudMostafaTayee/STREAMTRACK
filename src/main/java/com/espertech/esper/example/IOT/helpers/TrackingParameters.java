package com.espertech.esper.example.IOT.helpers;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.JsonElement;
import org.apache.commons.cli.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class TrackingParameters {
    private static final Logger logger = LoggerFactory.getLogger(TrackingParameters.class);

    public enum exec_level {
        ALL, SCPT, MCPT
    };

    public static double epsilonScpt = 0.10;
    public static int timePeriod = 3;
    public static int fps = 30;
    public static double epsilonMcpt = 0.37;
    public static int shortTrackTh = 0;
    public static int keypointConditionTh = 2;
    public static boolean replaceSimilarityByWCoordinate = false; // Python default: False
    public static String distanceType = "max"; // Python default: "max"
    public static int distanceTh = 10; // Python default: 5
    public static double simTh = 0.75; // Python default: 0.75
    public static boolean reassign_global_id = true; // Python default: True
    public static boolean assign_all_tracklet = false; // Python default: False
    public static boolean delete_few_camera_cluster = true; // Python default: True
    public static double keypointTh = 0.7;
    public static double aspectTh = 1.6;
    public static double replaceValue = -10.0;
    public static int deleteGidTh = 6000;

    public static int min_samples = 4;
    public static String clustering_method = "agglomerative";
    public static String representativeSelectionMethod = "keypoint";

    public static exec_level exec_lvl = exec_level.ALL;
    public static double iouTh = 0.9;
    public static boolean overlap_suppression = true;
    public static boolean isDebug = false;
    public static int max_number_of_windows_to_process = 50; // Limit to 50 windows for benchmarking
    static {
        String mw = System.getenv("MAX_WINDOWS");
        if (mw != null && !mw.trim().isEmpty()) {
            try {
                max_number_of_windows_to_process = Integer.parseInt(mw.trim());
            } catch (NumberFormatException e) {
                // Ignore
            }
        }
    }
    public static boolean turboMode = false;
    public static boolean reconfigExperiment = false;

    // SNMS Parameters
    public static boolean sequential_nms = true;
    public static double temporally_snms_th = 0.6;
    public static double spatially_snms_th = 0.6;
    public static boolean merge_nonoverlap = true;

    // Separate Warp Parameters
    public static boolean separate_warp = true;
    public static int warp_th = 40;
    public static double alpha = 0.5;

    public static boolean exclude_short = false; // Python default: False
    public static int short_tracklet_th = 120; // Python default: 120

    public static boolean exclude_motionless = false; // Python default: False
    public static int stop_track_th = 25;

    // ===== Runtime-configurable paths =====
    public static String FEATURES_BASE_DIR;
    public static String OUTPUT_DIR;

    // ===== Camera selection =====
    // "all" OR "0001", "0002", ...
    public static String CAMERA_FILTER;

    // ===== Camera groups =====
    // "all" OR "1,2;2,3,4"
    public static String CAMERA_GROUPS;

    // ===== Camera transitions =====
    // e.g., "12:02,13,17"
    public static String CAMERA_TRANSITIONS = "";

    public static int scene = 2;

    private TrackingParameters() {
        /* Prevent instantiation */
    }

    public static ErrorCode getTrackingParams(String[] args) {

        CommandLine cmd = parseArguments(args);
        if (cmd == null) {
            return ErrorCode.INVALID_INPUT;
        }

        // ---------- Scene ----------
        if (cmd.hasOption("scene")) {
            scene = Integer.parseInt(cmd.getOptionValue("scene"));
        }

        // ---------- Feature directory ----------
        if (cmd.hasOption("features_dir")) {
            FEATURES_BASE_DIR = cmd.getOptionValue("features_dir");
        }

        // ---------- Output directory ----------
        OUTPUT_DIR = cmd.getOptionValue(
                "output_dir",
                "./output");

        // ---------- Camera filter ----------
        CAMERA_FILTER = cmd.getOptionValue("camera", "all");

        // ---------- Camera groups ----------
        CAMERA_GROUPS = cmd.getOptionValue("camera_groups", "all");

        // ---------- Camera transitions ----------
        CAMERA_TRANSITIONS = cmd.getOptionValue("camera_transitions", "");

        // ---------- Execution level ----------
        if (cmd.hasOption("exec_all")) {
            exec_lvl = exec_level.ALL;
        } else if (cmd.hasOption("exec_scpt")) {
            exec_lvl = exec_level.SCPT;
        } else if (cmd.hasOption("exec_mcpt")) {
            exec_lvl = exec_level.MCPT;
        }

        // ---------- Scene-specific parameters ----------
        getParametersForScene(scene);

        // ---------- Create output directory ----------
        createOutputDirectory();

        // ---------- Log everything ----------
        printArgs();

        // ---------- Debug Mode ----------
        isDebug = cmd.hasOption("debug");

        // ---------- Turbo Mode ----------
        turboMode = cmd.hasOption("turbo");

        // ---------- Reconfig Experiment ----------
        reconfigExperiment = cmd.hasOption("reconfig");

        // ---------- Clustering Method ----------
        // The CLI flag takes precedence over scene configuration; only override
        // when explicitly provided so a scene file can select the clusterer.
        if (cmd.hasOption("clusterer")) {
            clustering_method = cmd.getOptionValue("clusterer");
        }

        return ErrorCode.SUCCESS;
    }

    private static void createOutputDirectory() {
        try {
            java.nio.file.Files.createDirectories(
                    java.nio.file.Paths.get(OUTPUT_DIR));
        } catch (Exception e) {
            logger.error("Failed to create output directory: " + OUTPUT_DIR, e);
        }
    }

    private static CommandLine parseArguments(String[] args) {
        Options options = new Options();

        options.addOption(Option.builder()
                .longOpt("scene")
                .hasArg()
                .build());

        options.addOption(Option.builder()
                .longOpt("features_dir")
                .hasArg()
                .desc("Base directory for embedding features")
                .build());
        options.addOption(Option.builder()
                .longOpt("camera")
                .hasArg()
                .desc("Camera number (e.g., 0001) or 'all'")
                .build());

        options.addOption(Option.builder()
                .longOpt("camera_groups")
                .hasArg()
                .desc("Camera groups (e.g., '1,2;2,3,4') or 'all'")
                .build());

        options.addOption(Option.builder()
                .longOpt("camera_transitions")
                .hasArg()
                .desc("Camera transitions (e.g., '12:02,13,17')")
                .build());

        options.addOption(Option.builder()
                .longOpt("output_dir")
                .hasArg()
                .desc("Directory to save logs and outputs")
                .build());

        options.addOption(Option.builder().longOpt("debug").desc("Debug mode").build());
        options.addOption(Option.builder().longOpt("turbo").desc("Turbo mode").build());
        options.addOption(Option.builder().longOpt("reconfig").desc("Enable runtime topology reconfiguration experiment").build());

        options.addOption(Option.builder().longOpt("exec_all").desc("Execute all stages").build());
        options.addOption(Option.builder().longOpt("exec_scpt").desc("Execute SCPT stage").build());
        options.addOption(Option.builder().longOpt("exec_mcpt").desc("Execute MCPT stage").build());

        options.addOption(Option.builder()
                .longOpt("clusterer")
                .hasArg()
                .desc("Clustering algorithm (agglomerative, clustream, clustree)")
                .build());

        CommandLineParser parser = new DefaultParser();
        HelpFormatter formatter = new HelpFormatter();

        try {
            return parser.parse(options, args);
        } catch (ParseException e) {
            formatter.printHelp("MCPT", options);
            return null;
        }
    }

    /**
     * Parameters that may be overridden by a scene configuration file.
     * Keep in sync with {@code IotMain.streamInitialConfigEvents()}, which
     * exposes the same set (plus runtime reconfiguration) as MCPTConfig events.
     */
    private static final String[] CONFIG_PARAM_NAMES = {
            "epsilonScpt", "timePeriod", "fps", "epsilonMcpt", "shortTrackTh",
            "keypointConditionTh", "replaceSimilarityByWCoordinate", "distanceType",
            "distanceTh", "simTh", "reassign_global_id", "assign_all_tracklet",
            "delete_few_camera_cluster", "keypointTh", "aspectTh", "replaceValue",
            "deleteGidTh", "min_samples", "clustering_method",
            "representativeSelectionMethod", "iouTh", "overlap_suppression",
            "sequential_nms", "temporally_snms_th", "spatially_snms_th",
            "merge_nonoverlap", "separate_warp", "warp_th", "alpha",
            "exclude_short", "short_tracklet_th", "exclude_motionless", "stop_track_th"
    };

    /**
     * Load scene-specific parameters from a JSON configuration file.
     * <p>
     * Resolution order (first existing file wins):
     * <ol>
     *   <li>{@code <OUTPUT_DIR-agnostic> config/scene_NNN.json} — explicit per-scene override</li>
     *   <li>{@code config/scenes/scene_NNN.json} — shipped scene defaults</li>
     * </ol>
     * If no configuration file exists for the scene, class-level defaults are kept
     * and a debug message is logged. Keys that do not map to a known parameter are
     * logged loudly and ignored so typos are not silently swallowed. Values are
     * applied to the corresponding public static fields of this class.
     */
    private static void getParametersForScene(int scene) {
        String fileName = String.format("scene_%03d.json", scene);

        Path configPath = Paths.get("config", fileName);
        if (!Files.isRegularFile(configPath)) {
            configPath = Paths.get("config", "scenes", fileName);
        }
        if (!Files.isRegularFile(configPath)) {
            logger.debug("No scene configuration file for scene {} ({}); using class defaults", scene, fileName);
            return;
        }

        loadSceneConfig(configPath);
    }

    /**
     * Parse the given JSON file and apply every recognized key to the
     * matching public static field of {@link TrackingParameters}.
     */
    private static void loadSceneConfig(Path configPath) {
        JsonObject root;
        try (InputStream in = Files.newInputStream(configPath)) {
            root = JsonParser.parseString(
                    new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8)
            ).getAsJsonObject();
        } catch (IOException | com.google.gson.JsonSyntaxException e) {
            logger.error("Failed to read scene configuration {}: {} — using class defaults", configPath, e.getMessage());
            return;
        }

        int applied = 0;
        for (String key : CONFIG_PARAM_NAMES) {
            if (!root.has(key) || root.get(key).isJsonNull()) {
                continue;
            }
            JsonElement value = root.get(key);
            try {
                java.lang.reflect.Field field = TrackingParameters.class.getField(key);
                if (field.getType() == double.class) {
                    field.setDouble(null, value.getAsDouble());
                } else if (field.getType() == int.class) {
                    field.setInt(null, value.getAsInt());
                } else if (field.getType() == boolean.class) {
                    field.setBoolean(null, value.getAsBoolean());
                } else {
                    field.set(null, value.getAsString());
                }
                applied++;
            } catch (NoSuchFieldException e) {
                logger.warn("Scene config references unknown parameter '{}' — ignoring", key);
            } catch (IllegalAccessException | IllegalArgumentException e) {
                logger.warn("Scene config: cannot apply '{}' ({}): {} — ignoring", key, value, e.getMessage());
            }
        }

        // Surface any keys we do not recognize so typos are not silently dropped
        java.util.Set<String> known = new java.util.HashSet<>(java.util.Arrays.asList(CONFIG_PARAM_NAMES));
        for (String key : root.keySet()) {
            if (key.startsWith("_")) {
                continue; // convention for comment/metadata keys
            }
            if (!known.contains(key)) {
                logger.warn("Scene config {}: unrecognized key '{}' — ignoring", configPath, key);
            }
        }

        logger.info("Loaded {} scene parameter(s) for scene config {}", applied, configPath);
    }

    public static void printArgs() {
        logger.info(
                "TrackingParameters{" +
                        "scene=" + scene +
                        ", FEATURES_BASE_DIR='" + FEATURES_BASE_DIR + '\'' +
                        ", OUTPUT_DIR='" + OUTPUT_DIR + '\'' +
                        ", CAMERA_FILTER='" + CAMERA_FILTER + '\'' +
                        ", CAMERA_GROUPS='" + CAMERA_GROUPS + '\'' +
                        ", CAMERA_TRANSITIONS='" + CAMERA_TRANSITIONS + '\'' +
                        ", epsilonScpt=" + epsilonScpt +
                        ", timePeriod=" + timePeriod +
                        ", epsilonMcpt=" + epsilonMcpt +
                        ", shortTrackTh=" + shortTrackTh +
                        ", keypointConditionTh=" + keypointConditionTh +
                        ", replaceSimilarityByWCoordinate=" + replaceSimilarityByWCoordinate +
                        ", distanceType='" + distanceType + '\'' +
                        ", distanceTh=" + distanceTh +
                        ", simTh=" + simTh +
                        ", deleteGidTh=" + deleteGidTh +
                        ", exec_lvl=" + exec_lvl +
                        '}');
    }

}
