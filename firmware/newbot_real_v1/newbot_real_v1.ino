/*
 * NewBot real firmware v1 skeleton.
 * - Patch 4A: config-driven actuator abstraction (ESP32-S3 + 2x TMC2208 + servo placeholders).
 * - Default: motor outputs disabled, pins unassigned, no real motion on wire.
 * - SERIAL_PROTOCOL_V1 profile B: BEGIN / commands / END queue.
 * - STOP and ERR paths use central hardStop() + actuatorHardStop().
 */

#include <Arduino.h>

#include "actuator_safe.h"
#include "robot_config.h"
#include "robot_state_machine.h"
#include "serial_protocol_v1.h"

static const unsigned long SERIAL_BAUD = 115200;
static const size_t MAX_LINE = 160;
static const size_t MAX_BATCH_CMDS = 256;
static const unsigned long HOST_ACTIVITY_TIMEOUT_MS = 5000;

struct QueuedLine {
  ProtoLineType type;
  float x;
  float y;
  float f1;
  bool penDown;
};

static String g_lineBuf;
static bool g_lineOverflow = false;
static uint32_t g_lastHostActivityMs = 0;
static bool g_hostTimeoutTripped = false;

static QueuedLine g_queue[MAX_BATCH_CMDS];
static size_t g_queueCount = 0;
static size_t g_queueIndex = 0;
static bool g_batchReceiving = false;
static bool g_queueRunning = false;
static bool g_queueWaitingForMotion = false;

static ActuatorSafe g_act;
static RobotStateMachine g_rsm(&g_act);

static char g_actuatorStatusBuf[128];

static void writeStatusLine() {
  actuatorFormatStatusFields(g_actuatorStatusBuf, sizeof(g_actuatorStatusBuf));
  serial_protocol_v1_write_status_ex(g_rsm.stateToken(),
                                     g_rsm.lastErrorToken(),
                                     queuedForStatus(),
                                     g_actuatorStatusBuf);
}

static void resetQueue() {
  g_queueCount = 0;
  g_queueIndex = 0;
  g_queueRunning = false;
  g_queueWaitingForMotion = false;
}

static uint16_t queuedForStatus() {
  uint16_t active = g_rsm.queued();
  if (g_batchReceiving) {
    size_t total = g_queueCount + active;
    return total > 65535u ? 65535u : (uint16_t)total;
  }
  if (!g_queueRunning) return active;
  size_t pending = (g_queueIndex < g_queueCount) ? (g_queueCount - g_queueIndex) : 0;
  size_t total = pending + active;
  return total > 65535u ? 65535u : (uint16_t)total;
}

static void failWithErr(uint32_t nowMs, const char* reason) {
  resetQueue();
  g_batchReceiving = false;
  g_rsm.hardStop(nowMs, reason ? reason : "error");
  serial_protocol_v1_write_err(reason ? reason : "error");
}

static bool enqueueParsedLine(const ProtoParsedLine& pl, uint32_t nowMs) {
  if (g_queueCount >= MAX_BATCH_CMDS) {
    failWithErr(nowMs, "queue_full");
    return false;
  }

  QueuedLine q{};
  q.type = pl.type;
  q.x = pl.x;
  q.y = pl.y;
  q.f1 = pl.f1;
  q.penDown = pl.penDown;
  g_queue[g_queueCount++] = q;
  return true;
}

static bool startMotionForQueuedLine(const QueuedLine& q, uint32_t nowMs) {
  switch (q.type) {
    case TL_HOME:
      return g_rsm.onHome(nowMs);
    case TL_MOVE:
      return g_rsm.onMove(nowMs, q.x, q.y);
    case TL_FORWARD:
      return g_rsm.onMove(nowMs, q.f1, 0.0f);
    case TL_TURN:
      return g_rsm.onMove(nowMs, q.f1, 0.0f);
    case TL_WAIT:
      return g_rsm.onMove(nowMs, q.f1, 0.0f);
    default:
      return false;
  }
}

static void continueQueuedExecution(uint32_t nowMs) {
  while (g_queueRunning && !g_queueWaitingForMotion) {
    if (g_queueIndex >= g_queueCount) {
      resetQueue();
      g_rsm.setError("none");
      serial_protocol_v1_write_done();
      return;
    }

    const QueuedLine& q = g_queue[g_queueIndex];
    switch (q.type) {
      case TL_SPEED:
        actuatorSetStepRateHz((uint32_t)q.f1);
        g_rsm.setError("none");
        g_queueIndex++;
        break;

      case TL_PEN:
        g_act.setPenDown(q.penDown);
        g_rsm.setError("none");
        g_queueIndex++;
        break;

      case TL_HOME:
      case TL_MOVE:
      case TL_FORWARD:
      case TL_TURN:
      case TL_WAIT:
        if (!startMotionForQueuedLine(q, nowMs)) {
          failWithErr(nowMs, g_rsm.lastErrorToken());
          return;
        }
        g_queueWaitingForMotion = true;
        return;

      default:
        failWithErr(nowMs, "invalid_queued_command");
        return;
    }
  }
}

