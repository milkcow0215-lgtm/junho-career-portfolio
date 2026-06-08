// ============================================================================
// File: main_control.ino
// Description: Main Executive Loop, Multi-rate Task Scheduling, and Control
// Project: Autonomous Railway Inspection Robot System (Graduation Project)
// ============================================================================

#include "TrackRobot_Header.h"

// ---- IMU & Filter States ----
Adafruit_MPU6050 mpu;
float roll_comp = 0.0f, pitch_comp = 0.0f, yaw_comp = 0.0f;
float gyroRoll = 0, gyroPitch = 0, gyroYaw = 0;
unsigned long last_time_mpu = 0;
float dt_mpu = 0.0f;

// ---- Calibration Windows ----
float y_off = 0, y_acc = 0;
bool gyroZeroReady = false;
int zero_cnt = 0;
unsigned long zeroStartMs = 0;
const unsigned long ZERO_WARMUP_MS = 1000;

// ---- Sensor State Variables ----
volatile long encoderCount = 0;
float potBase[4] = {0, 0, 0, 0};
float rawPL1 = 0, rawPL2 = 0, rawPR1 = 0, rawPR2 = 0;
float dPL1 = 0, dPL2 = 0, dPR1 = 0, dPR2 = 0;
float angPL1_deg = 0, angPL2_deg = 0, angPR1_deg = 0, angPR2_deg = 0;
float pl1_ema_deg = 0, pl2_ema_deg = 0, pr1_ema_deg = 0, pr2_ema_deg = 0;
float ulL_cm = -1, ulR_cm = -1, emaL = -1, emaR = -1;
bool potEmaInit = false;
bool armAbnormalState = false;
bool crackLatched = false;

// ---- Actuator & Sequence States ----
bool motorEnabled = false;
bool prevMotorEnabled = false;
bool desiredFwd = true;
bool currentFwd = true;
float pwmCmd = 30.0f;
float pwmTarget = 80.0f;
float pwmRamp_per_s = 23.0f;
const float DIR_SWITCH_THRESHOLD = 4.0f;

unsigned long lastCtrlMs = 0;
const unsigned long ctrlPeriodMs = 50;     // 20 Hz Motor Loop
unsigned long lastSenseMs = 0;
const unsigned long sensePeriodMs = 20;    // 50 Hz Sensor Loop
unsigned long lastCsvMs = 0;
const unsigned long csvPeriodMs = 20;     // 50 Hz Telemetry Log
unsigned long lastPrintMs = 0;
const unsigned long printPeriodMs = 1000;  // 1 Hz Debug Print

// ---- Watchdog & Safety Windows ----
unsigned long kickUntilMs = 0;
unsigned long pwmFreqRestoreAtMs = 0;
unsigned long lastBtCmdMs = 0;
unsigned long lastMoveChkMs = 0;
long lastEncMove = 0;
unsigned long stallGraceUntilMs = 0;
uint8_t stallTry = 0;

// ---- Encoder & Timer Setup ----
void ISR_encoder() { if (digitalRead(encoderPinB)) encoderCount--; else encoderCount++; }
long atomicReadEncoder() { noInterrupts(); long v = encoderCount; interrupts(); return v; }
long stallMinCounts() { return (long)ceil(STALL_MIN_MOVE_M / meterPerCount); }

void setupTimer5(uint16_t top) {
  TCCR5A = 0; TCCR5B = 0; TCNT5 = 0;
  TCCR5A |= (1 << WGM51);
  TCCR5B |= (1 << WGM53) | (1 << WGM52); // Fast PWM Mode 14
  TCCR5A |= (1 << COM5A1) | (1 << COM5B1); // Non-Inverting
  ICR5 = top;
  TCCR5B |= (1 << CS50); // Prescaler = 1
  OCR5A = 0; OCR5B = 0;
}

// ---- Oversampling ADC ----
float readADC_oversampled(uint8_t pin, uint8_t N = 16) {
  long s = 0; analogRead(pin);
  for (uint8_t i = 0; i < N; i++) s += analogRead(pin);
  return (float)s / (float)N;
}

// ---- Ultrasonic Ping ----
float readUltrasonic_cm(int trig, int echo) {
  digitalWrite(trig, LOW); delayMicroseconds(2);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long dur = pulseIn(echo, HIGH, 10000UL);
  if (!dur) return -1.0f;
  return dur * 0.0343f / 2.0f;
}

