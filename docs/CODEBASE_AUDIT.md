# AMBIENT Codebase Audit Report

**Date:** 2026-01-10
**Scope:** Full codebase audit excluding chirp-specific code
**Status:** Findings documented, patches pending
**Context:** Localhost-only dashboard for hardware interaction (not network-exposed)

---

## Executive Summary

This audit identified **90+ issues** across the AMBIENT codebase, focusing on code quality, maintainability, and reliability. Since the dashboard is designed for localhost-only use as a hardware interface, traditional web security concerns (authentication, CORS, rate limiting) are appropriately scoped and not considered issues.

The most significant problems are:
- **Test coverage gaps** for newly added modules (1,531 lines untested)
- **Code complexity** in core processing loops
- **Resource management** issues that could affect long-running sessions
- **Code duplication** reducing maintainability

### Severity Distribution

| Severity | Count | Categories |
|----------|-------|------------|
| **CRITICAL** | 3 | Test gaps, git hygiene, resource leaks |
| **HIGH** | 18 | Code complexity, input validation, error handling |
| **MEDIUM** | 40+ | Code duplication, inconsistencies, documentation |
| **LOW** | 30+ | Style issues, minor improvements |

---

## Table of Contents

1. [Input Validation & Robustness](#1-input-validation--robustness)
2. [Test Coverage Gaps](#2-test-coverage-gaps)
3. [Code Quality Issues](#3-code-quality-issues)
4. [API Layer Issues](#4-api-layer-issues)
5. [Frontend Issues](#5-frontend-issues)
6. [Project Structure Issues](#6-project-structure-issues)
7. [Actionable Items](#7-actionable-items)

---

## 1. Input Validation & Robustness

> **Context Note:** Since this is a localhost-only hardware dashboard, traditional web security concerns (authentication, CORS, rate limiting) are not applicable. The issues below focus on input validation for robustness and preventing accidental misuse.

### 1.1 MEDIUM: Path Input Validation

**Location:** `src/ambient/api/routes/config.py:376`
```python
target_path = config_dir / file.filename
```
**Issue:** Filename not sanitized - could accidentally create files with problematic names

**Location:** `src/ambient/api/routes/recordings.py:97, 118, 135`
```python
path = data_dir / f"{recording_id}.{ext}"
```
**Issue:** Recording ID not validated - malformed IDs could cause confusing errors

**Recommended Fix:** Add basic input sanitization for cleaner error handling:
```python
from pathlib import Path
import re

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for cleaner file operations."""
    name = Path(filename).name
    return re.sub(r'[^a-zA-Z0-9_.-]', '', name)
```

---

### 1.2 LOW: Test Module Name Validation

**Location:** `src/ambient/api/ws/tests.py:53-54`
```python
cmd.append(str(test_dir / f"{module}.py"))
```
**Location:** `src/ambient/api/routes/tests.py:51-54`

**Issue:** Module names not validated against available test files - typos give confusing errors

**Recommended Fix:** Validate module names against discovered test files for better UX

---

### 1.3 NOT AN ISSUE: Authentication/CORS/Rate Limiting

The following are **appropriately scoped** for a localhost hardware dashboard:
- No authentication required (local user has physical access to hardware)
- CORS configured for localhost only (correct)
- No rate limiting needed (single user, local access)
- Full config exposure is expected (user needs to see device state)

---

## 2. Test Coverage Gaps

### 2.1 CRITICAL: New Modules Without Tests

| Module | Lines | Test Status |
|--------|-------|-------------|
| `src/ambient/processing/fall_detection.py` | 506 | **NO TESTS** |
| `src/ambient/processing/point_cloud.py` | 329 | **NO TESTS** |
| `src/ambient/sensor/config_parser.py` | 696 | **NO TESTS** |
| **Total uncovered** | **1,531** | 0% coverage |

**Action Required:** Create test files:
- `tests/test_fall_detection.py`
- `tests/test_point_cloud.py`
- `tests/test_config_parser.py`

### 2.2 HIGH: Frontend Components Without Tests

| Component | Status |
|-----------|--------|
| `dashboard/src/components/charts/PointCloud3D.tsx` | No tests |
| `dashboard/src/components/charts/RangeDopplerEnhanced.tsx` | No tests |
| `dashboard/src/components/charts/QualityMetricsDashboard.tsx` | No tests |
| All React components | No test framework configured |

**Action Required:**
- Set up Vitest or Jest for frontend testing
- Add component tests for critical visualizations

---

## 3. Code Quality Issues

### 3.1 Code Duplication

#### HIGH: TLV Parsing Duplication
**Locations:**
- `src/ambient/sensor/frame.py:1098-1176` (RadarFrame.from_bytes)
- `src/ambient/sensor/frame.py:1237-1305` (FrameBuffer._parse_frame)

**Issue:** Nearly identical TLV parsing logic with 11 elif branches duplicated

**Fix:** Extract to shared `parse_tlv()` function

#### MEDIUM: Configuration Loading Pattern
**Location:** `src/ambient/config.py:239-272`
```python
# Repeated 7 times:
if "sensor" in data:
    for key, value in data["sensor"].items():
        if hasattr(config.sensor, key):
            setattr(config.sensor, key, value)
```

**Fix:** Create helper function for config section loading

#### MEDIUM: Chart Cursor Handling (Frontend)
**Locations:**
- `RangeProfile.tsx:45-56`
- `VitalsChart.tsx:33-45`
- `PhaseSignal.tsx:24-35`
- `QualityMetricsChart.tsx:39-59`

**Fix:** Extract to `useChartCursor()` custom hook

---

### 3.2 Overly Complex Functions

| Function | File | Lines | Issue |
|----------|------|-------|-------|
| `acquisition_loop()` | `api/tasks.py:272-465` | ~200 | Too many responsibilities |
| `connect()` | `api/state.py:178-288` | ~110 | Deeply nested, mixes concerns |
| `RadarFrame.from_bytes()` | `sensor/frame.py` | ~80 | 11 elif branches |
| `_parse_frame()` | `sensor/frame.py` | ~70 | Duplicates from_bytes() |

**Fix:** Break into smaller, single-responsibility functions

---

### 3.3 Hardcoded Magic Numbers

| Value | Locations | Should Be |
|-------|-----------|-----------|
| `0.044` (range res) | `processing/pipeline.py:106, 117` | Config constant |
| `65536` (buffer size) | `sensor/frame.py:1182` | Config parameter |
| `200` (max frames) | `stores/appStore.ts:88` | Config constant |
| `15` (point cloud age) | `stores/appStore.ts:148` | Config parameter |
| `5` seconds | `vitals/extractor.py:149, 313` | Named constant |
| `/dev/ttyUSB0/1` | Multiple files | Environment variable |

---

### 3.4 Missing Type Hints

| Location | Issue |
|----------|-------|
| `api/tasks.py:148` | `frame` parameter untyped |
| `api/tasks.py:203` | `vitals` parameter untyped |
| `sensor/frame.py:56` | Returns `list` not `list[DetectedPoint]` |
| `processing/pipeline.py:102` | Could be more specific |

---

### 3.5 Missing Error Handling

| Location | Issue |
|----------|-------|
| `sensor/frame.py:59` | No validation data length divisible by point_size |
| `processing/pipeline.py:102-108` | No check if peaks array empty |
| `vitals/heart_rate.py:136-139` | No bounds check on peak_idx |
| `api/tasks.py:313-315` | Silent continue on None frame |
| `vitals/heart_rate.py:209-213` | Harmonic indices can exceed array bounds |

---

## 4. API Layer Issues

### 4.1 Inconsistent Response Patterns

| Pattern | Example Locations | Issue |
|---------|-------------------|-------|
| Status wrapping | `config.py:201` vs `device.py:219` | Some wrap in `{status}`, some don't |
| Error details | `config.py:109` vs `device.py:99` | Inconsistent error message format |
| Deletion responses | `config.py:138` vs `recordings.py:112` | Different key names |

**Recommended Fix:** Create standardized response helper:
```python
def success_response(data: Any = None, message: str | None = None) -> dict:
    return {"success": True, "data": data, "message": message}

def error_response(message: str, details: Any = None) -> dict:
    return {"success": False, "error": message, "details": details}
```

---

### 4.2 Resource Leaks

| Location | Issue | Severity |
|----------|-------|----------|
| `routes/recordings.py:163, 172` | NamedTemporaryFile not cleaned up | HIGH |
| `routes/device.py:44-67` | Serial port not closed on exception | MEDIUM |
| `state.py:297-301` | Task cancellation not fully awaited | LOW |

**Note:** These are reliability issues for long-running sessions, not security concerns.

---

### 4.3 Input Validation for Better UX

| Endpoint | Parameter | Issue |
|----------|-----------|-------|
| `POST /ti-configs/upload` | filename | Only checks extension - unclear errors on bad names |
| `POST /recordings/start` | name | No validation - could create confusing file names |
| `PUT /streaming` | all params | No bounds checking - could set unreasonable values |

**Note:** These are UX improvements, not security issues. Invalid inputs should give clear error messages.

---

## 5. Frontend Issues

### 5.1 Dead/Unused Code

| File | Issue |
|------|-------|
| `RangeDopplerEnhanced.tsx` | Created but never imported/used |
| `PointCloud3D.tsx:348-368` | `ColorModeSelector` export unused |
| `RangeDopplerEnhanced.tsx:343-364` | `ColormapSelector` export unused |

---

### 5.2 Error Handling Gaps (UX Issues)

| Location | Issue | Impact |
|----------|-------|--------|
| `DeviceStatus.tsx:28, 42` | `.catch(() => {})` - silent failures | User doesn't know why action failed |
| `ConfigManager.tsx:218, 250, 263, 273` | Empty catch blocks | Config changes may fail silently |
| `AlgorithmTuning.tsx:24, 40, 58` | Errors silently ignored | Parameter updates may not apply |
| `Recordings.tsx:23, 41, 54, 65` | No user feedback on errors | Recording state unclear |
| `websocket.ts:29-60` | WebSocket errors silently swallowed | Connection issues not apparent |

**Impact:** Users won't understand why operations fail, leading to confusion during hardware debugging sessions.

---

### 5.3 Accessibility Issues

| Issue | Locations |
|-------|-----------|
| Missing ARIA labels | Buttons in Layout.tsx, Sidebar.tsx |
| No form labels | Search input in Logs.tsx |
| Chart accessibility | All uPlot charts lack ARIA |
| Color contrast | Small text in StatusIndicator.tsx |
| Missing alt text | All inline SVG icons |

---

### 5.4 Performance Issues

| Issue | Location |
|-------|----------|
| Missing memoization | `ConfigManager.tsx:241`, `SignalViewer.tsx:82-86` |
| Unnecessary re-renders | `Logs.tsx:71-84`, uPlot chart recreation |
| Multiple store selectors | `useWebSocket.ts:17-24` |

---

## 6. Project Structure Issues

### 6.1 Git Hygiene

**CRITICAL: Large files not gitignored**
```
?? manual.pdf (1.2M)
?? swru546e.pdf (7.2M)
```
**Risk:** Will be committed on `git add .`

**Fix:** Add to `.gitignore`:
```
*.pdf
.coverage
```

**Uncommitted Changes:** 16 modified files, 6 new untracked source files

---

### 6.2 Documentation Gaps

| Missing Documentation |
|-----------------------|
| Fall detection module - algorithm, configuration, usage |
| Point cloud module - accumulation, visualization |
| Config parser - supported commands, integration |
| README updates for new features |
| API documentation for new endpoints |

---

### 6.3 Configuration Issues

| Issue | Details |
|-------|---------|
| Modified configs uncommitted | `vital_signs_chirp.cfg`, `working.cfg` |
| Empty profiles.json | Only 2 bytes |
| Inconsistent naming | `basic.cfg` vs `vital_signs.cfg` vs `working.cfg` |

---

## 7. Actionable Items

### CRITICAL Priority (Fix Immediately)

| # | Item | Location | Reason |
|---|------|----------|--------|
| 1 | Add `*.pdf` to .gitignore | `.gitignore` | Prevent 8.4MB of PDFs being committed |
| 2 | Create tests for fall_detection.py | `tests/test_fall_detection.py` | 506 lines untested |
| 3 | Create tests for point_cloud.py | `tests/test_point_cloud.py` | 329 lines untested |
| 4 | Create tests for config_parser.py | `tests/test_config_parser.py` | 696 lines untested |
| 5 | Fix temporary file cleanup | `routes/recordings.py:163` | Files accumulate in /tmp |

### HIGH Priority (Fix Before Release)

| # | Item | Location | Reason |
|---|------|----------|--------|
| 6 | Refactor `acquisition_loop()` | `api/tasks.py` | ~200 lines, too complex |
| 7 | Eliminate TLV parsing duplication | `sensor/frame.py` | Same logic in 2 places |
| 8 | Add error feedback to frontend | All pages | Silent failures confuse users |
| 9 | Add bounds checking to vital signs | `heart_rate.py:209` | Harmonic index overflow |
| 10 | Fix serial port resource leak | `routes/device.py` | Port left open on exception |
| 11 | Commit or stash modified files | Git working tree | 16 files in limbo |

### MEDIUM Priority (Address Soon)

| # | Item | Location | Reason |
|---|------|----------|--------|
| 12 | Extract hardcoded values to config | Multiple files | Magic numbers scattered |
| 13 | Add missing type hints | `api/tasks.py`, `sensor/frame.py` | Type safety |
| 14 | Create frontend constants file | `dashboard/src/config/constants.ts` | Centralize config |
| 15 | Document new modules | `docs/` | No docs for 3 new features |
| 16 | Standardize API response format | All API routes | Inconsistent patterns |
| 17 | Add memoization to components | `ConfigManager.tsx`, etc. | Performance |
| 18 | Extract chart cursor hook | Dashboard charts | Code duplication |
| 19 | Add input sanitization | `routes/config.py`, `routes/recordings.py` | Cleaner error handling |

### LOW Priority (Nice to Have)

| # | Item | Location | Reason |
|---|------|----------|--------|
| 20 | Integrate or remove RangeDopplerEnhanced | `RangeDopplerEnhanced.tsx` | Unused component |
| 21 | Consolidate config loading pattern | `config.py` | Repeated code block |
| 22 | Add ARIA labels | Dashboard components | Accessibility |
| 23 | Add pre-commit pytest/mypy | `.pre-commit-config.yaml` | Catch issues early |
| 24 | Add frontend test framework | `dashboard/` | No React tests |
| 25 | Pin npm dependency versions | `package.json` | Reproducible builds |

---

## Appendix: Files Requiring Attention

### Files with Most Issues
1. `src/ambient/api/tasks.py` - Complexity, types, refactoring needed
2. `src/ambient/sensor/frame.py` - Duplication, error handling
3. `src/ambient/api/routes/config.py` - Security, validation
4. `src/ambient/api/routes/recordings.py` - Security, resource leaks
5. `dashboard/src/pages/DeviceStatus.tsx` - Error handling

### New Files Needing Tests
- `src/ambient/processing/fall_detection.py` (506 lines)
- `src/ambient/processing/point_cloud.py` (329 lines)
- `src/ambient/sensor/config_parser.py` (696 lines)

### New Files Needing Documentation
- Fall detection algorithm and configuration
- Point cloud accumulation and visualization
- TI config parser usage and integration
