#include "serial_protocol_v1.h"

#include <stdlib.h>

static void trimInPlace(String& s) { s.trim(); }

static bool parseFloatTok(const String& tok, float& out) {
  String t = tok;
  trimInPlace(t);
  if (t.length() == 0) return false;

  const char* cstr = t.c_str();
  char* endptr = nullptr;
  double v = strtod(cstr, &endptr);
  if (endptr == cstr) return false;

  // Token'un tamamini tuketmis olmali.
  // (String icinde bosluk yok; bu kontrol erken ariza durumlarini yakalar.)
  if (*endptr != '\0') return false;

  out = (float)v;
  return true;
}

static bool parseMoveParamsKeyValue(const String& restUpper,
                                      const String& restOrig,
                                      float& x,
                                      float& y,
                                      bool& hasX,
                                      bool& hasY) {
  // restUpper/restOrig ayni uzunlukta ama case icin farkli; yine de
  // deger kisimlari ayni karakterler oldugu icin parseFloatTok icinde
  // restOrig'tan cektigimiz val ile calismak guvenli.
  (void)restUpper;

  hasX = false;
  hasY = false;

  int start = 0;
  while (start < restOrig.length()) {
    while (start < restOrig.length() && restOrig.charAt(start) == ' ') start++;
    if (start >= restOrig.length()) break;

    int end = start;
    while (end < restOrig.length() && restOrig.charAt(end) != ' ') end++;
    if (end <= start) break;

    String tokUpper = restUpper.substring(start, end);
    tokUpper.toUpperCase();

    int eq = tokUpper.indexOf('=');
    if (eq < 0) {
      start = end + 1;
      continue;
    }

    String key = tokUpper.substring(0, eq);
    // Deger: restOrig substringinden alinacak.
    String val = restOrig.substring(start + eq + 1, end);
    trimInPlace(val);

    if (key == "X") {
      float vx;
      if (!parseFloatTok(val, vx)) return false;
      x = vx;
      hasX = true;
    } else if (key == "Y") {
      float vy;
      if (!parseFloatTok(val, vy)) return false;
      y = vy;
      hasY = true;
    }

    start = end + 1;
  }

  return true;
}

static bool parseMoveParamsSpace(const String& restUpper,
                                  const String& restOrig,
                                  float& x,
                                  float& y,
                                  bool& hasX,
                                  bool& hasY) {
  (void)restUpper;
  (void)restOrig;
  // restOrig uzerinden token ayiklayalim.
  hasX = false;
  hasY = false;

  String r = restOrig;
  trimInPlace(r);

  int sp1 = r.indexOf(' ');
  if (sp1 < 0) return false;
  String t1 = r.substring(0, sp1);
  String t2 = r.substring(sp1 + 1);
  trimInPlace(t2);

  if (t1.length() == 0 || t2.length() == 0) return false;

  float vx;
  float vy;
  if (!parseFloatTok(t1, vx)) return false;
  if (!parseFloatTok(t2, vy)) return false;

  x = vx;
  y = vy;
  hasX = true;
  hasY = true;
  return true;
}

