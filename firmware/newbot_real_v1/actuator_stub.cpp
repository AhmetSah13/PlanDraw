#include "actuator_stub.h"

ActuatorStub::ActuatorStub() : m_motorsEnabled(false), m_penDown(false) {}

void ActuatorStub::begin() {
  m_motorsEnabled = false;
  m_penDown = false;
}

void ActuatorStub::enableMotors() { m_motorsEnabled = true; }

void ActuatorStub::disableMotors() { m_motorsEnabled = false; }

void ActuatorStub::stopAll() {
  // Bu asamada sadece durum kaydi var.
  m_motorsEnabled = false;
}

void ActuatorStub::setPenDown(bool down) { m_penDown = down; }

