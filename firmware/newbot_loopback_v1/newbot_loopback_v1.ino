/*
 * NewBot loopback v1 — SERIAL_PROTOCOL_V1 profil B (BEGIN/END), motor yok.
 * Host: serialize_commands + frame_dsl_payload (profil B) bekler; yanıt DONE/ERR.
 *
 * Dahili durum (simülasyon): son hız, kalem, son işlenen komut tipi — gerçek motor yok.
 * Tek satır host sorgusu: STATUS -> MCU STATUS ... (parse_response_line ile uyumlu).
 */

#include <Arduino.h>

static const unsigned long SERIAL_BAUD = 115200;
static const size_t MAX_CMDS = 256;
static const size_t MAX_LINE = 160;

enum CmdType : uint8_t {
  CMD_NONE = 0,
  CMD_SPEED,
  CMD_MOVE,
  CMD_MOVE_REL,
  CMD_TURN,
  CMD_FORWARD,
  CMD_WAIT,
  CMD_PEN,
};

struct QueuedCmd {
  CmdType type;
  float p1;
  float p2;
  bool pen_down;
};

enum AppState : uint8_t { ST_IDLE, ST_RECEIVING, ST_RUNNING };

static String g_lineBuf;
static QueuedCmd g_queue[MAX_CMDS];
static size_t g_qCount;
static AppState g_state = ST_IDLE;
static size_t g_execIdx;
static bool g_waitActive;
static uint32_t g_waitStartMs;
static uint32_t g_waitDurationMs;

/* Yürütücü tarafı soyut durum (motor/PWM yok; yalnızca son kabul edilen parametreler) */
static float g_currentSpeed = 1.0f;
static bool g_penDown = false;
static CmdType g_lastCmdType = CMD_NONE;

static void sendErr(const char *msg) {
  Serial.print("ERR ");
  Serial.println(msg);
}

static void trimInPlace(String &s) {
  s.trim();
}

static bool parseFloatTok(const String &s, size_t start, float &out) {
  String t = s.substring(start);
  trimInPlace(t);
  if (t.length() == 0) return false;
  out = t.toFloat();
  return true;
}

static bool parseTwoFloatsAfterKeyword(const String &line, const char *kw, float &a,
                                     float &b) {
  String u = line;
  u.trim();
  String ku = String(kw);
  ku.toUpperCase();
  u.toUpperCase();
  if (!u.startsWith(ku)) return false;
  String rest = line;
  rest.trim();
  int sp = rest.indexOf(' ');
  if (sp < 0) return false;
  rest = rest.substring(sp + 1);
  trimInPlace(rest);
  sp = rest.indexOf(' ');
  if (sp < 0) return false;
  String sa = rest.substring(0, sp);
  String sb = rest.substring(sp + 1);
  trimInPlace(sa);
  trimInPlace(sb);
  if (sa.length() == 0 || sb.length() == 0) return false;
  a = sa.toFloat();
  b = sb.toFloat();
  return true;
}

static bool parseDslLine(const String &line, QueuedCmd &out) {
  String s = line;
  trimInPlace(s);
  if (s.length() == 0) return false;

  String u = s;
  u.toUpperCase();

  if (u.startsWith("SPEED ")) {
    float v;
    if (!parseFloatTok(s, 6, v)) return false;
    if (v <= 0.0f) return false;
    out.type = CMD_SPEED;
    out.p1 = v;
    return true;
  }
  if (u.startsWith("PEN ")) {
    String rest = s.substring(4);
    trimInPlace(rest);
    String ru = rest;
    ru.toUpperCase();
    out.type = CMD_PEN;
    if (ru == "UP") {
      out.pen_down = false;
      return true;
    }
    if (ru == "DOWN") {
      out.pen_down = true;
      return true;
    }
    return false;
  }
  if (u.startsWith("MOVE_REL ")) {
    float dx, dy;
    if (!parseTwoFloatsAfterKeyword(s, "MOVE_REL", dx, dy)) return false;
    out.type = CMD_MOVE_REL;
    out.p1 = dx;
    out.p2 = dy;
    return true;
  }
  if (u.startsWith("MOVE ")) {
    float x, y;
    if (!parseTwoFloatsAfterKeyword(s, "MOVE", x, y)) return false;
    out.type = CMD_MOVE;
    out.p1 = x;
    out.p2 = y;
    return true;
  }
  if (u.startsWith("TURN ")) {
    float deg;
    if (!parseFloatTok(s, 5, deg)) return false;
    out.type = CMD_TURN;
    out.p1 = deg;
    return true;
  }
  if (u.startsWith("FORWARD ")) {
    float d;
    if (!parseFloatTok(s, 8, d)) return false;
    if (d < 0.0f) return false;
    out.type = CMD_FORWARD;
    out.p1 = d;
    return true;
  }
  if (u.startsWith("WAIT ")) {
    float sec;
    if (!parseFloatTok(s, 5, sec)) return false;
    if (sec < 0.0f) return false;
    out.type = CMD_WAIT;
    out.p1 = sec;
    return true;
  }
  return false;
}

