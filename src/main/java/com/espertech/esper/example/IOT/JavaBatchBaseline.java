package com.espertech.esper.example.IOT;

import com.espertech.esper.example.IOT.helpers.TrackingParameters;
import com.espertech.esper.example.IOT.helpers.ErrorCode;
import com.espertech.esper.example.IOT.helpers.HelperUtils;
import com.espertech.esper.example.IOT.helpers.ClusteringUtils;
import com.espertech.esper.example.IOT.clusterers.MCPT;
import com.espertech.esper.example.IOT.clusterers.SCPT;
import org.nd4j.linalg.api.ndarray.INDArray;
import org.nd4j.linalg.factory.Nd4j;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileReader;
import java.io.FileWriter;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class JavaBatchBaseline {
    private static final Logger logger = LoggerFactory.getLogger(JavaBatchBaseline.class);
    private static final Pattern FILE_PATTERN = Pattern
            .compile("feature_(\\d+)_(\\d+)_(\\d+)_(\\d+)_(\\d+)_(\\d+)_(\\d+\\.?\\d*)\\.npy");

    // Feature cache for lazy loading - maps file path to loaded feature array
    private static final Map<String, double[]> featureCache = new HashMap<>();

    private static class PoseData {
        List<Float> bbox;
        List<List<Float>> keypoints;
    }

    /**
     * Lazy load feature from .npy file with caching
     * Python equivalent: np.load() - only loads when needed
     */
    private static double[] loadFeatureWithCache(Path npyFile) {
        String filePath = npyFile.toString();
        
        // Check cache first
        if (featureCache.containsKey(filePath)) {
            return featureCache.get(filePath);
        }
        
        // Load from file
        try {
            INDArray data = Nd4j.createFromNpyFile(npyFile.toFile());
            double[] feature = data.toDoubleVector();
            featureCache.put(filePath, feature);
            return feature;
        } catch (Exception e) {
            logger.error("Error reading feature from " + filePath, e);
            return null;
        }
    }

    /**
     * Load features for specific serials on-demand
     * This is called before MCPT stages that need features
     * Python equivalent: features are loaded lazily during MCPT operations
     */
    private static void loadFeaturesForSerials(Map<Integer, Map<String, Map<String, Object>>> trackingResults, Set<String> serialsToLoad) {
        logger.info("Loading features for " + serialsToLoad.size() + " serials with caching...");
        int loadedCount = 0;
        int errorCount = 0;

        for (Map.Entry<Integer, Map<String, Map<String, Object>>> camEntry : trackingResults.entrySet()) {
            for (Map.Entry<String, Map<String, Object>> serialEntry : camEntry.getValue().entrySet()) {
                String serial = serialEntry.getKey();
                if (!serialsToLoad.contains(serial)) {
                    continue;
                }
                
                Map<String, Object> detection = serialEntry.getValue();
                String featurePath = (String) detection.get("FeaturePath");
                
                if (featurePath != null && detection.get("Feature") == null) {
                    double[] feature = loadFeatureWithCache(Paths.get(featurePath));
                    if (feature != null) {
                        detection.put("Feature", feature);
                        loadedCount++;
                    } else {
                        errorCount++;
                    }
                }
            }
        }
        
        logger.info("Loaded " + loadedCount + " features successfully, " + errorCount + " errors");
        logger.info("Feature cache size: " + featureCache.size());
    }

    public static void main(String[] args) {
        long tTotalStart = System.nanoTime();

        // 1. Parse CLI arguments
        ErrorCode retval = TrackingParameters.getTrackingParams(args);
        if (retval != ErrorCode.SUCCESS) {
            logger.error("Invalid arguments: " + retval.getMessage());
            System.exit(retval.getCode());
        }

        logger.info("Executing Java Batch Baseline for scene " + TrackingParameters.scene);

        // 2. Discover cameras
        List<String> cameraNames = getCameraList();
        if (cameraNames.isEmpty()) {
            logger.error("No cameras found or specified.");
            System.exit(1);
        }

        // 3. Load all calibration data
        Map<Integer, double[][]> calibrationMap = loadCalibrationData(cameraNames, TrackingParameters.scene);

        // 4. Determine frames limits
        int maxFrames = TrackingParameters.max_number_of_windows_to_process 
                * TrackingParameters.timePeriod 
                * TrackingParameters.fps;
        logger.info("Max frames to process: " + maxFrames);

        // 5. Load feature files & keypoints
        long tLoadStart = System.nanoTime();
        Map<Integer, Map<String, Map<String, Object>>> trackingResults = new HashMap<>();
        long globalCounter = 0;

        for (String cameraName : cameraNames) {
            int cameraId = Integer.parseInt(cameraName.replace("camera_", ""));
            Path cameraDir = Paths.get(TrackingParameters.FEATURES_BASE_DIR, 
                    String.format("scene_%03d", TrackingParameters.scene), cameraName);

            if (!Files.isDirectory(cameraDir)) {
                logger.warn("Camera directory not found: " + cameraDir);
                continue;
            }

            // Load pose keypoints
            Map<Integer, List<PoseData>> poseCache = loadPoseData(cameraDir);

            // Get sorted .npy files
            List<Path> files;
            try {
                files = HelperUtils.getSortedFiles(cameraDir, "*.npy");
            } catch (Exception e) {
                logger.error("Error reading files for camera " + cameraName, e);
                continue;
            }

            Map<String, Map<String, Object>> trackingDict = new HashMap<>();

            for (Path file : files) {
                String fileName = file.getFileName().toString();
                Matcher matcher = FILE_PATTERN.matcher(fileName);
                if (!matcher.matches()) {
                    continue;
                }

                int curFrame = Integer.parseInt(matcher.group(1));
                if (curFrame > maxFrames) {
                    continue;
                }

                int uNum = Integer.parseInt(matcher.group(2)) - 1; // OfflineID tracklet index
                int x1 = Integer.parseInt(matcher.group(3));
                int x2 = Integer.parseInt(matcher.group(4));
                int y1 = Integer.parseInt(matcher.group(5));
                int y2 = Integer.parseInt(matcher.group(6));
                float conf = Float.parseFloat(matcher.group(7));

                // Load .npy feature immediately (original approach)
                double[] feature;
                try {
                    File npyFile = file.toFile();
                    INDArray data = Nd4j.createFromNpyFile(npyFile);
                    feature = data.toDoubleVector();
                } catch (Exception e) {
                    logger.error("Error reading feature from " + fileName, e);
                    continue;
                }

                // Match keypoints
                List<List<Float>> keypoints = getMatchingKeypoints(poseCache, curFrame, x1, y1, x2, y2);

                String serial = String.format("%08d", globalCounter++);

                Map<String, Object> detection = new HashMap<>();
                detection.put("OfflineID", uNum);
                detection.put("Frame", curFrame);
                detection.put("Timestamp", System.currentTimeMillis());

                Map<String, Integer> coord = new HashMap<>();
                coord.put("x1", x1);
                coord.put("x2", x2);
                coord.put("y1", y1);
                coord.put("y2", y2);
                detection.put("Coordinate", coord);

                detection.put("Feature", feature);
                detection.put("Keypoints", keypoints);

                trackingDict.put(serial, detection);
            }

            trackingResults.put(cameraId, trackingDict);
            logger.info("Loaded " + trackingDict.size() + " detections for camera " + cameraId);
        }
        long tLoadEnd = System.nanoTime();
        
        // ==================== SCPT PHASE (Stage 0b) ====================
        long tScptStart = System.nanoTime();
        trackingResults = runScptBatch(trackingResults);
        long tScptEnd = System.nanoTime();

        // 6. Measure World Coordinates (Stage 1)
        long tWCoordStart = System.nanoTime();
        trackingResults = MCPT.measureWorldCoordinate(TrackingParameters.scene, trackingResults);
        long tWCoordEnd = System.nanoTime();

        // Verify if world coordinates were computed
        boolean worldCoordAvailable = false;
        if (!trackingResults.isEmpty()) {
            Map<String, Map<String, Object>> firstCam = trackingResults.values().iterator().next();
            if (!firstCam.isEmpty()) {
                Map<String, Object> firstTrack = firstCam.values().iterator().next();
                if (firstTrack.containsKey("WorldCoordinate")) {
                    worldCoordAvailable = true;
                }
            }
        }
        boolean replaceSimilarityByWCoordinate = TrackingParameters.replaceSimilarityByWCoordinate;
        if (replaceSimilarityByWCoordinate && !worldCoordAvailable) {
            logger.warn("replaceSimilarityByWCoordinate requested but World Coordinates not available. Disabling.");
            replaceSimilarityByWCoordinate = false;
        }

        // === INCREMENTAL MCPT CHECKPOINT BENCHMARK ===
        runIncrementalMcptBenchmark(trackingResults, replaceSimilarityByWCoordinate,
                TrackingParameters.max_number_of_windows_to_process);
        // =============================================

        // 7. Representative Selection (Stage 1)
        long tRepStart = System.nanoTime();
        Map<Integer, Map<Integer, MCPT.RepresentativeNode>> representativeNodes = MCPT.decideRepresentativeNodes(
                trackingResults,
                TrackingParameters.representativeSelectionMethod,
                TrackingParameters.epsilonMcpt,
                TrackingParameters.shortTrackTh,
                TrackingParameters.keypointTh,
                new int[] { 1920, 1080 },
                TrackingParameters.aspectTh,
                2000
        );
        long tRepEnd = System.nanoTime();

        if (TrackingParameters.isDebug) {
            Map<Integer, Map<Integer, Map<String, Object>>> dumpRepNodes = new HashMap<>();
            for (Map.Entry<Integer, Map<Integer, MCPT.RepresentativeNode>> camEntry : representativeNodes.entrySet()) {
                Map<Integer, Map<String, Object>> camRepNodes = new HashMap<>();
                for (Map.Entry<Integer, MCPT.RepresentativeNode> nodeEntry : camEntry.getValue().entrySet()) {
                    Map<String, Object> nodeMap = new HashMap<>();
                    nodeMap.put("serial", nodeEntry.getValue().serial);
                    nodeMap.put("score", nodeEntry.getValue().score);
                    nodeMap.put("allSerials", nodeEntry.getValue().allSerials);
                    camRepNodes.put(nodeEntry.getKey(), nodeMap);
                }
                dumpRepNodes.put(camEntry.getKey(), camRepNodes);
            }
            dumpMcptParams(Collections.singletonMap("representativeNodes", dumpRepNodes),
                    "mcpt-representative-nodes-java_batch_0");

            Map<String, Object> params = new LinkedHashMap<>();
            params.put("epsilon", TrackingParameters.epsilonMcpt);
            params.put("shortTrackTh", TrackingParameters.shortTrackTh);
            params.put("keypointTh", TrackingParameters.keypointTh);
            params.put("keypointConditionTh", TrackingParameters.keypointConditionTh);
            params.put("replaceSimilarityByWCoordinate", replaceSimilarityByWCoordinate);
            params.put("distanceType", TrackingParameters.distanceType);
            params.put("distanceTh", TrackingParameters.distanceTh);
            params.put("replaceValue", TrackingParameters.replaceValue);

            Map<Integer, Map<String, Map<String, Object>>> filteredTrackingResults = new HashMap<>();
            for (Map.Entry<Integer, Map<String, Map<String, Object>>> camEntry : trackingResults.entrySet()) {
                Map<String, Map<String, Object>> camData = new HashMap<>();
                for (Map.Entry<String, Map<String, Object>> serialEntry : camEntry.getValue().entrySet()) {
                    Map<String, Object> trackletData = new HashMap<>(serialEntry.getValue());
                    trackletData.remove("Keypoints");
                    trackletData.remove("Feature");
                    camData.put(serialEntry.getKey(), trackletData);
                }
                filteredTrackingResults.put(camEntry.getKey(), camData);
            }
            params.put("trackingResults", filteredTrackingResults);
            dumpMcptParams(params, "mcpt-params-java_batch_0");
        }

        // 8. Matrix Gen (Raw) (Stage 2)
        long tSimStart = System.nanoTime();
        double[][] similarityMatrix = MCPT.createSimilarityMatrixMCPT(
                representativeNodes,
                TrackingParameters.shortTrackTh,
                TrackingParameters.keypointConditionTh
        );
        long tSimRaw = System.nanoTime();

        if (TrackingParameters.isDebug) {
            dumpMcptMatrix(similarityMatrix, "mcpt-similarity-matrix-raw_batch_0");
        }

        // 9. Matrix Zeroing (Stage 3)
        for (int i = 0; i < similarityMatrix.length; i++) {
            for (int j = 0; j < similarityMatrix[i].length; j++) {
                if (similarityMatrix[i][j] < 1.0 - TrackingParameters.epsilonMcpt) {
                    similarityMatrix[i][j] = 0.0;
                }
            }
        }
        long tSimZeroed = System.nanoTime();

        if (TrackingParameters.isDebug) {
            dumpMcptMatrix(similarityMatrix, "mcpt-similarity-matrix-zeroed_batch_0");
        }

        List<Integer> clusters = new ArrayList<>();
        for (int i = 0; i < similarityMatrix.length; i++) {
            clusters.add(i);
        }

        // 10. Similarity Replace (World) (Stage 4)
        long tReplaceStart = System.nanoTime();
        similarityMatrix = MCPT.replaceSimilarity(
                representativeNodes,
                similarityMatrix,
                trackingResults,
                clusters,
                false,
                replaceSimilarityByWCoordinate,
                TrackingParameters.distanceType,
                TrackingParameters.distanceTh,
                TrackingParameters.replaceValue,
                TrackingParameters.shortTrackTh,
                TrackingParameters.keypointConditionTh
        );
        long tReplaceEnd = System.nanoTime();

        if (TrackingParameters.isDebug) {
            dumpMcptMatrix(similarityMatrix, "mcpt-similarity-matrix-replaced_batch_0");
        }

        // 11. Clustering (HC) (Stage 5)
        long tHcStart = System.nanoTime();
        clusters = SCPT.associateCluster(
                clusters,
                similarityMatrix,
                TrackingParameters.epsilonMcpt,
                true,
                2,
                false
        );
        long tHcEnd = System.nanoTime();

        if (TrackingParameters.isDebug) {
            dumpMcptClusters(clusters, "mcpt-clusters-after-hc_batch_0");
        }

        // 12. Global ID Assignment (Stage 6)
        long tPostStart = System.nanoTime();
        Map<Integer, MCPT.CameraDict> cameraDict = MCPT.createCameraDict(
                representativeNodes,
                TrackingParameters.shortTrackTh,
                TrackingParameters.keypointConditionTh
        );

        for (Map.Entry<Integer, MCPT.CameraDict> cameraEntry : cameraDict.entrySet()) {
            Integer cameraId = cameraEntry.getKey();
            Map<String, Map<String, Object>> trackingDict = trackingResults.get(cameraId);
            MCPT.CameraDict dict = cameraEntry.getValue();

            List<Integer> indices = dict.indices;
            List<Integer> localIds = dict.uniqueLocalIds;

            Map<Integer, Integer> localIdClusterDict = new HashMap<>();
            for (int i = 0; i < indices.size(); i++) {
                int clusterId = clusters.get(indices.get(i));
                localIdClusterDict.put(localIds.get(i), clusterId);
            }

            for (Map.Entry<String, Map<String, Object>> entry : trackingDict.entrySet()) {
                Integer localId = (Integer) entry.getValue().get("OfflineID");
                if (localIdClusterDict.containsKey(localId)) {
                    entry.getValue().put("GlobalOfflineID", localIdClusterDict.get(localId));
                }
            }
        }
        long tPostEnd = System.nanoTime();

        if (TrackingParameters.isDebug) {
            dumpMcptCameraDict(cameraDict, "mcpt-camera-dict_batch_0");
            dumpMcptGlobalIds(trackingResults, "mcpt-global-ids_batch_0");
        }

        // 13. Global ID Reassignment (Stage 7 - post-processing)
        long tReassignStart = System.nanoTime();
        if (TrackingParameters.reassign_global_id) {
            trackingResults = MCPT.globalIdReassignment(
                    trackingResults,
                    representativeNodes,
                    TrackingParameters.deleteGidTh,
                    TrackingParameters.simTh,
                    TrackingParameters.assign_all_tracklet,
                    TrackingParameters.delete_few_camera_cluster
            );
        }
        long tReassignEnd = System.nanoTime();

        long tTotalEnd = System.nanoTime();

        // Print Performance timing reports to console
        System.out.println("\n" + "=".repeat(50));
        System.out.println("PERFORMANCE REPORT (MCPT - Java Batch Baseline)");
        System.out.println("-".repeat(50));
        System.out.printf("Stage 1: Load Features & Keypoints:      %.2f ms%n", (tLoadEnd - tLoadStart) / 1_000_000.0);
        System.out.printf("Stage 2: SCPT Batch Clustering:         %.2f ms%n", (tScptEnd - tScptStart) / 1_000_000.0);
        System.out.printf("Stage 3: Measure World Coordinates:     %.2f ms%n", (tWCoordEnd - tWCoordStart) / 1_000_000.0);
        System.out.printf("Stage 4: Representative Selection:      %.2f ms%n", (tRepEnd - tRepStart) / 1_000_000.0);
        System.out.printf("Stage 5: Matrix Gen (Raw):              %.2f ms%n", (tSimRaw - tSimStart) / 1_000_000.0);
        System.out.printf("Stage 6: Matrix Zeroing:                %.2f ms%n", (tSimZeroed - tSimRaw) / 1_000_000.0);
        System.out.printf("Stage 7: Similarity Replace (World):    %.2f ms%n", (tReplaceEnd - tReplaceStart) / 1_000_000.0);
        System.out.printf("Stage 8: Clustering (HC):               %.2f ms%n", (tHcEnd - tHcStart) / 1_000_000.0);
        System.out.printf("Stage 9: Global ID Assignment:          %.2f ms%n", (tPostEnd - tPostStart) / 1_000_000.0);
        System.out.printf("Stage 10: Global ID Reassignment:       %.2f ms%n", (tReassignEnd - tReassignStart) / 1_000_000.0);
        System.out.printf("Total Core Processing Time:             %.2f ms%n", (tReassignEnd - tWCoordStart) / 1_000_000.0);
        System.out.printf("Total Batch Execution Time:             %.2f ms%n", (tTotalEnd - tTotalStart) / 1_000_000.0);
        System.out.println("=".repeat(50) + "\n");

        // Dump final results to file
        dumpBatchResults(trackingResults);
    }

    // ==================== INCREMENTAL MCPT BENCHMARK ====================

    /**
     * Runs incremental MCPT checkpoints for n=1..maxWindows to produce
     * real cumulative MCPT times per window count (no modelling needed).
     * 
     * After each checkpoint, outputs a line: MCPT_BENCHMARK n tracklets ms
     * so the figure generator can parse it directly.
     */
    private static void runIncrementalMcptBenchmark(
            Map<Integer, Map<String, Map<String, Object>>> fullResults,
            boolean replaceSimilarityByWCoordinate,
            int maxWindows) {

        int framePeriod = TrackingParameters.timePeriod * TrackingParameters.fps;
        logger.info("Running incremental MCPT benchmark for n=1..{} windows", maxWindows);

        System.out.println("\n" + "#".repeat(70));
        System.out.println("# INCREMENTAL MCPT BENCHMARK (cumulative per window count)");
        System.out.println("# Format: MCPT_BENCHMARK n tracklets cumulative_ms");
        System.out.println("#".repeat(70));

        for (int n = 1; n <= maxWindows; n++) {
            long tStart = System.nanoTime();

            // 1. Build subset: serials with Frame <= n * framePeriod
            int frameLimit = n * framePeriod;
            Map<Integer, Map<String, Map<String, Object>>> subset = new HashMap<>();
            int trackletCount = 0;
            for (Map.Entry<Integer, Map<String, Map<String, Object>>> camEntry : fullResults.entrySet()) {
                int cameraId = camEntry.getKey();
                Map<String, Map<String, Object>> camDict = camEntry.getValue();
                Map<String, Map<String, Object>> camSubset = new HashMap<>();
                for (Map.Entry<String, Map<String, Object>> serialEntry : camDict.entrySet()) {
                    int frame = (int) serialEntry.getValue().get("Frame");
                    if (frame <= frameLimit) {
                        camSubset.put(serialEntry.getKey(), serialEntry.getValue());
                    }
                }
                if (!camSubset.isEmpty()) {
                    subset.put(cameraId, camSubset);
                }
                // Count unique OfflineIDs for tracklet estimate
                Set<Integer> localIds = new HashSet<>();
                for (Map<String, Object> det : camSubset.values()) {
                    localIds.add((Integer) det.get("OfflineID"));
                }
                trackletCount += localIds.size();
            }

            // 2. Representative Selection
            Map<Integer, Map<Integer, MCPT.RepresentativeNode>> repNodes = MCPT.decideRepresentativeNodes(
                    subset,
                    TrackingParameters.representativeSelectionMethod,
                    TrackingParameters.epsilonMcpt,
                    TrackingParameters.shortTrackTh,
                    TrackingParameters.keypointTh,
                    new int[]{1920, 1080},
                    TrackingParameters.aspectTh,
                    2000
            );

            // 3. Matrix Gen (Raw)
            double[][] simMatrix = MCPT.createSimilarityMatrixMCPT(
                    repNodes,
                    TrackingParameters.shortTrackTh,
                    TrackingParameters.keypointConditionTh
            );

            // 4. Matrix Zeroing
            for (int i = 0; i < simMatrix.length; i++) {
                for (int j = 0; j < simMatrix[i].length; j++) {
                    if (simMatrix[i][j] < 1.0 - TrackingParameters.epsilonMcpt) {
                        simMatrix[i][j] = 0.0;
                    }
                }
            }

            // 5. Similarity Replace (World)
            List<Integer> clusters = new ArrayList<>();
            for (int i = 0; i < simMatrix.length; i++) {
                clusters.add(i);
            }
            simMatrix = MCPT.replaceSimilarity(
                    repNodes, simMatrix, subset, clusters,
                    false, replaceSimilarityByWCoordinate,
                    TrackingParameters.distanceType, TrackingParameters.distanceTh,
                    TrackingParameters.replaceValue,
                    TrackingParameters.shortTrackTh, TrackingParameters.keypointConditionTh
            );

            // 6. Clustering (HC)
            clusters = SCPT.associateCluster(
                    clusters, simMatrix,
                    TrackingParameters.epsilonMcpt, true, 2, false
            );

            long tEnd = System.nanoTime();
            double mcptTime = (tEnd - tStart) / 1_000_000.0;

            System.out.printf("MCPT_BENCHMARK %d %d %.2f%n", n, trackletCount, mcptTime);
        }

        System.out.println("#".repeat(70) + "\n");
        logger.info("Incremental MCPT benchmark complete");
    }

    // ==================== SCPT BATCH PHASE ====================

    /**
     * Runs SCPT (Single-Camera People Tracking) batch processing for each camera.
     * Mirrors Python's run_scpt() by processing detections through:
     * 1. Per-window clustering (trackingByClustering)
     * 2. Inter-window association (associateClusterBetweenPeriod)
     * 3. Post-processing (NMS, warp, short/motionless exclusion)
     * 4. Sequential OfflineID renumbering
     * 
     * After this, the trackingDict has proper per-camera tracklet IDs
     * instead of raw ground-truth OfflineIDs.
     */
    private static Map<Integer, Map<String, Map<String, Object>>> runScptBatch(
            Map<Integer, Map<String, Map<String, Object>>> trackingResults) {
        
        int framePeriod = TrackingParameters.timePeriod * TrackingParameters.fps; // e.g., 90
        int maxWindows = TrackingParameters.max_number_of_windows_to_process;
        
        for (int cameraId : trackingResults.keySet()) {
            Map<String, Map<String, Object>> trackingDict = trackingResults.get(cameraId);
            logger.info("[SCPT] Processing camera {} with {} detections", cameraId, trackingDict.size());
            
            // Step 1: Group serials by time window
            // Sort serials deterministically to match Python's insertion order
            List<String> sortedSerials = new ArrayList<>(trackingDict.keySet());
            Collections.sort(sortedSerials);
            Map<Integer, List<String>> windowSerials = new TreeMap<>();
            for (String serial : sortedSerials) {
                int frame = (int) trackingDict.get(serial).get("Frame");
                int windowIdx = (frame - 1) / framePeriod;
                if (windowIdx < maxWindows) {
                    windowSerials.computeIfAbsent(windowIdx, k -> new ArrayList<>()).add(serial);
                }
            }
            
            int maxOfflineId = -1;
            List<String> pastSerials = new ArrayList<>();
            List<double[]> pastFeatures = new ArrayList<>();
            List<Integer> pastClusters = new ArrayList<>();
            List<Integer> pastFrames = new ArrayList<>();
            
            // Step 2: Process each time window
            for (int w : windowSerials.keySet()) {
                List<String> serials = windowSerials.get(w);
                if (serials.isEmpty()) continue;
                
                // Build lists for this window
                List<double[]> featureList = new ArrayList<>();
                List<Integer> frameNumbers = new ArrayList<>();
                List<Integer> serialIndices = new ArrayList<>();
                List<Integer[]> boundingBoxList = new ArrayList<>();
                
                for (String serial : serials) {
                    Map<String, Object> data = trackingDict.get(serial);
                    featureList.add((double[]) data.get("Feature"));
                    int frame = (int) data.get("Frame");
                    frameNumbers.add(frame);
                    serialIndices.add(serialIndices.size()); // unique per-detection index
                    @SuppressWarnings("unchecked")
                    Map<String, Integer> coord = (Map<String, Integer>) data.get("Coordinate");
                    boundingBoxList.add(new Integer[]{coord.get("x1"), coord.get("x2"), coord.get("y1"), coord.get("y2")});
                }
                
                if (featureList.isEmpty()) continue;
                
                logger.info("[SCPT] Camera {} Window {}: {} detections", cameraId, w, featureList.size());
                
                // 2a. Intra-window clustering
                List<Integer> newClusterLabels;
                if (TrackingParameters.clustering_method.equalsIgnoreCase("clustream")) {
                    int numSerials = new HashSet<>(serialIndices).size();
                    newClusterLabels = SCPT.trackingByCluStream(featureList, numSerials);
                } else if (TrackingParameters.clustering_method.equalsIgnoreCase("clustree")) {
                    newClusterLabels = SCPT.trackingByClusTree(featureList);
                } else {
                    newClusterLabels = SCPT.trackingByClustering(featureList, frameNumbers, serialIndices,
                            boundingBoxList, w, String.valueOf(cameraId));
                }
                
                // 2b. Label shifting (same as Tracker.java)
                for (int i = 0; i < newClusterLabels.size(); i++) {
                    int c = newClusterLabels.get(i);
                    if (c != -1) {
                        newClusterLabels.set(i, c + maxOfflineId + 1);
                    } else {
                        newClusterLabels.set(i, -(i + 1));
                    }
                }
                
                // DEBUG DUMP: After trackingByClustering + label shifting (matches Tracker.java)
                if (TrackingParameters.isDebug) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-trackingByClustering");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_" + w + ".txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(newClusterLabels.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump after-trackingByClustering clusters", e);
                    }
                }
                
                // 2c. Inter-window association (skip first window)
                if (w > 0 && !pastFeatures.isEmpty()) {
                    // associateClusterBetweenPeriod now returns the FULL list
                    // [past_items_post_association..., current_items_post_association...]
                    List<Integer> fullAssociated = SCPT.associateClusterBetweenPeriod(
                            featureList, newClusterLabels, frameNumbers,
                            pastFeatures, pastClusters, pastFrames,
                            TrackingParameters.epsilonScpt);
                    
                    int pastSize = pastClusters.size();
                    
                    // Update PAST window items' OfflineIDs in trackingDict
                    for (int i = 0; i < pastSize; i++) {
                        trackingDict.get(pastSerials.get(i)).put("OfflineID", fullAssociated.get(i));
                    }
                    
                    // Extract current half for the rest of this iteration
                    List<Integer> currentHalf = new ArrayList<>();
                    for (int i = pastSize; i < fullAssociated.size(); i++) {
                        currentHalf.add(fullAssociated.get(i));
                    }
                    newClusterLabels = currentHalf;
                    
                    // Also update pastClusters for the next iteration (store current half as new past)
                    pastClusters = new ArrayList<>(currentHalf);
                }
                
                // DEBUG DUMP: After association (only for w > 0)
                // Dump only the CURRENT half (matching earlier format expectations)
                if (TrackingParameters.isDebug && w > 0) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-associateClusterBetweenPeriod");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_" + w + ".txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(newClusterLabels.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump after-association clusters", e);
                    }
                }
                
                // 2d. Update maxOfflineId after association
                for (int c : newClusterLabels) {
                    if (c > maxOfflineId) maxOfflineId = c;
                }
                
                // NOTE: Post-processing (NMS, warp, etc.) was moved OUT of the per-window loop.
                // It is now applied on combined data after all windows are processed,
                // matching Python's correcting_scpt_result() behavior.
                // See combined post-processing block below (after Step 2, before Step 3).
                
                // 2f. Update OfflineIDs in trackingDict for current window
                for (int i = 0; i < serials.size(); i++) {
                    trackingDict.get(serials.get(i)).put("OfflineID", newClusterLabels.get(i));
                }
                
                // 2g. Save state for next window
                pastSerials = new ArrayList<>(serials);
                pastFeatures = new ArrayList<>(featureList);
                pastFrames = new ArrayList<>(frameNumbers);
                // pastClusters was already updated above inside the association block
                // for w=0 we set it here
                if (w == 0) {
                    pastClusters = new ArrayList<>(newClusterLabels);
                }
            }
            
            // =======================================================
            // Combined Post-Processing (matching Python's correcting_scpt_result)
            // Applied on ALL windows' data combined, not per-window.
            // =======================================================
            
            // Collect ALL detections from trackingDict in sorted order by serial
            List<String> allSerials = new ArrayList<>(trackingDict.keySet());
            Collections.sort(allSerials);
            
            // Build combined lists for ClusteringUtils methods
            List<Integer> combinedClusters = new ArrayList<>();
            List<Integer> combinedFrames = new ArrayList<>();
            List<Integer[]> combinedBBoxes = new ArrayList<>();
            
            for (String serial : allSerials) {
                Map<String, Object> data = trackingDict.get(serial);
                combinedClusters.add((int) data.get("OfflineID"));
                combinedFrames.add((int) data.get("Frame"));
                @SuppressWarnings("unchecked")
                Map<String, Integer> coord = (Map<String, Integer>) data.get("Coordinate");
                combinedBBoxes.add(new Integer[]{coord.get("x1"), coord.get("x2"), coord.get("y1"), coord.get("y2")});
            }
            
            // DEBUG DUMP: Before NMS (combined input)
            if (TrackingParameters.isDebug) {
                try {
                    java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                            TrackingParameters.OUTPUT_DIR, "before-nms-combined");
                    java.nio.file.Files.createDirectories(dumpDir);
                    java.nio.file.Path filePath = dumpDir.resolve(
                            "clusters-java_" + cameraId + "_combined.txt");
                    try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                        writer.write(combinedClusters.toString());
                    }
                } catch (IOException e) {
                    logger.error("Failed to dump before-NMS combined clusters", e);
                }
            }
            
            // Apply combined NMS (if enabled)
            if (TrackingParameters.sequential_nms) {
                combinedClusters = ClusteringUtils.sequentialNonMaximumSuppression(
                        combinedClusters, combinedFrames, combinedBBoxes,
                        TrackingParameters.temporally_snms_th,
                        TrackingParameters.spatially_snms_th,
                        TrackingParameters.merge_nonoverlap);
                
                // DEBUG DUMP: After sequential NMS (combined)
                if (TrackingParameters.isDebug) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-sequential_nms");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_combined.txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(combinedClusters.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump combined after-NMS clusters", e);
                    }
                }
            }
            
            // Apply combined warp separation (if enabled)
            if (TrackingParameters.separate_warp) {
                combinedClusters = ClusteringUtils.separateWarpTracklet(
                        combinedClusters, combinedFrames, combinedBBoxes,
                        TrackingParameters.warp_th, TrackingParameters.alpha);
                
                // DEBUG DUMP: After separate warp (combined)
                if (TrackingParameters.isDebug) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-separate_warp");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_combined.txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(combinedClusters.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump combined after-warp clusters", e);
                    }
                }
            }
            
            // Apply combined short tracklet exclusion (if enabled)
            if (TrackingParameters.exclude_short) {
                combinedClusters = ClusteringUtils.excludeShortTracklet(
                        combinedClusters, TrackingParameters.short_tracklet_th);
                
                // DEBUG DUMP: After exclude short (combined)
                if (TrackingParameters.isDebug) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-exclude_short");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_combined.txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(combinedClusters.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump combined after-exclude-short clusters", e);
                    }
                }
            }
            
            // Apply combined motionless tracklet exclusion (if enabled)
            if (TrackingParameters.exclude_motionless) {
                combinedClusters = ClusteringUtils.excludeMotionlessTracklet(
                        combinedClusters, combinedFrames, combinedBBoxes,
                        TrackingParameters.stop_track_th);
                
                // DEBUG DUMP: After exclude motionless (combined)
                if (TrackingParameters.isDebug) {
                    try {
                        java.nio.file.Path dumpDir = java.nio.file.Paths.get(
                                TrackingParameters.OUTPUT_DIR, "after-exclude_motionless");
                        java.nio.file.Files.createDirectories(dumpDir);
                        java.nio.file.Path filePath = dumpDir.resolve(
                                "clusters-java_" + cameraId + "_combined.txt");
                        try (BufferedWriter writer = new BufferedWriter(new FileWriter(filePath.toFile()))) {
                            writer.write(combinedClusters.toString());
                        }
                    } catch (IOException e) {
                        logger.error("Failed to dump combined after-exclude-motionless clusters", e);
                    }
                }
            }
            
            // Write combined-processed labels back to trackingDict
            for (int i = 0; i < allSerials.size(); i++) {
                trackingDict.get(allSerials.get(i)).put("OfflineID", combinedClusters.get(i));
            }
            
            // Step 3: Renumber OfflineIDs sequentially (matching Python's correct_scpt_result)
            int newOfflineId = 0;
            Map<Integer, Integer> oldToNewMap = new HashMap<>();
            for (String serial : allSerials) {
                int oldId = (int) trackingDict.get(serial).get("OfflineID");
                if (oldId != -1) {
                    if (!oldToNewMap.containsKey(oldId)) {
                        oldToNewMap.put(oldId, newOfflineId++);
                    }
                    trackingDict.get(serial).put("OfflineID", oldToNewMap.get(oldId));
                } else {
                    trackingDict.get(serial).put("OfflineID", -1);
                }
            }
            
            logger.info("[SCPT] Camera {} done: {} tracklets across {} windows",
                    cameraId, oldToNewMap.size(), windowSerials.size());
        }
        
        return trackingResults;
    }

    private static void dumpBatchResults(Map<Integer, Map<String, Map<String, Object>>> trackingResults) {
        // Prepare clean results output similar to Python
        Map<Integer, Map<String, Map<String, Object>>> cleanResults = new HashMap<>();
        for (Map.Entry<Integer, Map<String, Map<String, Object>>> camEntry : trackingResults.entrySet()) {
            Map<String, Map<String, Object>> camData = new HashMap<>();
            for (Map.Entry<String, Map<String, Object>> serialEntry : camEntry.getValue().entrySet()) {
                Map<String, Object> trackletData = new HashMap<>(serialEntry.getValue());
                // Remove raw features and keypoints to keep file size reasonable
                trackletData.remove("Feature");
                trackletData.remove("Keypoints");
                camData.put(serialEntry.getKey(), trackletData);
            }
            cleanResults.put(camEntry.getKey(), camData);
        }

        try {
            Path outputFilePath = Paths.get(TrackingParameters.OUTPUT_DIR).resolve("batch_whole_tracking_results.json");
            Files.createDirectories(outputFilePath.getParent());
            Gson gson = new GsonBuilder().setPrettyPrinting().create();
            try (FileWriter writer = new FileWriter(outputFilePath.toFile())) {
                gson.toJson(cleanResults, writer);
            }
            logger.info("Dumped batch results to: " + outputFilePath.toAbsolutePath());
        } catch (Exception e) {
            logger.error("Failed to dump batch results: " + e.getMessage(), e);
        }
    }

    private static List<String> getCameraList() {
        List<String> cameras = new ArrayList<>();
        String filter = TrackingParameters.CAMERA_FILTER;

        if (filter.equalsIgnoreCase("all")) {
            cameras = discoverCamerasFromFeaturesDir();
            return cameras;
        }

        String[] parts = filter.split(",");
        for (String part : parts) {
            String token = part.trim();
            if (token.isEmpty())
                continue;

            if (token.matches("\\d+")) {
                int id = Integer.parseInt(token);
                cameras.add(String.format("camera_%04d", id));
            } else if (!token.startsWith("camera_")) {
                cameras.add("camera_" + token);
            } else {
                cameras.add(token);
            }
        }

        if (cameras.isEmpty()) {
            cameras = discoverCamerasFromFeaturesDir();
        }

        return cameras;
    }

    private static List<String> discoverCamerasFromFeaturesDir() {
        List<String> cameras = new ArrayList<>();
        String sceneDirName = String.format("scene_%03d", TrackingParameters.scene);
        Path scenePath = Paths.get(TrackingParameters.FEATURES_BASE_DIR, sceneDirName);

        if (!Files.isDirectory(scenePath)) {
            logger.error("Scene directory not found for dynamic camera discovery: " + scenePath);
            return cameras;
        }

        try (java.util.stream.Stream<Path> dirs = Files.list(scenePath)) {
            dirs.filter(Files::isDirectory)
                .map(p -> p.getFileName().toString())
                .filter(name -> name.startsWith("camera_"))
                .sorted()
                .forEach(cameras::add);
        } catch (Exception e) {
            logger.error("Error scanning features directory for cameras", e);
        }

        return cameras;
    }

    private static Map<Integer, double[][]> loadCalibrationData(List<String> cameras, int sceneId) {
        Map<Integer, double[][]> calibrationMap = new HashMap<>();
        Gson gson = new Gson();

        // 1. Try scene-level multi-camera calibration file first
        List<String> sceneLevelFiles = Arrays.asList(
                String.format("Original/scene_%03d/calibration.json", sceneId),
                String.format("Original/scene_%03d/calibration (1).json", sceneId));

        for (String fileName : sceneLevelFiles) {
            Path path = Paths.get(fileName);
            if (Files.exists(path)) {
                try (FileReader reader = new FileReader(path.toFile())) {
                    TypeToken<Map<String, Object>> typeToken = new TypeToken<>() {};
                    Map<String, Object> json = gson.fromJson(reader, typeToken.getType());

                    if (json.containsKey("sensors")) {
                        List<Map<String, Object>> sensors = (List<Map<String, Object>>) json.get("sensors");
                        for (Map<String, Object> sensor : sensors) {
                            String idStr = (String) sensor.get("id");
                            if (idStr != null && idStr.toLowerCase().startsWith("camera_")) {
                                int id = Integer.parseInt(idStr.toLowerCase().replace("camera_", ""));
                                String expectedCamName = String.format("camera_%04d", id);
                                if (cameras.contains(expectedCamName) && !calibrationMap.containsKey(id)) {
                                    Object homographyObj = sensor.get("homography");
                                    if (homographyObj == null)
                                        homographyObj = sensor.get("homography matrix");

                                    if (homographyObj != null) {
                                        double[][] matrix = parseHomographyMatrix(homographyObj, gson);
                                        if (matrix != null) {
                                            calibrationMap.put(id, matrix);
                                            logger.info("Loaded calibration for camera_" + id + " from " + fileName);
                                        }
                                    }
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    logger.error("Error parsing scene-level calibration " + fileName, e);
                }
            }
        }

        // 2. Fallback to camera-specific subdirectories
        for (String cameraName : cameras) {
            int id = Integer.parseInt(cameraName.replace("camera_", ""));
            if (calibrationMap.containsKey(id))
                continue;

            String calibrationPath = String.format("Original/scene_%03d/camera_%04d/calibration.json", sceneId, id);
            Path path = Paths.get(calibrationPath);

            if (Files.exists(path)) {
                try (FileReader reader = new FileReader(path.toFile())) {
                    TypeToken<Map<String, Object>> typeToken = new TypeToken<>() {};
                    Map<String, Object> calibrationJson = gson.fromJson(reader, typeToken.getType());

                    Object matrixObj = calibrationJson.get("homography matrix");
                    if (matrixObj == null)
                        matrixObj = calibrationJson.get("homography");

                    if (matrixObj != null) {
                        double[][] homographyMatrix = parseHomographyMatrix(matrixObj, gson);
                        if (homographyMatrix != null) {
                            calibrationMap.put(id, homographyMatrix);
                            logger.info("Loaded calibration for camera_" + id + " from subdirectory");
                        }
                    }
                } catch (Exception e) {
                    logger.error("Error loading calibration for camera " + id, e);
                }
            } else {
                logger.warn("Calibration file not found for camera_" + id + " at " + calibrationPath);
            }
        }

        return calibrationMap;
    }

    private static double[][] parseHomographyMatrix(Object matrixObj, Gson gson) {
        try {
            TypeToken<ArrayList<ArrayList<Double>>> typeToken = new TypeToken<>() {};
            String matrixJson = gson.toJson(matrixObj);
            ArrayList<ArrayList<Double>> homographyList = gson.fromJson(matrixJson, typeToken.getType());

            double[][] homographyMatrix = new double[3][3];
            for (int i = 0; i < 3; i++) {
                for (int j = 0; j < 3; j++) {
                    homographyMatrix[i][j] = homographyList.get(i).get(j);
                }
            }
            return homographyMatrix;
        } catch (Exception e) {
            logger.error("Failed to parse homography matrix", e);
            return null;
        }
    }

    private static Map<Integer, List<PoseData>> loadPoseData(Path cameraDir) {
        String cameraName = cameraDir.getFileName().toString();
        String sceneName = cameraDir.getParent().getFileName().toString();

        Path poseDir = Paths.get(TrackingParameters.FEATURES_BASE_DIR).getParent().resolve("Pose").resolve(sceneName).resolve(cameraName);
        
        // Discover pose file — the naming may differ from camera dir name
        // (e.g., camera_0101 dir may have camera_0001_out_keypoint.json)
        Path jsonFile = null;
        try (java.util.stream.Stream<Path> files = java.nio.file.Files.list(poseDir)) {
            jsonFile = files.filter(f -> f.getFileName().toString().endsWith("_out_keypoint.json"))
                    .findFirst().orElse(null);
        } catch (java.io.IOException e) {
            logger.warn("Could not list pose dir: " + poseDir);
            return new HashMap<>();
        }

        if (jsonFile == null || !Files.exists(jsonFile)) {
            logger.warn("Pose file not found in: " + poseDir);
            return new HashMap<>();
        }

        logger.info("Loading pose data from: " + jsonFile.getFileName());

        try (FileReader reader = new FileReader(jsonFile.toFile())) {
            Gson gson = new Gson();
            TypeToken<Map<String, List<PoseData>>> typeToken = new TypeToken<>() {};
            Map<String, List<PoseData>> rawData = gson.fromJson(reader, typeToken.getType());

            Map<Integer, List<PoseData>> frameData = new HashMap<>();
            for (Map.Entry<String, List<PoseData>> entry : rawData.entrySet()) {
                try {
                    int frame = Integer.parseInt(entry.getKey());
                    frameData.put(frame, entry.getValue());
                } catch (NumberFormatException e) {
                    // Ignore non-integer keys
                }
            }
            return frameData;
        } catch (Exception e) {
            logger.error("Error loading pose data for " + cameraDir, e);
            return new HashMap<>();
        }
    }

    private static List<List<Float>> getMatchingKeypoints(Map<Integer, List<PoseData>> poseCache, int frame, int x1, int y1, int x2, int y2) {
        if (poseCache == null)
            return null;

        List<PoseData> poses = poseCache.get(frame);
        if (poses == null)
            return null;

        for (PoseData pose : poses) {
            if (isBBoxMatch(pose.bbox, x1, y1, x2, y2)) {
                return pose.keypoints;
            }
        }
        return null;
    }

    private static boolean isBBoxMatch(List<Float> bbox, int x1, int y1, int x2, int y2) {
        if (bbox == null || bbox.size() < 4)
            return false;
        return Math.abs(bbox.get(0) - x1) <= 1.0 &&
                Math.abs(bbox.get(1) - y1) <= 1.0 &&
                Math.abs(bbox.get(2) - x2) <= 1.0 &&
                Math.abs(bbox.get(3) - y2) <= 1.0;
    }

    // ==================== MCPT DUMP HELPERS ====================

    private static void dumpMcptParams(Map<String, Object> params, String filename) {
        try {
            java.nio.file.Path dir = java.nio.file.Paths.get(TrackingParameters.OUTPUT_DIR, "mcpt-dumps");
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Path filePath = dir.resolve(filename + ".json");

            Gson gson = new GsonBuilder().setPrettyPrinting().create();
            try (java.io.FileWriter writer = new java.io.FileWriter(filePath.toFile())) {
                gson.toJson(params, writer);
            }
            logger.info("Dumped MCPT params to: " + filePath);
        } catch (java.io.IOException e) {
            logger.error("Failed to dump MCPT params: " + filename, e);
        }
    }

    private static void dumpMcptMatrix(double[][] matrix, String filename) {
        if (matrix == null || matrix.length == 0) {
            logger.warn("MCPT Matrix " + filename + " is empty or null!");
            return;
        } else {
            logger.info("Dumping MCPT Matrix " + filename + " with size " + matrix.length + "x" + matrix[0].length);
        }
        try {
            java.nio.file.Path dir = java.nio.file.Paths.get(TrackingParameters.OUTPUT_DIR, "mcpt-dumps");
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Path filePath = dir.resolve(filename + ".txt");

            try (java.io.BufferedWriter writer = new java.io.BufferedWriter(
                    new java.io.FileWriter(filePath.toFile()))) {
                for (double[] row : matrix) {
                    StringBuilder sb = new StringBuilder();
                    for (int j = 0; j < row.length; j++) {
                        sb.append(String.format("%.6f", row[j]));
                        if (j < row.length - 1)
                            sb.append(", ");
                    }
                    writer.write(sb.toString());
                    writer.newLine();
                }
            }
            logger.info("Dumped MCPT matrix to: " + filePath);
        } catch (java.io.IOException e) {
            logger.error("Failed to dump MCPT matrix: " + filename, e);
        }
    }

    private static void dumpMcptClusters(List<Integer> clusters, String filename) {
        if (clusters == null || clusters.isEmpty()) {
            logger.warn("MCPT Clusters " + filename + " is empty!");
            return;
        } else {
            logger.info("Dumping MCPT Clusters " + filename + " with size " + clusters.size());
        }
        try {
            java.nio.file.Path dir = java.nio.file.Paths.get(TrackingParameters.OUTPUT_DIR, "mcpt-dumps");
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Path filePath = dir.resolve(filename + ".txt");

            try (java.io.BufferedWriter writer = new java.io.BufferedWriter(
                    new java.io.FileWriter(filePath.toFile()))) {
                writer.write(clusters.toString());
            }
            logger.info("Dumped MCPT clusters to: " + filePath);
        } catch (java.io.IOException e) {
            logger.error("Failed to dump MCPT clusters: " + filename, e);
        }
    }

    private static void dumpMcptCameraDict(Map<Integer, MCPT.CameraDict> cameraDict, String filename) {
        if (cameraDict == null || cameraDict.isEmpty()) {
            logger.warn("MCPT Camera Dict " + filename + " is empty!");
            return;
        } else {
            logger.info("Dumping MCPT Camera Dict " + filename + " with " + cameraDict.size() + " cameras");
        }
        try {
            java.nio.file.Path dir = java.nio.file.Paths.get(TrackingParameters.OUTPUT_DIR, "mcpt-dumps");
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Path filePath = dir.resolve(filename + ".txt");

            try (java.io.BufferedWriter writer = new java.io.BufferedWriter(
                    new java.io.FileWriter(filePath.toFile()))) {
                // Sort cameras
                List<Integer> sortedCameras = new ArrayList<>(cameraDict.keySet());
                Collections.sort(sortedCameras);

                for (Integer cameraId : sortedCameras) {
                    MCPT.CameraDict dict = cameraDict.get(cameraId);
                    writer.write("Camera " + cameraId + ":");
                    writer.newLine();
                    writer.write("  indices: " + dict.indices);
                    writer.newLine();
                    writer.write("  uniqueLocalIds: " + dict.uniqueLocalIds);
                    writer.newLine();
                }
            }
            logger.info("Dumped MCPT camera dict to: " + filePath);
        } catch (java.io.IOException e) {
            logger.error("Failed to dump MCPT camera dict: " + filename, e);
        }
    }

    private static void dumpMcptGlobalIds(Map<Integer, Map<String, Map<String, Object>>> trackingResults,
            String filename) {
        if (trackingResults == null || trackingResults.isEmpty()) {
            logger.warn("MCPT Global IDs " + filename + " is empty!");
            return;
        } else {
            logger.info("Dumping MCPT Global IDs " + filename + " for " + trackingResults.size() + " cameras");
        }
        try {
            java.nio.file.Path dir = java.nio.file.Paths.get(TrackingParameters.OUTPUT_DIR, "mcpt-dumps");
            java.nio.file.Files.createDirectories(dir);
            java.nio.file.Path filePath = dir.resolve(filename + ".json");

            // Organize by frame number
            // Frame -> List of entries
            Map<Integer, List<Map<String, Object>>> frames = new TreeMap<>();

            for (Map.Entry<Integer, Map<String, Map<String, Object>>> camEntry : trackingResults.entrySet()) {
                Integer cameraId = camEntry.getKey();
                Map<String, Map<String, Object>> camData = camEntry.getValue();

                for (Map.Entry<String, Map<String, Object>> serialEntry : camData.entrySet()) {
                    String serial = serialEntry.getKey();
                    Map<String, Object> attrs = serialEntry.getValue();

                    Object globalIdObj = attrs.get("GlobalOfflineID");
                    Object localIdObj = attrs.get("OfflineID");
                    Object frameObj = attrs.get("Frame");
                    Object coordObj = attrs.get("Coordinate");

                    if (globalIdObj != null && frameObj instanceof Integer) {
                        Integer frameNum = (Integer) frameObj;

                        Map<String, Object> entry = new LinkedHashMap<>();
                        entry.put("camera", cameraId);
                        entry.put("serial", serial);
                        entry.put("localId", localIdObj);
                        entry.put("globalId", globalIdObj);
                        entry.put("bbox", coordObj); // Already a Map<String, Integer>

                        frames.computeIfAbsent(frameNum, k -> new ArrayList<>()).add(entry);
                    }
                }
            }

            // Sort entries within each frame by camera then globalId
            for (List<Map<String, Object>> entryList : frames.values()) {
                Collections.sort(entryList, (a, b) -> {
                    int camComp = ((Integer) a.get("camera")).compareTo((Integer) b.get("camera"));
                    if (camComp != 0)
                        return camComp;
                    return ((Integer) a.get("globalId")).compareTo((Integer) b.get("globalId"));
                });
            }

            Gson gson = new GsonBuilder().setPrettyPrinting().create();
            try (java.io.FileWriter writer = new java.io.FileWriter(filePath.toFile())) {
                gson.toJson(frames, writer);
            }
            logger.info("Dumped MCPT global IDs to: " + filePath);
        } catch (java.io.IOException e) {
            logger.error("Failed to dump MCPT global IDs: " + filename, e);
        }
    }
}
