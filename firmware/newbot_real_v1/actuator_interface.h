#pragma once

#include <Arduino.h>

// Bu asamada sadece arabirim var; gercek motor/pwm/encoder yok.
// Ileride motor surumu eklenirken stopAll() merkezi guvenli durdurma
// siniri olarak korunur: motor gucu kesilir ve actuator safe state'e alinir.
class ActuatorInterface {
public:
  virtual ~ActuatorInterface() {}

  virtual void begin() = 0;
  virtual void enableMotors() = 0;
  virtual void disableMotors() = 0;
  virtual void stopAll() = 0;
  virtual void setPenDown(bool down) = 0;
};