// ---- H-Bridge Control ----
inline uint16_t map255_to_ICR(uint8_t duty) { return (uint16_t)((uint32_t)duty * ICR5 / 255UL); }
inline void motorWriteRaw(uint8_t dutyRPWM, uint8_t dutyLPWM) {
  OCR5B = map255_to_ICR(dutyRPWM); // Pin 45
  OCR5A = map255_to_ICR(dutyLPWM); // Pin 46
}
inline void motorCoast() { motorWriteRaw(0, 0); }
inline void motorSetDir(bool fwd) { currentFwd = fwd; }
void motorWrite(uint8_t duty, bool fwd) {
  if (duty == 0) { motorCoast(); return; }
  if (fwd) motorWriteRaw(duty, 0);
  else     motorWriteRaw(0, duty);
}

// ---- Telemetry Utilities ----
void sendEvent(float dist_m, const char* tag) {
  Serial2.print(dist_m, 2); Serial2.print('@'); Serial2.print(tag); Serial2.print('\n'); // BT
  Serial .print(dist_m, 2); Serial .print('@'); Serial .print(tag); Serial .print('\n'); // USB PC
}

void handleInput(Stream& io) {
  while (io.available()) {
    char ch = io.read();
    if (ch == '\n' || ch == '\r' || ch == ' ') continue;
    lastBtCmdMs = millis();
    if (ch == '0') {
      motorEnabled = false; pwmCmd = 0; motorCoast();
      if (currentFwd != desiredFwd) { motorSetDir(desiredFwd); }
    }
    else if (ch == 'f' || ch == 'F') { desiredFwd = true;  motorEnabled = true; }
    else if (ch == 'b' || ch == 'B') { desiredFwd = false; motorEnabled = true; }
    else if (ch == 'z' || ch == 'Z') {
      y_off = yaw_comp; gyroZeroReady = true;
    }
  }
}

void csv_sendHeader() {
  Serial.println(F("dist_m,ul_L_cm,ul_R_cm,PL1_deg,PL2_deg,PR1_deg,PR2_deg,roll_deg,pitch_deg,yaw_deg,event"));
}

void csv_sendRow(float dist_m, float ulL, float ulR, float aPL1, float aPL2, float aPR1, float aPR2, float r_deg, float p_deg, float y_deg, const char* ev) {
  Serial.print(dist_m, 3);    Serial.print(',');
  Serial.print(ulL, 1);       Serial.print(',');
  Serial.print(ulR, 1);       Serial.print(',');
  Serial.print(aPL1, 1);      Serial.print(',');
  Serial.print(aPL2, 1);      Serial.print(',');
  Serial.print(aPR1, 1);      Serial.print(',');
  Serial.print(aPR2, 1);      Serial.print(',');
  Serial.print(r_deg, 2);     Serial.print(',');
  Serial.print(p_deg, 2);     Serial.print(',');
  Serial.print(y_deg, 2);     Serial.print(',');
  Serial.println(ev);
}

void printStatusTo(Stream& io, float distL, float distR, float aPL1, float aPL2, float aPR1, float aPR2, long c, float m, bool armAbnormal) {
  io.println(F("---- STATUS REPORT ----"));
  io.print(F("[ULTRA] L(cm): ")); io.print(distL, 1); io.print(F(" | R(cm): ")); io.println(distR, 1);
  io.print(F("[ENC] Count: ")); io.print(c); io.print(F(" | Distance(m): ")); io.println(m, 3);
  io.print(F("[IMU] Roll: ")); io.print(gyroRoll, 2); io.print(F(" | Pitch: ")); io.print(gyroPitch, 2); io.print(F(" | Yaw: ")); io.println(gyroYaw, 2);
  io.println(armAbnormal ? F("[ALERT] STRUCTURE TWIST DETECTED") : F("[STATUS] STRUCTURAL NORMAL"));
  io.println();
}

// ---- Main Executive ----
void setup() {
  Serial.begin(115200);
  Serial2.begin(9600); // Bluetooth Link
  Wire.begin();        // I2C Hardware Bus (Pins 20, 21)

  if (!mpu.begin()) {
    Serial.println(F("MPU-6050 Verification Failed!"));
    while (1) delay(10);
  }
  last_time_mpu = micros();

  pinMode(PIN_PL1, INPUT); pinMode(PIN_PL2, INPUT);
  pinMode(PIN_PR1, INPUT); pinMode(PIN_PR2, INPUT);
  pinMode(TRIG_L, OUTPUT); pinMode(ECHO_L, INPUT);
  pinMode(TRIG_R, OUTPUT); pinMode(ECHO_R, INPUT);
  pinMode(PIN_R_EN, OUTPUT); pinMode(PIN_L_EN, OUTPUT);
  pinMode(PIN_RPWM, OUTPUT); pinMode(PIN_LPWM, OUTPUT);

  digitalWrite(PIN_R_EN, HIGH);
  digitalWrite(PIN_L_EN, HIGH);
  setupTimer5(ICR5_20KHZ);
  motorSetDir(true);
  motorCoast();

  pinMode(encoderPinA, INPUT_PULLUP);
  pinMode(encoderPinB, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(encoderPinA), ISR_encoder, RISING);

  delay(300);
  potBase[0] = readADC_oversampled(PIN_PL1, 32);
  potBase[1] = readADC_oversampled(PIN_PL2, 32);
  potBase[2] = readADC_oversampled(PIN_PR1, 32);
  potBase[3] = readADC_oversampled(PIN_PR2, 32);

  lastCtrlMs = lastSenseMs = lastMoveChkMs = zeroStartMs = millis();
  lastEncMove = atomicReadEncoder();
  csv_sendHeader();
}

