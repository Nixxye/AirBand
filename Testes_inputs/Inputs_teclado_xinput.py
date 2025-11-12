import threading
import time
import sys
import tkinter as tk
import keyboard

try:
    import vgamepad as vg
except Exception as e:
    print("Erro ao importar vgamepad:", e)
    sys.exit(1)

# --- Inicializa o gamepad virtual ---
gamepad = vg.VX360Gamepad()
print("Gamepad virtual criado (VX360Gamepad).")

BUTTONS = {
    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
    "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
}

KEY_MAP = {
    "f1": "A",
    "f2": "B",
    "f3": "Y",
    "f4": "X",
}

button_state = {k: False for k in BUTTONS.keys()}

# --- Tkinter Visualização ---
root = tk.Tk()
root.title("XInput Visual")
root.geometry("300x150")
root.configure(bg="#1a1a1a")

labels = {}

def create_button_label(name, row, col):
    lbl = tk.Label(root, text=name, font=("Arial", 20, "bold"),
                   width=4, height=2, bg="#333", fg="white", relief="raised")
    lbl.grid(row=row, column=col, padx=10, pady=10)
    labels[name] = lbl

create_button_label("A", 1, 1)
create_button_label("B", 1, 2)
create_button_label("X", 0, 1)
create_button_label("Y", 0, 2)

# --- Funções para controlar os botões ---
def press_button(name):
    if button_state[name]:
        return
    button_state[name] = True
    gamepad.press_button(button=BUTTONS[name])
    gamepad.update()
    labels[name].config(bg="lime", relief="sunken")

def release_button(name):
    if not button_state[name]:
        return
    button_state[name] = False
    gamepad.release_button(button=BUTTONS[name])
    gamepad.update()
    labels[name].config(bg="#333", relief="raised")

# --- Listener de teclado em background ---
def keyboard_listener():
    while True:
        for key, btn in KEY_MAP.items():
            if keyboard.is_pressed(key):
                press_button(btn)
            else:
                release_button(btn)
        time.sleep(0.02)  # 50 FPS de atualização

threading.Thread(target=keyboard_listener, daemon=True).start()

# --- Encerramento seguro ---
def on_close():
    for b in BUTTONS:
        release_button(b)
    root.destroy()
    sys.exit(0)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()