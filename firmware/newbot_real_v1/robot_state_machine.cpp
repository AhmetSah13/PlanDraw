#include "robot_state_machine.h"

RobotStateMachine::RobotStateMachine(ActuatorInterface* act)
    : m_act(act),
      m_motion(act),
      m_state(RS_BOOT),
      m_lastError("none"),
      m_donePending(false),
      m_stopReleaseMs(0),
      m_bootReleaseMs(0) {}

void RobotStateMachine::begin() {
  if (m_act) m_act->begin();
  m_motion.begin();

  m_lastError = "none";
  m_donePending = false;
  m_stopReleaseMs = 0;

  // BOOT durumunu cok kisa tutalim.
  m_state = RS_BOOT;
  m_bootReleaseMs = millis() + 50;
}

const char* RobotStateMachine::stateToken() const {
  switch (m_state) {
    case RS_BOOT:
      return "BOOT";
    case RS_IDLE:
      return "IDLE";
    case RS_BUSY:
      return "BUSY";
    case RS_STOPPED:
      return "STOPPED";
    case RS_FAULT:
      return "FAULT";
    default:
      return "IDLE";
  }
}

uint16_t RobotStateMachine::queued() const { return m_motion.queued(); }

bool RobotStateMachine::onHome(uint32_t nowMs) {
  if (m_state == RS_BUSY) {
    setError("busy");
    return false;
  }

  bool ok = m_motion.startHome(nowMs);
  if (!ok) {
    setError("busy");
    return false;
  }

  m_state = RS_BUSY;
  m_lastError = "none";
  m_donePending = true;
  return true;
}

bool RobotStateMachine::onMove(uint32_t nowMs, float x, float y) {
  if (m_state == RS_BUSY) {
    setError("busy");
    return false;
  }

  bool ok = m_motion.startMove(nowMs, x, y);
  if (!ok) {
    setError("busy");
    return false;
  }

  m_state = RS_BUSY;
  m_lastError = "none";
  m_donePending = true;
  return true;
}

void RobotStateMachine::onStop(uint32_t nowMs) {
  // STOP oncelikli: busy iptal ve hosta DONE hemen gonderilir.
  m_motion.stop(nowMs);
  m_donePending = false;
  m_state = RS_STOPPED;
  m_lastError = "none";
  m_stopReleaseMs = nowMs + 200;
}

bool RobotStateMachine::tick(uint32_t nowMs) {
  // BOOT bitince IDLE'e gec.
  if (m_state == RS_BOOT) {
    if ((int32_t)(nowMs - m_bootReleaseMs) >= 0) {
      m_state = RS_IDLE;
    }
    return false;
  }

  // STOPPED gecis suresi.
  if (m_state == RS_STOPPED) {
    if ((int32_t)(nowMs - m_stopReleaseMs) >= 0) {
      m_state = RS_IDLE;
    }
  }

  // Hareket bitti mi?
  bool finished = m_motion.tick(nowMs);
  if (finished && m_donePending) {
    m_state = RS_IDLE;
    m_donePending = false;
    return true;
  }

  return false;
}

void RobotStateMachine::setFault(const char* reason) {
  m_state = RS_FAULT;
  m_lastError = reason ? reason : "ariza";
  m_donePending = false;
}

void RobotStateMachine::setError(const char* reason) {
  m_lastError = reason ? reason : "hata";
}

