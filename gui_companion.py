import tkinter as tk
from tkinter import colorchooser, ttk

import serial
import serial.tools.list_ports


class TeensyCompanion:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Teensy LED Companion")
        self.ser = None

        self.port_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.mode_var = tk.StringVar(value="fixed")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.bri_var = tk.IntVar(value=35)
        self.base_rgb = (32, 110, 230)

        frame = ttk.Frame(root, padding=10)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Serial Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=30, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=4)
        ttk.Button(frame, text="Connect", command=self.connect).grid(row=0, column=3, padx=4)
        ttk.Button(frame, text="Disconnect", command=self.disconnect).grid(row=0, column=4, padx=4)

        ttk.Label(frame, textvariable=self.status_var).grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 10))

        ttk.Label(frame, text="Brightness").grid(row=2, column=0, sticky="w")
        bri = ttk.Scale(frame, from_=0, to=255, variable=self.bri_var, command=self.on_brightness)
        bri.grid(row=2, column=1, columnspan=4, sticky="ew")

        ttk.Label(frame, text="Tempo / Speed").grid(row=3, column=0, sticky="w")
        spd = ttk.Scale(frame, from_=0.2, to=3.0, variable=self.speed_var, command=self.on_speed)
        spd.grid(row=3, column=1, columnspan=4, sticky="ew")

        ttk.Label(frame, text="Color Mode").grid(row=4, column=0, sticky="w")
        mode_combo = ttk.Combobox(
            frame,
            textvariable=self.mode_var,
            values=["fixed", "pitch", "rainbow", "alternate"],
            state="readonly",
        )
        mode_combo.grid(row=4, column=1, sticky="w")
        mode_combo.bind("<<ComboboxSelected>>", self.on_mode)

        ttk.Button(frame, text="Pick Base Color", command=self.pick_color).grid(row=4, column=2, padx=4)
        ttk.Button(frame, text="Send HELP", command=lambda: self.send_line("HELP")).grid(row=4, column=3, padx=4)

        frame.columnconfigure(1, weight=1)
        self.refresh_ports()

    def refresh_ports(self) -> None:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def connect(self) -> None:
        if self.ser:
            return
        port = self.port_var.get().strip()
        if not port:
            self.status_var.set("No serial port selected.")
            return
        try:
            self.ser = serial.Serial(port, 115200, timeout=0.1)
            self.status_var.set(f"Connected: {port}")
            self.push_all_settings()
        except Exception as exc:
            self.status_var.set(f"Connect failed: {exc}")

    def disconnect(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.status_var.set("Disconnected")

    def send_line(self, line: str) -> None:
        if not self.ser:
            return
        try:
            self.ser.write((line + "\n").encode("utf-8"))
        except Exception as exc:
            self.status_var.set(f"Write failed: {exc}")

    def push_all_settings(self) -> None:
        self.send_line(f"BRI {int(self.bri_var.get())}")
        self.send_line(f"SPD {self.speed_var.get():.2f}")
        self.send_line(f"MODE {self.mode_var.get()}")
        r, g, b = self.base_rgb
        self.send_line(f"BASE {r} {g} {b}")

    def on_brightness(self, _evt=None) -> None:
        self.send_line(f"BRI {int(self.bri_var.get())}")

    def on_speed(self, _evt=None) -> None:
        self.send_line(f"SPD {self.speed_var.get():.2f}")

    def on_mode(self, _evt=None) -> None:
        self.send_line(f"MODE {self.mode_var.get()}")

    def pick_color(self) -> None:
        chosen = colorchooser.askcolor(
            color="#%02x%02x%02x" % self.base_rgb,
            title="Pick base note color",
            parent=self.root,
        )
        if chosen and chosen[0] is not None:
            r, g, b = [int(v) for v in chosen[0]]
            self.base_rgb = (r, g, b)
            self.send_line(f"BASE {r} {g} {b}")


if __name__ == "__main__":
    app = tk.Tk()
    TeensyCompanion(app)
    app.mainloop()
