#pragma once

#include <Arduino.h>
#include "actuator_interface.h"

// Donanim yokken bile derlenip calisacak en dusuk seviye taklit.
class ActuatorStub : public ActuatorInterface {
public:
  ActuatorStub();

  void begin() override;
  void enableMotors() override;
  void disableMotors() override;
  void stopAll() override;
  void setPenDown(bool down) override;

  bool motorsEnabled() const { return m_motorsEnabled; }
  bool penDown() const { return m_penDown; }

private:
  bool m_motorsEnabled;
  bool m_penDown;
};

