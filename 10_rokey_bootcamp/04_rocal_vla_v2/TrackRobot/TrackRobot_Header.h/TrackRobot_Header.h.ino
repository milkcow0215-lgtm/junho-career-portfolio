// ============================================================================
// File: TrackRobot_Header.h
// Description: Global Constants, Pin Configurations, and State Variables
// Project: Autonomous Railway Inspection Robot System (Graduation Project)
// ============================================================================

#ifndef TRACK_ROBOT_HEADER_H
#define TRACK_ROBOT_HEADER_H

#include <math.h>
#include <stdlib.h>
#include <stdint.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>

// ---- Math Compatibility Guards ----
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef fabsf
#define fabsf(x) ((float)fabs(x))
#endif

static inline float fmaxf_local(float a, float b) { return (a > b) ? a : b; }
static inline float fminf_local(float a, float b) { return (a < b) ? a : b; }

// ---- Hardware Pin Mapping ----
const int PIN_PL1 = A0, PIN_PL2 = A1, PIN_PR1 = A2, PIN_PR2 = A3;   // Potentiometers
const int TRIG_L = 40, ECHO_L = 41, TRIG_R = 42, ECHO_R = 43;       // Ultrasonic Sensors
const int PIN_R_EN = 22;      // BTS7960 R Enable (Active HIGH)
const int PIN_L_EN = 23;      // BTS7960 L Enable (Active HIGH)
const int PIN_RPWM = 45;      // BTS7960 RPWM -> OC5B (Timer5)
const int PIN_LPWM = 46;      // BTS7960 LPWM -> OC5A (Timer5)
const int encoderPinA = 2, encoderPinB = 3;                         // Quadrature Encoder

// ---- Kinematics & Calibration ----
const float countsPerRev = 637.0f;
const float wheelCircumf = 0.1971f * 3.1415926f;                    // Wheel Circumference (~0.6192m)
const float gearRatioExtra = 35.0f / 18.0f;                         // External Spur Gear Ratio
const float meterPerCount = (wheelCircumf / countsPerRev) / gearRatioExtra; // ~0.0005m / Count

const float POT_TOTAL_DEG = 300.0f;
const float degreePerStep = POT_TOTAL_DEG / 1023.0f;                // ~0.2937 deg / LSB
const int8_t potSign[4] = { -1, -1, -1, -1 };
const float tolerance_deg = 10.0f;                                 // Structural Twist Threshold

// ---- Filter & Safety Parameters ----
#define MPU_ALPHA 0.98               // Complementary Filter Alpha
const float POT_EMA_ALPHA = 0.20f;   // Potentiometer Alpha
const float EMA_ALPHA = 0.10f;       // Ultrasonic Sensor Alpha
const float CRACK_RISE_CM = 1.5f;    // Crack Detection Threshold Trigger

const uint8_t PWM_MAX = 80;
const float PWM_DEADBAND = 30.0f;
const uint8_t START_KICK_PWM = PWM_MAX;
const unsigned long START_KICK_MS = 150;
const unsigned long STALL_WIN_MS = 1000;
const float STALL_MIN_MOVE_M = 0.02f;
const uint8_t STALL_MAX_TRY = 1;

const uint16_t ICR5_20KHZ = 800;     // 16MHz / (1 * 20kHz)
const uint16_t ICR5_2KHZ  = 8000;    // 16MHz / (1 * 2kHz)
const unsigned long START_FREQ_LO_MS = 400;

#endif // TRACK_ROBOT_HEADER_H