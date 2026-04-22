#pragma once

#include <Arduino.h>
#include <math.h>
#include "actuator_interface.h"

class MotionStub {
public:
  explicit MotionStub(ActuatorInterface* act);

  void begin();

  // Busy ise baslatamaz; false dondurur.
  bool startHome(uint32_t nowMs);
  bool startMove(uint32_t nowMs, float x, float y);

  // Busy olsa bile hemen iptal eder.
  void stop(uint32_t nowMs);

  // Bu tick icinde bitis olduysa true dondurur.
  bool tick(uint32_t nowMs);

  bool isBusy() const { return m_busy; }

  // Kuyruk yerine sadece busy varsa 1 gosterilir (ilk surum icin).
  uint16_t queued() const { return m_busy ? 1 : 0; }

private:
  ActuatorInterface* m_act;

  bool m_busy;
  uint32_t m_busyUntilMs;
  bool m_justFinished;

  float m_lastX;
  float m_lastY;

  uint32_t m_homeDurationMs;
  uint32_t m_moveDurationMs;
};

