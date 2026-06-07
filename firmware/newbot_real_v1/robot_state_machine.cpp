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
  if (m_act) m_act->stopAll();

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
    hardStop(nowMs, "busy");
    return false;
  }

  bool ok = m_motion.startHome(nowMs);
  if (!ok) {
    hardStop(nowMs, "busy");
    return false;
  }

  m_state = RS_BUSY;
  m_lastError = "none";
  m_donePending = true;
  return true;
}

bool RobotStateMachine::onMove(uint32_t nowMs, float x, float y) {
  if (m_state == RS_BUSY) {
    hardStop(nowMs, "busy");
    return false;
  }

  bool ok = m_motion.startMove(nowMs, x, y);
  if (!ok) {
    hardStop(nowMs, "busy");
    return false;
  }

  m_state = RS_BUSY;
  m_lastError = "none";
  m_donePending = true;
  return true;
}

void RobotStateMachine::onStop(uint32_t nowMs) {
  // STOP oncelikli: busy iptal ve hosta DONE hemen gonderilir.
  hardStop(nowMs, "none");
}

void RobotStateMachine::hardStop(uint32_t nowMs, const char* reason, bool fault) {
  m_motion.stop(nowMs);
  if (m_act) m_act->stopAll();
  m_donePending = false;
  m_state = fault ? RS_FAULT : RS_STOPPED;
  m_lastError = reason ? reason : "stopped";
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
  hardStop(millis(), reason ? reason : "ariza", true);
}

void RobotStateMachine::setError(const char* reason) {
  m_lastError = reason ? reason : "hata";
}

