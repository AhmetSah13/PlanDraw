/*
 * NewBot gercek firmware v1 iskeleti (ilk asama).
 * - Motor/calismayi simule eden motion taklit var.
 * - STATUS/DONE/ERR wire yanitlari var.
 * - STOP oncelikli; BUSY sirasinda hareket iptal edilir.
 *
 * Ileride: motor/surucu ve kalem aktuatörü bu iskeletin uzerine eklenecek.
 */

#include <Arduino.h>

#include "actuator_stub.h"
#include "robot_state_machine.h"
#include "serial_protocol_v1.h"

static const unsigned long SERIAL_BAUD = 115200;
static const size_t MAX_LINE = 160;

static String g_lineBuf;

static ActuatorStub g_act;
static RobotStateMachine g_rsm(&g_act);

static void processLine(const String& line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;
  if (s.charAt(0) == '#') return;

  ProtoParsedLine pl;
  const char* errReason = nullptr;
  bool ok = parse_serial_protocol_v1_line(s, pl, errReason);
  if (!ok) {
    const char* reason = errReason ? errReason : "bilinmeyen";
    g_rsm.setError(reason);
    serial_protocol_v1_write_err(reason);
    return;
  }

  uint32_t nowMs = millis();

  switch (pl.type) {
    case TL_NONE:
      return;

    case TL_BEGIN:
      // Bu asamada batch'in ici ayrica kuyruga alinmiyor; kontrol kelimesi olarak yok say.
      return;

    case TL_END:
      // Bu asamada END, DONE'i tetiklemiyor; DONE motion bitince gelir.
      return;

    case TL_STATUS:
      serial_protocol_v1_write_status(g_rsm.stateToken(),
                                        g_rsm.lastErrorToken(),
                                        g_rsm.queued());
      return;

    case TL_STOP:
      g_rsm.onStop(nowMs);
      serial_protocol_v1_write_done();
      return;

    case TL_HOME:
      if (!g_rsm.onHome(nowMs)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    case TL_MOVE:
      if (!g_rsm.onMove(nowMs, pl.x, pl.y)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    case TL_FORWARD:
      // FORWARD taklit olarak MOVE gibi busy yaratir.
      if (!g_rsm.onMove(nowMs, pl.f1, 0.0f)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    case TL_TURN:
      // TURN taklit olarak MOVE gibi busy yaratir.
      if (!g_rsm.onMove(nowMs, pl.f1, 0.0f)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    case TL_WAIT:
      // WAIT taklit olarak MOVE gibi busy yaratir (ilksur um sabit sure).
      if (!g_rsm.onMove(nowMs, pl.f1, 0.0f)) {
        serial_protocol_v1_write_err(g_rsm.lastErrorToken());
      }
      return;

    case TL_SPEED:
      // Ilk surumda sadece parse var; davranisa etkisi yok.
      g_rsm.setError("none");
      return;

    case TL_PEN:
      // Bu asamada kalem icin sadece durum tut.
      g_act.setPenDown(pl.penDown);
      g_rsm.setError("none");
      return;

    default:
      serial_protocol_v1_write_err("bilinmeyen");
      g_rsm.setError("bilinmeyen");
      return;
  }
}

static void feedSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      processLine(g_lineBuf);
      g_lineBuf = "";
      continue;
    }
    if (g_lineBuf.length() < (int)MAX_LINE - 1) {
      g_lineBuf += c;
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  g_lineBuf.reserve(MAX_LINE);
  g_rsm.begin();
}

void loop() {
  feedSerial();

  uint32_t nowMs = millis();
  bool sendDone = g_rsm.tick(nowMs);
  if (sendDone) {
    serial_protocol_v1_write_done();
  }
}