void loop() {
  unsigned long now = millis();

  handleInput(Serial);
  handleInput(Serial2);

  // Task 1: Sensor Interrogation & State Machine Updates (50 Hz)
  if (now - lastSenseMs >= sensePeriodMs) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    unsigned long current_time = micros();
    dt_mpu = (float)(current_time - last_time_mpu) / 1000000.0f;
    last_time_mpu = current_time;

    float roll_accel  = atan2(a.acceleration.y, a.acceleration.z) * 180.0f / (float)M_PI;
    float pitch_accel = atan2(-a.acceleration.x, sqrt(a.acceleration.y * a.acceleration.y + a.acceleration.z * a.acceleration.z)) * 180.0f / (float)M_PI;

    roll_comp  = MPU_ALPHA * (roll_comp  + (g.gyro.x * 180.0f / (float)M_PI) * dt_mpu) + (1.0f - MPU_ALPHA) * roll_accel;
    pitch_comp = MPU_ALPHA * (pitch_comp + (g.gyro.y * 180.0f / (float)M_PI) * dt_mpu) + (1.0f - MPU_ALPHA) * pitch_accel;
    yaw_comp  += (g.gyro.z * 180.0f / (float)M_PI) * dt_mpu;

    if (!gyroZeroReady) {
      if (now - zeroStartMs <= ZERO_WARMUP_MS) {
        y_acc += yaw_comp; zero_cnt++;
      } else {
        if (zero_cnt > 0) y_off = y_acc / zero_cnt;
        gyroZeroReady = true;
      }
    }

    gyroRoll  = roll_comp;
    gyroPitch = pitch_comp;
    gyroYaw   = gyroZeroReady ? (yaw_comp - y_off) : yaw_comp;

    ulL_cm = readUltrasonic_cm(TRIG_L, ECHO_L);
    ulR_cm = readUltrasonic_cm(TRIG_R, ECHO_R);

    rawPL1 = readADC_oversampled(PIN_PL1, 16); dPL1 = rawPL1 - potBase[0];
    rawPL2 = readADC_oversampled(PIN_PL2, 16); dPL2 = rawPL2 - potBase[1];
    rawPR1 = readADC_oversampled(PIN_PR1, 16); dPR1 = rawPR1 - potBase[2];
    rawPR2 = readADC_oversampled(PIN_PR2, 16); dPR2 = rawPR2 - potBase[3];

    angPL1_deg = potSign[0] * dPL1 * degreePerStep;
    angPL2_deg = potSign[1] * dPL2 * degreePerStep;
    angPR1_deg = potSign[2] * dPR1 * degreePerStep;
    angPR2_deg = potSign[3] * dPR2 * degreePerStep;

    if (!potEmaInit) {
      pl1_ema_deg = angPL1_deg; pl2_ema_deg = angPL2_deg;
      pr1_ema_deg = angPR1_deg; pr2_ema_deg = angPR2_deg;
      potEmaInit = true;
    } else {
      pl1_ema_deg = (1.0f - POT_EMA_ALPHA) * pl1_ema_deg + POT_EMA_ALPHA * angPL1_deg;
      pl2_ema_deg = (1.0f - POT_EMA_ALPHA) * pl2_ema_deg + POT_EMA_ALPHA * angPL2_deg;
      pr1_ema_deg = (1.0f - POT_EMA_ALPHA) * pr1_ema_deg + POT_EMA_ALPHA * angPR1_deg;
      pr2_ema_deg = (1.0f - POT_EMA_ALPHA) * pr2_ema_deg + POT_EMA_ALPHA * angPR2_deg;
    }

    if (ulL_cm > 0) emaL = (emaL < 0) ? ulL_cm : (1 - EMA_ALPHA) * emaL + EMA_ALPHA * ulL_cm;
    if (ulR_cm > 0) emaR = (emaR < 0) ? ulR_cm : (1 - EMA_ALPHA) * emaR + EMA_ALPHA * ulR_cm;

    float riseL = (emaL > 0 && ulL_cm > 0) ? (ulL_cm - emaL) : 0;
    float riseR = (emaR > 0 && ulR_cm > 0) ? (ulR_cm - emaR) : 0;
    bool crackNow = (riseL > CRACK_RISE_CM) || (riseR > CRACK_RISE_CM);

    static bool armEventLatched = false;
    bool armAbnormal = (fabsf(pl1_ema_deg) > tolerance_deg) || (fabsf(pl2_ema_deg) > tolerance_deg) ||
                       (fabsf(pr1_ema_deg) > tolerance_deg) || (fabsf(pr2_ema_deg) > tolerance_deg);
    armAbnormalState = armAbnormal;

    if (crackNow && !crackLatched) { sendEvent((float)atomicReadEncoder() * meterPerCount, "CRACK"); crackLatched = true; }
    if (!crackNow) crackLatched = false;
    if (armAbnormal && !armEventLatched) { sendEvent((float)atomicReadEncoder() * meterPerCount, "TWIST"); armEventLatched = true; }
    if (!armAbnormal) armEventLatched = false;

    lastSenseMs = now;
  }

  // Task 2: Closed-loop Speed Profiling & Safety Watchdog (20 Hz)
  if (now - lastCtrlMs >= ctrlPeriodMs) {
    float dt = (now - lastCtrlMs) / 1000.0f;

    if (motorEnabled && !prevMotorEnabled) {
      if (pwmCmd < PWM_DEADBAND) pwmCmd = PWM_DEADBAND;
      kickUntilMs = now + START_KICK_MS;
      stallTry = 0; lastMoveChkMs = now; lastEncMove = atomicReadEncoder();
      stallGraceUntilMs = now + 2000;
      setupTimer5(ICR5_2KHZ); // Torque Enhancement
      pwmFreqRestoreAtMs = now + START_FREQ_LO_MS;
    }
    prevMotorEnabled = motorEnabled;

    if (currentFwd != desiredFwd) {
      if (pwmCmd > DIR_SWITCH_THRESHOLD) {
        pwmCmd = fmaxf_local(0.0f, pwmCmd - (pwmRamp_per_s * dt));
        motorWrite((uint8_t)pwmCmd, currentFwd);
      } else {
        motorCoast(); motorSetDir(desiredFwd); currentFwd = desiredFwd;
        if (motorEnabled) {
          if (pwmCmd < PWM_DEADBAND) pwmCmd = PWM_DEADBAND;
          kickUntilMs = now + START_KICK_MS; stallGraceUntilMs = now + 1500;
          setupTimer5(ICR5_2KHZ); pwmFreqRestoreAtMs = now + START_FREQ_LO_MS;
        }
      }
    } else if (motorEnabled) {
      float step = pwmRamp_per_s * dt;
      if      (pwmCmd + step < pwmTarget) pwmCmd += step;
      else if (pwmCmd > pwmTarget + step) pwmCmd -= step;
      else                                pwmCmd  = pwmTarget;

      uint8_t outPWM = (uint8_t)constrain(pwmCmd, 0.0f, (float)PWM_MAX);
      if (now < kickUntilMs && outPWM < START_KICK_PWM) outPWM = START_KICK_PWM;
      motorWrite(outPWM, currentFwd);

      if (now >= stallGraceUntilMs && (now - lastMoveChkMs >= STALL_WIN_MS)) {
        long ec = atomicReadEncoder();
        if (labs(ec - lastEncMove) < stallMinCounts()) {
          if (stallTry < STALL_MAX_TRY) {
            stallTry++; pwmCmd = fminf_local((float)PWM_MAX, pwmCmd + 10.0f); pwmTarget = pwmCmd;
          } else {
            motorEnabled = false; motorCoast();
          }
        }
        lastEncMove = ec; lastMoveChkMs = now;
      }
    } else {
      motorCoast();
    }
    lastCtrlMs = now;
  }

  // Task 3: PWM Frequency Adaptive Restoration (2kHz -> 20kHz)
  if (pwmFreqRestoreAtMs && now >= pwmFreqRestoreAtMs) {
    setupTimer5(ICR5_20KHZ);
    pwmFreqRestoreAtMs = 0;
  }

  // Task 4: High-speed Telemetry Transmission (50 Hz)
  if (now - lastCsvMs >= csvPeriodMs) {
    csv_sendRow(atomicReadEncoder() * meterPerCount, ulL_cm, ulR_cm, angPL1_deg, angPL2_deg, angPR1_deg, angPR2_deg, gyroRoll, gyroPitch, gyroYaw, crackLatched ? "CRACK" : "");
    lastCsvMs = now;
  }

  // Task 5: Human-Readable Monitoring (1 Hz)
  if (now - lastPrintMs >= printPeriodMs) {
    printStatusTo(Serial, ulL_cm, ulR_cm, angPL1_deg, angPL2_deg, angPR1_deg, angPR2_deg, atomicReadEncoder(), atomicReadEncoder() * meterPerCount, armAbnormalState);
    lastPrintMs = now;
  }
}