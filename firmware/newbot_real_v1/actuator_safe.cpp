#include "actuator_safe.h"

#include <stdio.h>

#include "robot_config.h"

namespace {

bool s_motorsEnabled = false;
bool s_outputsArmed = false;
bool s_penDown = false;
uint32_t s_stepRateHz = DEFAULT_STEP_RATE_HZ;
uint32_t s_lastStepMicros = 0;
bool s_servoAttached = false;

bool pinAssigned(int pin) { return pin >= 0; }

bool leftMotorPinsAssigned() {
  return pinAssigned(LEFT_STEP_PIN) && pinAssigned(LEFT_DIR_PIN);
}

bool rightMotorPinsAssigned() {
  return pinAssigned(RIGHT_STEP_PIN) && pinAssigned(RIGHT_DIR_PIN);
}

bool motorPinsAssigned() { return leftMotorPinsAssigned() && rightMotorPinsAssigned(); }

void writeEnablePin(int pin, bool enable) {
  if (!pinAssigned(pin)) return;
  const bool level = MOTOR_ENABLE_ACTIVE_LOW ? !enable : enable;
  digitalWrite(pin, level ? HIGH : LOW);
}

void configureOutputPin(int pin) {
  if (!pinAssigned(pin)) return;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
}

uint32_t clampStepRateHz(uint32_t hz) {
  if (hz == 0) return DEFAULT_STEP_RATE_HZ;
  if (hz > MAX_STEP_RATE_HZ) return MAX_STEP_RATE_HZ;
  return hz;
}

uint32_t minStepIntervalMicros() {
  const uint32_t hz = clampStepRateHz(s_stepRateHz);
  if (hz == 0) return 1000000UL;
  return 1000000UL / hz;
}

bool canEmitMotorPulse() {
  return s_motorsEnabled && s_outputsArmed && motorPinsAssigned();
}

void emitStepPulse(int stepPin) {
  if (!canEmitMotorPulse() || !pinAssigned(stepPin)) return;

  const uint32_t now = micros();
  const uint32_t minInterval = minStepIntervalMicros();
  if (s_lastStepMicros != 0 && (uint32_t)(now - s_lastStepMicros) < minInterval) {
    return;
  }

  digitalWrite(stepPin, HIGH);
  delayMicroseconds(MIN_STEP_PULSE_US);
  digitalWrite(stepPin, LOW);
  s_lastStepMicros = now;
}

void applyPenAngle(int angle) {
  (void)angle;
  // Servo surucu Patch 4B: ESP32-S3 icin uygun servo kutuphanesi ve aci kalibrasyonu
  // henuz baglanmadi. Pin atanmis olsa bile gercek PWM/servo attach yapilmaz.
}

void detachServoIfNeeded() {
  s_servoAttached = false;
}

}  // namespace

bool actuatorIsPinAssigned(int pin) { return pinAssigned(pin); }

bool actuatorIsConfigured() { return motorPinsAssigned() && pinAssigned(PEN_SERVO_PIN); }

void actuatorInit() {
  s_motorsEnabled = false;
  s_outputsArmed = false;
  s_penDown = false;
  s_stepRateHz = DEFAULT_STEP_RATE_HZ;
  s_lastStepMicros = 0;

  configureOutputPin(LEFT_STEP_PIN);
  configureOutputPin(LEFT_DIR_PIN);
  configureOutputPin(LEFT_ENABLE_PIN);
  configureOutputPin(RIGHT_STEP_PIN);
  configureOutputPin(RIGHT_DIR_PIN);
  configureOutputPin(RIGHT_ENABLE_PIN);

  if (pinAssigned(PEN_SERVO_PIN)) {
    pinMode(PEN_SERVO_PIN, OUTPUT);
    digitalWrite(PEN_SERVO_PIN, LOW);
  }

  if (SAFE_BOOT_MOTORS_DISABLED || !MOTOR_OUTPUTS_ENABLED_BY_DEFAULT) {
    actuatorDisableOutputs();
  }

  if (SAFE_BOOT_PEN_UP) {
    actuatorSetPenUp();
  }

  detachServoIfNeeded();
}

