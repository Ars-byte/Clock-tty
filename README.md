# TTY-CLOCK (Python Port)

This script is a Python-based implementation of the original C-language TTY-CLOCK. It renders a digital clock interface within the terminal using the `curses` library.

## Functional Overview

* **Time Display**: Supports 12-hour (with AM/PM indicators) and 24-hour formats.
* **Visual Toggles**: Includes options for displaying seconds, drawing window borders, and enabling a blinking separator.
* **Rendering Engine**: Utilizes custom 5x3 bitmapped digit arrays to draw the clock face.
* **Motion Dynamics**:
* **Centered**: Locks the clock to the terminal midpoint.
* **Rebound**: Animates the clock to bounce off terminal boundaries.
* **Manual**: Permits coordinate adjustments via directional inputs.


* **Date Integration**: Features a configurable date string using standard `strftime` formatting.

---

## Execution

Requirements: **Python 3.x** and a Unix-like environment (Linux, macOS, WSL) providing the `curses` module.

1. Initialize execution permissions:
```bash
chmod +x clock.py

```


2. Launch the application:
```bash
python3 clock.py

```

<img width="737" height="234" alt="image" src="https://github.com/user-attachments/assets/a021fc1d-bbd8-43a8-9a0e-9ede1e49398b" />


### Argument Specifications

| Flag | Logic |
| --- | --- |
| -s | Append seconds to the display. |
| -t | Apply 12-hour clock logic. |
| -x | Render box borders. |
| -b | Apply bold text attributes. |
| -r | Enable boundary rebound animation. |
| -C [0-7] | Set initial color index (e.g., 1:Red, 2:Green). |
| -f "fmt" | Define custom `strftime` date structure. |

---

## Interactive Keybindings

Modify the interface state during runtime using the following inputs:

* **Q**: Terminate process.
* **S**: Toggle seconds display.
* **T**: Toggle 12/24-hour format.
* **C**: Toggle centering.
* **R**: Toggle rebound mode.
* **X**: Toggle borders.
* **B**: Toggle bold attributes.
* **Space / Tab**: Cycle forward through color pairs.
* **0-7**: Assign color index directly.
* **Arrows / HJKL**: Manual displacement (requires centering disabled).

---

## Technical Origin

* This port translates the original C logic (Copyright 2008-2018) into Python.
* Frame timing is managed via `stdscr.timeout`, defaulting to a 1-second refresh rate.