static void resetQueue() {
  g_qCount = 0;
  g_execIdx = 0;
  g_waitActive = false;
}

static void goIdle() { g_state = ST_IDLE; }

static const char *stateToken() {
  switch (g_state) {
    case ST_IDLE:
      return "IDLE";
    case ST_RECEIVING:
      return "RECEIVING";
    case ST_RUNNING:
      return "RUNNING";
    default:
      return "IDLE";
  }
}

static uint32_t queuedCountForStatus() {
  switch (g_state) {
    case ST_IDLE:
      return 0;
    case ST_RECEIVING:
      return (uint32_t)g_qCount;
    case ST_RUNNING:
      if (g_execIdx >= g_qCount) return 0;
      return (uint32_t)(g_qCount - g_execIdx);
    default:
      return 0;
  }
}

static const char *lastCmdToken() {
  switch (g_lastCmdType) {
    case CMD_NONE:
      return "NONE";
    case CMD_SPEED:
      return "SPEED";
    case CMD_MOVE:
      return "MOVE";
    case CMD_MOVE_REL:
      return "MOVE_REL";
    case CMD_TURN:
      return "TURN";
    case CMD_FORWARD:
      return "FORWARD";
    case CMD_WAIT:
      return "WAIT";
    case CMD_PEN:
      return "PEN";
    default:
      return "NONE";
  }
}

/* SERIAL_PROTOCOL_V1: STATUS ... (host parse_response_line ile status sayılır) */
static void printStatusLine() {
  Serial.print("STATUS speed=");
  Serial.print(g_currentSpeed, 4);
  Serial.print(" pen=");
  Serial.print(g_penDown ? "DOWN" : "UP");
  Serial.print(" state=");
  Serial.print(stateToken());
  Serial.print(" queued=");
  Serial.print(queuedCountForStatus());
  Serial.print(" last=");
  Serial.println(lastCmdToken());
}

static void applyExecutedCommand(const QueuedCmd &c) {
  g_lastCmdType = c.type;
  if (c.type == CMD_SPEED) {
    g_currentSpeed = c.p1;
  } else if (c.type == CMD_PEN) {
    g_penDown = c.pen_down;
  }
}

static void handleStop() {
  resetQueue();
  goIdle();
  Serial.println("DONE");
}

static void processCompleteLine(String line) {
  trimInPlace(line);
  if (line.length() == 0) return;
  if (line.charAt(0) == '#') return;
  String mu = line;
  mu.toUpperCase();
  if (mu.startsWith("META ")) return;

  if (mu == "STOP") {
    handleStop();
    return;
  }

  /* Host -> MCU: durum sorgusu; DONE üretmez (SerialDriver STATUS satırlarını yok sayar) */
  if (mu == "STATUS") {
    printStatusLine();
    return;
  }

  if (mu == "BEGIN") {
    g_state = ST_RECEIVING;
    resetQueue();
    g_lastCmdType = CMD_NONE;
    return;
  }

  if (mu == "END") {
    if (g_state != ST_RECEIVING) {
      sendErr("parse");
      goIdle();
      return;
    }
    g_state = ST_RUNNING;
    g_execIdx = 0;
    g_waitActive = false;
    return;
  }

  if (g_state == ST_RUNNING) {
    return;
  }

  if (g_state == ST_RECEIVING) {
    QueuedCmd qc{};
    if (!parseDslLine(line, qc)) {
      sendErr("parse");
      resetQueue();
      goIdle();
      return;
    }
    if (g_qCount >= MAX_CMDS) {
      sendErr("limit");
      resetQueue();
      goIdle();
      return;
    }
    g_queue[g_qCount++] = qc;
    return;
  }

  sendErr("unknown");
}

static void feedSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      processCompleteLine(g_lineBuf);
      g_lineBuf = "";
      continue;
    }
    if (g_lineBuf.length() < (int)MAX_LINE - 1) g_lineBuf += c;
  }
}

static void tickLoopback() {
  if (g_state != ST_RUNNING) return;

  if (g_execIdx >= g_qCount) {
    goIdle();
    Serial.println("DONE");
    return;
  }

  QueuedCmd &c = g_queue[g_execIdx];
  if (c.type == CMD_WAIT) {
    if (!g_waitActive) {
      g_waitDurationMs = (uint32_t)(c.p1 * 1000.0f);
      g_waitStartMs = millis();
      g_waitActive = true;
      return;
    }
    if (millis() - g_waitStartMs < g_waitDurationMs) return;
    g_waitActive = false;
    applyExecutedCommand(c);
    g_execIdx++;
    return;
  }

  applyExecutedCommand(c);
  g_execIdx++;
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  g_lineBuf.reserve(MAX_LINE);
  g_state = ST_IDLE;
  g_currentSpeed = 1.0f;
  g_penDown = false;
  g_lastCmdType = CMD_NONE;
  resetQueue();
}

void loop() {
  feedSerial();
  tickLoopback();
}
