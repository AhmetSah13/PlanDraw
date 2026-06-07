#pragma once

#include "actuator_interface.h"

// ActuatorInterface uygulamasi: config odakli, varsayilan disabled, pin yoksa stub-safe.
class ActuatorSafe : public ActuatorInterface {
public:
  void begin() override;
  void enableMotors() override;
  void disableMotors() override;
  void stopAll() override;
  void setPenDown(bool down) override;
};
