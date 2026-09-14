package com.espertech.esper.example.IOT.streams;

/**
 * Event type for runtime reconfiguration of MCPT tracking parameters.
 * <p>
 * Sent during streaming to change behavioral parameters like {@code epsilonMcpt},
 * {@code simTh}, {@code distanceType}, etc. The EPL table {@code MCPTConfigTable}
 * receives these via MERGE upsert, and a reactive listener updates the
 * corresponding {@code TrackingParameters} static fields accordingly.
 * <p>
 * This follows the same architecture as {@link CameraTopology} for topology
 * reconfiguration: Event → EPL Table (MERGE upsert) → Reactive Listener → Action.
 */
public class MCPTConfigEvent {
    private String paramName;
    private String paramValue;
    private String paramType;  // "double", "int", "boolean", "string"

    public MCPTConfigEvent(String paramName, String paramValue, String paramType) {
        this.paramName = paramName;
        this.paramValue = paramValue;
        this.paramType = paramType;
    }

    public String getParamName() {
        return paramName;
    }

    public String getParamValue() {
        return paramValue;
    }

    public String getParamType() {
        return paramType;
    }
}
