#pragma once

#include <Arduino.h>

// Bu asamada sadece arabirim var; gercek motor/pwm/encoder yok.
// Ileride motor surumu eklenirken sadece bu sinirlar korunur.
class ActuatorInterface {
public:
  virtual ~ActuatorInterface() {}

  virtual void begin() = 0;
  virtual void enableMotors() = 0;
  virtual void disableMotors() = 0;
  virtual void stopAll() = 0;
  virtual void setPenDown(bool down) = 0;
};

