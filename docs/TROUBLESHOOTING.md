# Troubleshooting Guide

Common issues and solutions for the Ambient radar SDK.

## Connection Issues

### Device Not Detected

**Symptoms:** Ports not showing up in `/dev/ttyUSB*` or `/dev/ttyACM*`

**Solutions:**
1. Check USB cable connection
2. Verify device power (LED should be lit)
3. Check kernel module: `lsmod | grep cdc_acm`
4. Add udev rules for TI devices:
   ```bash
   sudo cp configs/99-ti-radar.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### Permission Denied on Serial Port

**Symptoms:** `PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'`

**Solutions:**
1. Add user to dialout group: `sudo usermod -a -G dialout $USER`
2. Log out and back in for group changes to take effect
3. Or temporarily: `sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1`

### Connection Timeout

**Symptoms:** `TimeoutError` during connect or configuration

**Solutions:**
1. Verify correct port assignments (CLI vs Data port)
2. Use the port verification endpoint: `GET /api/device/verify-ports`
3. Check baud rate matches device (CLI: 115200, Data: 921600)
4. Reset device by power cycling

### Wrong Port Assignment

**Symptoms:** Data appears garbled or no response to commands

**Solutions:**
1. Swap CLI and Data port assignments
2. Run port verification in dashboard
3. Check device documentation for correct port mapping

### Flash Mode vs Run Mode

**Symptoms:** Ports appear but CLI is unresponsive, or only XDS110 shows up

**Quick checks:**
1. **Flash mode (SOP = 0b011)** enumerates as XDS110 and typically won't respond to `version`
2. **Run mode (SOP = 0b000)** shows two serial ports and responds to `version`
3. If `version` responds but `chirp status` is unknown, the firmware is running but not chirp-enabled

**Fixes:**
1. Power cycle and set SOP jumpers for the desired mode
2. Reflash firmware if the device is in run mode but responds with unexpected CLI output

### Single Port Enumeration

**Symptoms:** Only one serial port appears instead of two (CLI + Data)

**Common causes:**
1. Some host systems enumerate the IWR6843AOPEVM as a single composite device
2. USB hub or cable may limit the number of virtual serial ports

**Workarounds:**
1. Use `ambient status` to verify CLI port responsiveness (data port optional)
2. Try a direct USB connection (no hub)
3. For streaming data, both ports are required; the data port handles high-speed frame output

## Streaming Issues

### No Data After Connection

**Symptoms:** Connected but no frames received

**Solutions:**
1. Verify device is configured: `GET /api/device/status`
2. Check if sensor is streaming: look for `state: "streaming"`
3. Verify chirp/firmware mode configuration
4. Check for errors in logs: `GET /api/logs/stream` via WebSocket

### Low Frame Rate

**Symptoms:** Frame rate significantly below expected (e.g., <10 Hz when expecting 20 Hz)

**Solutions:**
1. Check performance metrics: `GET /api/device/metrics`
2. Look for high processing latency (p95 > 50ms)
3. Reduce data payloads: disable range_doppler in streaming config
4. Check CPU usage on host machine

### Dropped Frames

**Symptoms:** `dropped_frames` counter increasing

**Causes & Solutions:**
1. **Processing backlog:**
   - Check queue depth in metrics
   - Reduce frame processing complexity
   - Increase `AMBIENT_STREAM_MAX_QUEUE`

2. **WebSocket backpressure:**
   - Check `websocket.messages_dropped` in metrics
   - Reduce payload size: set `include_range_doppler: false`
   - Reduce connected clients

3. **Serial buffer overflow:**
   - Increase system serial buffer: `setserial /dev/ttyUSB1 low_latency`

## Performance Issues

### High Latency

**Symptoms:** Processing latency p99 > 50ms, visible lag in dashboard

**Diagnosis:**
```bash
# Enable performance profiling
export AMBIENT_PERF_ENABLED=true
export AMBIENT_PERF_LOG_INTERVAL=100

# Check metrics endpoint
curl http://localhost:8000/api/device/metrics | jq '.timing'
```

**Solutions:**
1. Identify slow stage (pipeline, vitals, broadcast)
2. Reduce range_doppler matrix size: `AMBIENT_STREAM_MAX_HEATMAP=32`
3. Reduce waveform samples: `AMBIENT_STREAM_MAX_WAVEFORM=100`
4. Use batching for WebSocket broadcasts

