#pragma once

#include <Arduino.h>

// Donanim modeli (Patch 4A): pinler henuz atanmadi; gercek degerler Patch 4B'de girilecek.

static const char BOARD_TARGET_NOTE[] = "ESP32-S3 DevKitC-1 N16R8";
// FQBN dokumantasyon notu (tahmin degil, build oncesi dogrulanmali):
// Ornek aday: esp32:esp32:esp32s3 — kesin FQBN firmware/BUILD.md ve donanim ekibi ile netlestirilir.

static const int PIN_UNASSIGNED = -1;

// --- Stepper / TMC2208 STEP-DIR-EN (placeholder) ---
static const int LEFT_STEP_PIN = PIN_UNASSIGNED;
static const int LEFT_DIR_PIN = PIN_UNASSIGNED;
static const int LEFT_ENABLE_PIN = PIN_UNASSIGNED;

static const int RIGHT_STEP_PIN = PIN_UNASSIGNED;
static const int RIGHT_DIR_PIN = PIN_UNASSIGNED;
static const int RIGHT_ENABLE_PIN = PIN_UNASSIGNED;

static const bool MOTOR_ENABLE_ACTIVE_LOW = true;
static const bool LEFT_MOTOR_INVERTED = false;
static const bool RIGHT_MOTOR_INVERTED = false;

static const uint32_t MAX_STEP_RATE_HZ = 2000;
static const uint32_t DEFAULT_STEP_RATE_HZ = 400;
static const uint32_t MIN_STEP_PULSE_US = 2;

static const bool MOTOR_OUTPUTS_ENABLED_BY_DEFAULT = false;

// --- Pen servo (placeholder acilar; mekanik kalibrasyon Patch 4B) ---
static const int PEN_SERVO_PIN = PIN_UNASSIGNED;
static const int PEN_UP_ANGLE = 90;    // PLACEHOLDER — kalibre edilecek
static const int PEN_DOWN_ANGLE = 0;   // PLACEHOLDER — kalibre edilecek
static const uint32_t PEN_SETTLE_MS = 300;

static const bool PEN_OUTPUT_ENABLED_BY_DEFAULT = false;

// --- Safety ---
static const bool REQUIRE_EXPLICIT_ACTUATOR_ENABLE = true;
static const uint32_t HEARTBEAT_TIMEOUT_MS = 5000;
static const bool SAFE_BOOT_PEN_UP = true;
static const bool SAFE_BOOT_MOTORS_DISABLED = true;
