#!/usr/bin/env python3

import sys


VOLTAGE_CURVE = [
    (4.20, 100),
    (4.10, 90),
    (4.00, 80),
    (3.90, 70),
    (3.85, 60),
    (3.80, 50),
    (3.70, 40),
    (3.60, 25),
    (3.50, 10),
    (3.30, 0),
]


def voltage_to_percent(voltage: float) -> float:
    """Piecewise-linear interpolation over the reference discharge curve."""
    if voltage >= VOLTAGE_CURVE[0][0]:
        return 100.0
    if voltage <= VOLTAGE_CURVE[-1][0]:
        return 0.0

    for (v_high, p_high), (v_low, p_low) in zip(VOLTAGE_CURVE, VOLTAGE_CURVE[1:]):
        if v_low <= voltage <= v_high:
            # Linear interpolation between the two bracketing points
            fraction = (voltage - v_low) / (v_high - v_low)
            return p_low + fraction * (p_high - p_low)

    return 0.0  # fallback, shouldn't be reached


def main():
    args = sys.argv[1:]

    if len(args) >= 1:
        try:
            voltage = float(args[0])
        except ValueError:
            print(f"Invalid voltage value: {args[0]}")
            sys.exit(1)
    else:
        raw = input("Enter measured battery voltage (V): ").strip()
        try:
            voltage = float(raw)
        except ValueError:
            print(f"Invalid voltage value: {raw}")
            sys.exit(1)

    if voltage < 2.5 or voltage > 4.3:
        print(f"Warning: {voltage:.2f}V is outside the normal Li-ion range (3.0V-4.2V).")
        print("Double-check your measurement or battery type.\n")

    percent = voltage_to_percent(voltage)

    # Optional: rated capacity, to also show estimated remaining mAh
    rated_mah = None
    if len(args) >= 2:
        try:
            rated_mah = float(args[1])
        except ValueError:
            rated_mah = None

    print(f"Measured voltage : {voltage:.2f} V")
    print(f"Your battery is {percent:.0f}%")

    if rated_mah:
        remaining_mah = rated_mah * (percent / 100.0)
        print(f"Estimated remaining capacity: {remaining_mah:.0f} mAh (of {rated_mah:.0f} mAh rated)")


if __name__ == "__main__":
    main()
