#pragma once

#include <Arduino.h>

// Actuator durum ozeti (STATUS alanlari ve debug icin).
struct ActuatorStatusInfo {
  bool configured;
  bool motorsEnabled;
  bool outputsArmed;
  bool penDown;
  bool leftPinsAssigned;
  bool rightPinsAssigned;
  bool penPinAssigned;
  uint32_t stepRateHz;
};

// Donanim bagimsiz actuator API (Patch 4A).
// Pin atanmamissa gercek GPIO/servo cikisi uretilmez.

void actuatorInit();
bool actuatorIsConfigured();
bool actuatorIsPinAssigned(int pin);

bool actuatorEnableOutputs();
void actuatorDisableOutputs();
void actuatorHardStop();

void actuatorSetStepRateHz(uint32_t hz);
uint32_t actuatorGetStepRateHz();

void actuatorSetLeftDirection(bool forward);
void actuatorSetRightDirection(bool forward);
void actuatorStepLeft();
void actuatorStepRight();

void actuatorSetPenUp();
void actuatorSetPenDown();
bool actuatorIsPenDown();

void actuatorGetStatus(ActuatorStatusInfo& out);
void actuatorFormatStatusFields(char* buf, size_t bufLen);

// MotionStub / RobotStateMachine uyumlulugu icin sanal arayuz.
class ActuatorInterface {
public:
  virtual ~ActuatorInterface() {}

  virtual void begin() = 0;
  virtual void enableMotors() = 0;
  virtual void disableMotors() = 0;
  virtual void stopAll() = 0;
  virtual void setPenDown(bool down) = 0;
};
