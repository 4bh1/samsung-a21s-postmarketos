# Power Management, S2MU106 PMIC & Watchdog Architecture

> [!NOTE]
> **PMIC:** Samsung S2MU106 Power Management IC  
> **Interface:** I2C Bus (`/dev/i2c-12` or sysfs driver)  
> **Watchdog:** Samsung S3C2410 Watchdog (`/dev/watchdog`) & Softdog  

---

## 1. Battery Swelling Prevention (Charge Hysteresis)

Running an Exynos 850 phone 24/7 as a headless server with a battery kept at 100% State of Charge (SoC) leads to accelerated electrolyte degradation and battery swelling.

### The Solution: Register Hysteresis (50% – 70%)
The `s2mu106-battery-manager.service` daemon monitors battery voltage, current, and SoC:

```mermaid
stateDiagram-v2
    [*] --> Charging : SoC <= 50%
    Charging --> BuckOnly : SoC >= 70%
    BuckOnly --> Charging : SoC <= 50%
    
    state Charging {
        Mode : Charger Register 0x18 = 0x03
        Current : Normal CC/CV Charging (~1400 mA)
    }
    
    state BuckOnly {
        Mode : Charger Register 0x18 = 0x01
        Current : 0 mA Battery Current (Running directly on USB VBUS)
    }
```

1. **At $\ge 70\%$ SoC:** The daemon sets charger control register `0x18` to **`0x01` (Buck-Only mode)**:
   - The device draws all system power directly from the 5V USB VBUS power rail.
   - Charging current drops to **0 mA**.
   - Battery voltage stabilizes around 3.9V – 4.0V, preventing cell swelling.
2. **At $\le 50\%$ SoC:** The daemon toggles register `0x18` back to **`0x03` (Charging Enabled)** until 70% is reached.

---

## 2. Eliminating Charger Watchdog Suspensions (`WD_SUSPEND`)

The S2MU106 PMIC features a hardware charger watchdog timer (`REG_CHG_CTRL12` at register `0x24`):
- When this timer expires (due to missing proprietary Samsung Android healthd pings), the charger enters `WD_SUSPEND` state (`STATUS1` bits 7:4 = 1 or 2).
- When suspended, charging halts completely, causing the phone to discharge even while plugged in.

### Fix:
In both `s2mu106-switch.py` and `s2mu106-battery-manager.py`:
```python
# Kick watchdog timer, then permanently disable it
self.write_reg(ADDR_CHG, 0x24, 0x01) # Kick
self.write_reg(ADDR_CHG, 0x24, 0x00) # Disable watchdog timer
```
The daemon actively maintains this register across USB re-plugs and wall charger changes.

---

## 3. Kernel Watchdog & Hung Task Panics

Samsung downstream kernels are built with aggressive kernel debugging mechanisms that panic on soft task delays or unhandled watchdog intervals.

### Mitigations:
1. **Disabling Hung Task Panic:**
   In `/usr/bin/init`:
   ```sh
   sysctl -w kernel.hung_task_panic=0 kernel.hung_task_timeout_secs=0 2>/dev/null || true
   ```
2. **Dedicated Watchdog Petter:**
   `/usr/bin/watchdog-petter.py` runs as an independent daemon started by `/usr/bin/init` before systemd:
   - Continuously writes keepalive bytes to `/dev/watchdog`.
   - Prevents hardware reboot loops if userland experiences temporary high CPU load during initialization.
