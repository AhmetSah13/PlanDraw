#include "actuator_stub.h"

ActuatorStub::ActuatorStub() : m_motorsEnabled(false), m_penDown(false) {}

void ActuatorStub::begin() {
  stopAll();
}

void ActuatorStub::enableMotors() { m_motorsEnabled = true; }

void ActuatorStub::disableMotors() { m_motorsEnabled = false; }

void ActuatorStub::stopAll() {
  // Stub bile gercek guvenlik davranisini taklit eder:
  // motorlar kapali, kalem guvenli/inactive (pen up) durumda.
  m_motorsEnabled = false;
  m_penDown = false;
}

void ActuatorStub::setPenDown(bool down) { m_penDown = down; }

