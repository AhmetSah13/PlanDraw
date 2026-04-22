#pragma once

#include <Arduino.h>
#include "actuator_interface.h"
#include "motion_stub.h"

enum RobotState : uint8_t { RS_BOOT = 0, RS_IDLE, RS_BUSY, RS_STOPPED, RS_FAULT };

class RobotStateMachine {
public:
  explicit RobotStateMachine(ActuatorInterface* act);

  void begin();

  RobotState state() const { return m_state; }

  const char* stateToken() const;

  uint16_t queued() const;

  const char* lastErrorToken() const { return m_lastError; }

  bool onHome(uint32_t nowMs);
  bool onMove(uint32_t nowMs, float x, float y);

  // STOP komutunda busy iptal edilir; host DONE'i hemen alir.
  void onStop(uint32_t nowMs);

  // Tick: hareket bittiyse DONE yollamak icin true doner.
  bool tick(uint32_t nowMs);

  void setFault(const char* reason);
  void setError(const char* reason);

private:
  ActuatorInterface* m_act;
  MotionStub m_motion;

  RobotState m_state;
  const char* m_lastError;

  bool m_donePending;
  uint32_t m_stopReleaseMs;
  uint32_t m_bootReleaseMs;
};