bool actuatorEnableOutputs() {
  if (!motorPinsAssigned()) {
    s_outputsArmed = false;
    s_motorsEnabled = false;
    return false;
  }

  if (REQUIRE_EXPLICIT_ACTUATOR_ENABLE) {
    s_outputsArmed = true;
  } else {
    s_outputsArmed = MOTOR_OUTPUTS_ENABLED_BY_DEFAULT;
  }

  writeEnablePin(LEFT_ENABLE_PIN, true);
  writeEnablePin(RIGHT_ENABLE_PIN, true);
  s_motorsEnabled = s_outputsArmed;
  return s_motorsEnabled;
}

void actuatorDisableOutputs() {
  writeEnablePin(LEFT_ENABLE_PIN, false);
  writeEnablePin(RIGHT_ENABLE_PIN, false);
  s_motorsEnabled = false;
  s_outputsArmed = false;
  s_lastStepMicros = 0;
}

void actuatorHardStop() {
  actuatorDisableOutputs();
  actuatorSetPenUp();
  detachServoIfNeeded();
}

void actuatorSetStepRateHz(uint32_t hz) { s_stepRateHz = clampStepRateHz(hz); }

uint32_t actuatorGetStepRateHz() { return clampStepRateHz(s_stepRateHz); }

void actuatorSetLeftDirection(bool forward) {
  if (!pinAssigned(LEFT_DIR_PIN)) return;
  const bool level = (forward != LEFT_MOTOR_INVERTED);
  digitalWrite(LEFT_DIR_PIN, level ? HIGH : LOW);
}

void actuatorSetRightDirection(bool forward) {
  if (!pinAssigned(RIGHT_DIR_PIN)) return;
  const bool level = (forward != RIGHT_MOTOR_INVERTED);
  digitalWrite(RIGHT_DIR_PIN, level ? HIGH : LOW);
}

void actuatorStepLeft() { emitStepPulse(LEFT_STEP_PIN); }

void actuatorStepRight() { emitStepPulse(RIGHT_STEP_PIN); }

void actuatorSetPenUp() {
  s_penDown = false;
  if (!pinAssigned(PEN_SERVO_PIN) || !PEN_OUTPUT_ENABLED_BY_DEFAULT) return;
  applyPenAngle(PEN_UP_ANGLE);
}

void actuatorSetPenDown() {
  if (!pinAssigned(PEN_SERVO_PIN)) {
    s_penDown = true;
    return;
  }
  if (!PEN_OUTPUT_ENABLED_BY_DEFAULT) {
    s_penDown = true;
    return;
  }
  applyPenAngle(PEN_DOWN_ANGLE);
  s_penDown = true;
}

bool actuatorIsPenDown() { return s_penDown; }

void actuatorGetStatus(ActuatorStatusInfo& out) {
  out.configured = actuatorIsConfigured();
  out.motorsEnabled = s_motorsEnabled;
  out.outputsArmed = s_outputsArmed;
  out.penDown = s_penDown;
  out.leftPinsAssigned = leftMotorPinsAssigned();
  out.rightPinsAssigned = rightMotorPinsAssigned();
  out.penPinAssigned = pinAssigned(PEN_SERVO_PIN);
  out.stepRateHz = actuatorGetStepRateHz();
}

void actuatorFormatStatusFields(char* buf, size_t bufLen) {
  if (!buf || bufLen == 0) return;

  ActuatorStatusInfo st;
  actuatorGetStatus(st);

  snprintf(buf, bufLen,
           " actuator=%s motors=%s pen=%s left_pin=%s right_pin=%s pen_pin=%s",
           st.configured ? "configured" : "unconfigured",
           st.motorsEnabled ? "enabled" : "disabled",
           st.penDown ? "down" : "up",
           st.leftPinsAssigned ? "assigned" : "unassigned",
           st.rightPinsAssigned ? "assigned" : "unassigned",
           st.penPinAssigned ? "assigned" : "unassigned");
}

void ActuatorSafe::begin() { actuatorInit(); }

void ActuatorSafe::enableMotors() { (void)actuatorEnableOutputs(); }

void ActuatorSafe::disableMotors() { actuatorDisableOutputs(); }

void ActuatorSafe::stopAll() { actuatorHardStop(); }

void ActuatorSafe::setPenDown(bool down) {
  if (down) {
    actuatorSetPenDown();
  } else {
    actuatorSetPenUp();
  }
}
