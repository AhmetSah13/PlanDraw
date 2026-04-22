#pragma once

#include <Arduino.h>

// Wire (seri satir) protokol parcalari.
// Bu asamada hedef: minimum komutlari parse etmek ve STATUS/DONE/ERR basmak.

enum ProtoLineType : uint8_t {
  TL_NONE = 0,
  TL_STATUS,
  TL_STOP,
  TL_HOME,
  TL_MOVE,
  TL_SPEED,
  TL_PEN,
  TL_TURN,
  TL_FORWARD,
  TL_WAIT,
  TL_BEGIN,
  TL_END,
};

struct ProtoParsedLine {
  ProtoLineType type;

  // MOVE icin:
  float x;
  float y;

  // FORWARD/TURN/WAIT icin:
  float f1;

  // PEN icin:
  bool penDown;
};

// Dondurulen true: satir biliniyor ve parse basarili.
// false: satir biliniyor olsa bile parse edilemedi ya da komut bilinmiyor.
// errReason: ERR <reason> icin kisa bir sebep.
bool parse_serial_protocol_v1_line(const String& line,
                                    ProtoParsedLine& out,
                                    const char*& errReason);

void serial_protocol_v1_write_done();
void serial_protocol_v1_write_err(const char* reason);
void serial_protocol_v1_write_status(const char* stateToken,
                                      const char* errorToken,
                                      uint16_t queued);