### Memory Growth

**Symptoms:** Process memory increasing over time

**Solutions:**
1. Check recording state - stop if not needed
2. Limit profiler sample buffer (1000 samples max)
3. Check for WebSocket connection leaks
4. Restart API server periodically if needed

### Queue Buildup

**Symptoms:** Queue depth increasing, approaching max

**Solutions:**
1. Check drop policy: `AMBIENT_STREAM_DROP_POLICY=oldest` (recommended)
2. Reduce incoming data rate if possible
3. Increase queue size for burst handling: `AMBIENT_STREAM_MAX_QUEUE=200`
4. Verify consumers are processing messages

## Recording Issues

### Recording Won't Start

**Symptoms:** `POST /api/recordings/start` fails

**Solutions:**
1. Check disk space: `df -h`
2. Verify data directory permissions
3. Ensure device is streaming first
4. Check for existing recording in progress

### Corrupt Recording File

**Symptoms:** Cannot open HDF5/Parquet file, validation fails

**Solutions:**
1. Run validation script:
   ```bash
   python scripts/validate_recording.py data/recording.h5 --verbose
   ```
2. Check for incomplete writes (power loss during recording)
3. Verify schema version compatibility

### Large Recording Files

**Solutions:**
1. Use Parquet for vitals-only recording (smaller, faster)
2. Disable raw data storage if not needed
3. Use compression: HDF5 uses gzip by default

## Dashboard Issues

### WebSocket Disconnects

**Symptoms:** Dashboard shows disconnected, data stops updating

**Solutions:**
1. Check browser console for errors
2. Verify API server is running: `curl http://localhost:8000/api/device/status`
3. Check for CORS issues if running on different port
4. Increase WebSocket timeout in client

### Charts Not Updating

**Symptoms:** Data is stale, charts frozen

**Solutions:**
1. Check WebSocket connection status in dashboard
2. Verify `include_waveforms` is enabled in streaming config
3. Check for JavaScript errors in browser console

### Missing Vital Signs

**Symptoms:** Heart rate or respiratory rate shows null/NaN

**Causes:**
1. **Motion detected:** Movement invalidates vital signs extraction
2. **Low signal quality:** Check `signal_quality` metric
3. **Insufficient data:** Need ~10 seconds of stable data
4. **Out of range:** Subject may be too close or too far

## API Issues

### Config Validation Fails

**Symptoms:** `GET /api/config/validate` returns errors

**Solutions:**
1. Check the specific validation errors returned
2. Common issues:
   - `drop_policy` must be "oldest", "newest", or "none"
   - `max_queue_size` must be 1-10000
   - `vitals_interval_hz` must be 0.1-10.0

### Endpoint Returns 500

**Symptoms:** Internal server error on API calls

**Solutions:**
1. Check API server logs for stack trace
2. Common causes:
   - Device not connected but operation requires it
   - Configuration file parsing error
   - Serial port access issue

## Environment Variables Reference

Quick reference for troubleshooting-related env vars:

```bash
# Serial ports
AMBIENT_CLI_PORT=/dev/ttyUSB0
AMBIENT_DATA_PORT=/dev/ttyUSB1

# Performance profiling
AMBIENT_PERF_ENABLED=true
AMBIENT_PERF_LOG_INTERVAL=100

# Streaming config
AMBIENT_STREAM_MAX_QUEUE=100
AMBIENT_STREAM_DROP_POLICY=oldest
AMBIENT_STREAM_MAX_HEATMAP=64
AMBIENT_STREAM_MAX_WAVEFORM=200

# Chirp mode
AMBIENT_CHIRP_ENABLED=true
AMBIENT_CHIRP_RANGE_MIN=0.2
AMBIENT_CHIRP_RANGE_MAX=5.0

# Logging
AMBIENT_LOG_LEVEL=DEBUG
```

## Getting Help

1. Check API documentation: `docs/API_REFERENCE.md`
2. Review integration guide: `docs/INTEGRATION_GUIDE.md`
3. Enable debug logging: `AMBIENT_LOG_LEVEL=DEBUG`
4. Run built-in tests: `pytest tests/ -v`
5. Use the load testing tools to reproduce issues:
   ```bash
   python scripts/simulate_frames.py --profile stress
   ```
