#include "motion_stub.h"

MotionStub::MotionStub(ActuatorInterface* act)
    : m_act(act),
      m_busy(false),
      m_busyUntilMs(0),
      m_justFinished(false),
      m_lastX(0.0f),
      m_lastY(0.0f),
      m_homeDurationMs(150),
      m_moveDurationMs(150) {}

void MotionStub::begin() {
  m_busy = false;
  m_busyUntilMs = 0;
  m_justFinished = false;
  m_lastX = 0.0f;
  m_lastY = 0.0f;
  m_homeDurationMs = 150;
  m_moveDurationMs = 150;
}

bool MotionStub::startHome(uint32_t nowMs) {
  if (m_busy) return false;
  m_justFinished = false;

  // Bu asamada sadece durum icin enable/disable var.
  if (m_act) m_act->enableMotors();

  m_busy = true;
  m_busyUntilMs = nowMs + m_homeDurationMs;
  return true;
}

bool MotionStub::startMove(uint32_t nowMs, float x, float y) {
  if (m_busy) return false;
  m_justFinished = false;

  m_lastX = x;
  m_lastY = y;

  if (m_act) m_act->enableMotors();

  // Ilk surum icin sabit sure; ileride mesafeye gore ayarlanabilir.
  m_busy = true;
  m_busyUntilMs = nowMs + m_moveDurationMs;
  return true;
}

void MotionStub::stop(uint32_t nowMs) {
  (void)nowMs;
  m_busy = false;
  m_busyUntilMs = 0;
  m_justFinished = false;

  if (m_act) {
    m_act->stopAll();
    m_act->disableMotors();
  }
}

bool MotionStub::tick(uint32_t nowMs) {
  m_justFinished = false;

  if (!m_busy) return false;

  // millis() wrap-riskine karsi imzali fark yaklasimi.
  if ((int32_t)(nowMs - m_busyUntilMs) >= 0) {
    m_busy = false;
    m_busyUntilMs = 0;
    m_justFinished = true;

    if (m_act) {
      m_act->disableMotors();
    }
    return true;
  }
  return false;
}