static void startQueuedExecution(uint32_t nowMs) {
  g_batchReceiving = false;
  g_queueIndex = 0;
  g_queueWaitingForMotion = false;

  if (g_queueCount == 0) {
    resetQueue();
    serial_protocol_v1_write_done();
    return;
  }

  g_queueRunning = true;
  continueQueuedExecution(nowMs);
}

static bool executeSingleParsedLine(const ProtoParsedLine& pl, uint32_t nowMs) {
  switch (pl.type) {
    case TL_HOME:
      return g_rsm.onHome(nowMs);
    case TL_MOVE:
      return g_rsm.onMove(nowMs, pl.x, pl.y);
    case TL_FORWARD:
      return g_rsm.onMove(nowMs, pl.f1, 0.0f);
    case TL_TURN:
      return g_rsm.onMove(nowMs, pl.f1, 0.0f);
    case TL_WAIT:
      return g_rsm.onMove(nowMs, pl.f1, 0.0f);
    default:
      return false;
  }
}

static void handleStop(uint32_t nowMs) {
  resetQueue();
  g_batchReceiving = false;
  g_rsm.onStop(nowMs);
  serial_protocol_v1_write_done();
}

static void processLine(const String& line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;
  if (s.charAt(0) == '#') return;

  uint32_t nowMs = millis();
  g_lastHostActivityMs = nowMs;
  g_hostTimeoutTripped = false;

  ProtoParsedLine pl;
  const char* errReason = nullptr;
  bool ok = parse_serial_protocol_v1_line(s, pl, errReason);
  if (!ok) {
    failWithErr(nowMs, errReason ? errReason : "parse");
    return;
  }

  if (pl.type == TL_STOP) {
    handleStop(nowMs);
    return;
  }

  switch (pl.type) {
    case TL_NONE:
      return;

    case TL_STATUS:
      writeStatusLine();
      return;

    case TL_BEGIN:
      if (g_queueRunning || g_rsm.state() == RS_BUSY) {
        failWithErr(nowMs, "busy");
        return;
      }
      resetQueue();
      g_batchReceiving = true;
      g_rsm.setError("none");
      Serial.println("OK");
      return;

    case TL_END:
      if (!g_batchReceiving) {
        failWithErr(nowMs, "end_without_begin");
        return;
      }
      startQueuedExecution(nowMs);
      return;

    case TL_SPEED:
    case TL_PEN:
    case TL_HOME:
    case TL_MOVE:
    case TL_FORWARD:
    case TL_TURN:
    case TL_WAIT:
      if (g_batchReceiving) {
        enqueueParsedLine(pl, nowMs);
        return;
      }
      if (g_queueRunning) {
        failWithErr(nowMs, "busy");
        return;
      }
      if (pl.type == TL_SPEED) {
        actuatorSetStepRateHz((uint32_t)pl.f1);
        g_rsm.setError("none");
        return;
      }
      if (pl.type == TL_PEN) {
        g_act.setPenDown(pl.penDown);
        g_rsm.setError("none");
        return;
      }
      if (!executeSingleParsedLine(pl, nowMs)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    default:
      failWithErr(nowMs, "bilinmeyen");
      return;
  }
}

static void feedSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (g_lineOverflow) {
        failWithErr(millis(), "line_too_long");
        g_lineOverflow = false;
        g_lineBuf = "";
        continue;
      }
      processLine(g_lineBuf);
      g_lineBuf = "";
      continue;
    }
    if (g_lineBuf.length() < (int)MAX_LINE - 1) {
      g_lineBuf += c;
    } else {
      g_lineOverflow = true;
    }
  }
}

static void enforceHostActivityTimeout(uint32_t nowMs) {
  if (HOST_ACTIVITY_TIMEOUT_MS == 0 || g_hostTimeoutTripped) return;
  bool activitySensitive = g_batchReceiving || g_queueRunning || g_rsm.state() == RS_BUSY ||
                           g_rsm.queued() > 0;
  if (!activitySensitive) return;
  if ((uint32_t)(nowMs - g_lastHostActivityMs) < HOST_ACTIVITY_TIMEOUT_MS) return;

  failWithErr(nowMs, "host_timeout");
  g_hostTimeoutTripped = true;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  g_lineBuf.reserve(MAX_LINE);
  actuatorInit();
  g_rsm.begin();
  resetQueue();
  g_batchReceiving = false;
  g_lastHostActivityMs = millis();
  (void)BOARD_TARGET_NOTE;
}

void loop() {
  feedSerial();

  uint32_t nowMs = millis();
  enforceHostActivityTimeout(nowMs);

  bool motionDone = g_rsm.tick(nowMs);
  if (motionDone) {
    if (g_queueRunning) {
      g_queueWaitingForMotion = false;
      g_queueIndex++;
      continueQueuedExecution(nowMs);
    } else {
      serial_protocol_v1_write_done();
    }
  }
}