bool parse_serial_protocol_v1_line(const String& line,
                                    ProtoParsedLine& out,
                                    const char*& errReason) {
  out = ProtoParsedLine{};
  out.type = TL_NONE;
  out.x = 0.0f;
  out.y = 0.0f;
  out.f1 = 0.0f;
  out.penDown = false;
  errReason = nullptr;

  String s = line;
  trimInPlace(s);
  if (s.length() == 0) {
    out.type = TL_NONE;
    return true;
  }

  String u = s;
  u.toUpperCase();

  if (u == "STATUS") {
    out.type = TL_STATUS;
    return true;
  }
  if (u == "STOP") {
    out.type = TL_STOP;
    return true;
  }
  if (u == "HOME") {
    out.type = TL_HOME;
    return true;
  }
  if (u == "BEGIN") {
    out.type = TL_BEGIN;
    return true;
  }
  if (u == "END") {
    out.type = TL_END;
    return true;
  }

  // SPEED <f>
  if (u.startsWith("SPEED ")) {
    float v;
    String rest = s.substring(6);
    trimInPlace(rest);
    if (!parseFloatTok(rest, v)) {
      errReason = "invalid_number";
      return false;
    }
    if (v <= 0.0f) {
      errReason = "invalid_number";
      return false;
    }
    out.type = TL_SPEED;
    out.f1 = v;
    return true;
  }

  // PEN UP / PEN DOWN
  if (u.startsWith("PEN ")) {
    String rest = s.substring(4);
    trimInPlace(rest);
    String ru = rest;
    ru.toUpperCase();
    out.type = TL_PEN;
    if (ru == "UP") {
      out.penDown = false;
      return true;
    }
    if (ru == "DOWN") {
      out.penDown = true;
      return true;
    }
    errReason = "bilinmeyen";
    return false;
  }

  // FORWARD <dist>
  if (u.startsWith("FORWARD ")) {
    float v;
    String rest = s.substring(8);
    trimInPlace(rest);
    if (!parseFloatTok(rest, v)) {
      errReason = "invalid_number";
      return false;
    }
    if (v < 0.0f) {
      errReason = "invalid_number";
      return false;
    }
    out.type = TL_FORWARD;
    out.f1 = v;
    return true;
  }

  // TURN <deg>
  if (u.startsWith("TURN ")) {
    float v;
    String rest = s.substring(5);
    trimInPlace(rest);
    if (!parseFloatTok(rest, v)) {
      errReason = "invalid_number";
      return false;
    }
    out.type = TL_TURN;
    out.f1 = v;
    return true;
  }

  // WAIT <s>
  if (u.startsWith("WAIT ")) {
    float v;
    String rest = s.substring(5);
    trimInPlace(rest);
    if (!parseFloatTok(rest, v)) {
      errReason = "invalid_number";
      return false;
    }
    if (v < 0.0f) {
      errReason = "invalid_number";
      return false;
    }
    out.type = TL_WAIT;
    out.f1 = v;
    return true;
  }

  // MOVE ...
  if (u.startsWith("MOVE")) {
    // "MOVE" sonrasini alma
    String restOrig = s;
    restOrig.trim();
    int idx = restOrig.indexOf(' ');
    if (idx < 0) {
      errReason = "missing_param";
      return false;
    }

    String restUpper = u.substring(idx + 1);
    restOrig = s.substring(idx + 1);
    restOrig.trim();
    restUpper.trim();

    float mx = 0.0f;
    float my = 0.0f;
    bool hasX = false;
    bool hasY = false;

    // Anahtar=değer mi?
    bool hasEq = false;
    for (int i = 0; i < restUpper.length(); i++) {
      if (restUpper.charAt(i) == '=') {
        hasEq = true;
        break;
      }
    }

    bool okParse = false;
    if (hasEq) {
      okParse = parseMoveParamsKeyValue(restUpper, restOrig, mx, my, hasX, hasY);
    } else {
      okParse = parseMoveParamsSpace(restUpper, restOrig, mx, my, hasX, hasY);
    }

    if (!okParse) {
      // Tek token (ornegin "MOVE 10") gibi eksik durumlari eksik_parametre sebebine alalim.
      String r = restOrig;
      trimInPlace(r);
      int sp = r.indexOf(' ');
      if (sp < 0) {
        errReason = "missing_param";
      } else {
        String t2 = r.substring(sp + 1);
        trimInPlace(t2);
        errReason = (t2.length() == 0) ? "missing_param" : "invalid_number";
      }
      return false;
    }
    if (!hasX || !hasY) {
      errReason = "missing_param";
      return false;
    }

    out.type = TL_MOVE;
    out.x = mx;
    out.y = my;
    return true;
  }

  errReason = "bilinmeyen";
  return false;
}

void serial_protocol_v1_write_done() { Serial.println("DONE"); }

void serial_protocol_v1_write_err(const char* reason) {
  Serial.print("ERR ");
  Serial.println(reason ? reason : "bilinmeyen");
}

void serial_protocol_v1_write_status(const char* stateToken,
                                      const char* errorToken,
                                      uint16_t queued) {
  serial_protocol_v1_write_status_ex(stateToken, errorToken, queued, nullptr);
}

void serial_protocol_v1_write_status_ex(const char* stateToken,
                                         const char* errorToken,
                                         uint16_t queued,
                                         const char* actuatorFields) {
  Serial.print("STATUS state=");
  Serial.print(stateToken ? stateToken : "IDLE");
  Serial.print(" fw=newbot_real_v1 motion=stub error=");
  Serial.print(errorToken ? errorToken : "none");
  Serial.print(" queued=");
  Serial.print(queued);
  if (actuatorFields && actuatorFields[0] != '\0') {
    Serial.print(actuatorFields);
  }
  Serial.println();
}

