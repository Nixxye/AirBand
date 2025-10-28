# pip install vgamepad 
# instalar o driver em : https://github.com/nefarius/ViGEmBus/releases
import tkinter as tk
import vgamepad as vg
import sys

try:
    # 1. Cria um objeto de gamepad XInput
    gamepad = vg.VX360Gamepad()
    print("Controle de Xbox 360 virtual criado com sucesso!")
    print("Vá em https://gamepad-tester.com/ para ver funcionando.")
    
except Exception as e:
    print(f"Erro ao inicializar o ViGEmBus: {e}")
    print("Certifique-se de que o driver ViGEmBus está instalado.")
    sys.exit()


# --- Novas Funções de Evento (Press e Release) ---

def on_press_button(button_obj):
    """Pressiona um botão do gamepad e ATUALIZA."""
    print(f"Press: {button_obj}")
    gamepad.press_button(button=button_obj)
    gamepad.update()

def on_release_button(button_obj):
    """Solta um botão do gamepad e ATUALIZA."""
    print(f"Release: {button_obj}")
    gamepad.release_button(button=button_obj)
    gamepad.update()

def on_press_trigger(trigger_func_ref):
    """Pressiona um gatilho (analógico 100%) e ATUALIZA."""
    print(f"Press Trigger")
    trigger_func_ref(value_float=1.0) # Pressiona 100%
    gamepad.update()

def on_release_trigger(trigger_func_ref):
    """Solta um gatilho (analógico 0%) e ATUALIZA."""
    print(f"Release Trigger")
    trigger_func_ref(value_float=0.0) # Solta 0%
    gamepad.update()

def on_press_stick(stick_func_ref, x, y):
    """Move um analógico para uma direção e ATUALIZA."""
    print(f"Move Stick: x={x}, y={y}")
    stick_func_ref(x_value_float=x, y_value_float=y)
    gamepad.update()

def on_release_stick(stick_func_ref):
    """Centraliza o analógico e ATUALIZA."""
    print(f"Center Stick")
    stick_func_ref(x_value_float=0.0, y_value_float=0.0)
    gamepad.update()

# --- Configuração da Janela Principal ---
root = tk.Tk()
root.title("Simulador Completo de Xbox 360 (ViGEmBus)")
root.geometry("550x450")
root.columnconfigure(0, weight=1)
root.columnconfigure(1, weight=1)
root.columnconfigure(2, weight=1)

# --- Frame dos Botões Superiores (LB, RB, LT, RT, Guide) ---
frame_top_buttons = tk.Frame(root)
frame_top_buttons.grid(row=0, column=0, columnspan=3, pady=10)

# LT (Gatilho Esquerdo)
btn_lt = tk.Button(frame_top_buttons, text="LT", width=10, height=2)
btn_lt.bind("<ButtonPress-1>", lambda event: on_press_trigger(gamepad.left_trigger_float))
btn_lt.bind("<ButtonRelease-1>", lambda event: on_release_trigger(gamepad.left_trigger_float))

# LB (Shoulder Esquerdo)
btn_lb = tk.Button(frame_top_buttons, text="LB", width=10, height=2)
btn_lb.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER))
btn_lb.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER))

# GUIDE
btn_guide = tk.Button(frame_top_buttons, text="GUIDE", width=10, height=2, bg="#333", fg="#FFF")
btn_guide.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE))
btn_guide.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE))

# RB (Shoulder Direito)
btn_rb = tk.Button(frame_top_buttons, text="RB", width=10, height=2)
btn_rb.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER))
btn_rb.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER))

# RT (Gatilho Direito)
btn_rt = tk.Button(frame_top_buttons, text="RT", width=10, height=2)
btn_rt.bind("<ButtonPress-1>", lambda event: on_press_trigger(gamepad.right_trigger_float))
btn_rt.bind("<ButtonRelease-1>", lambda event: on_release_trigger(gamepad.right_trigger_float))

btn_lt.pack(side=tk.LEFT, padx=5)
btn_lb.pack(side=tk.LEFT, padx=5)
btn_guide.pack(side=tk.LEFT, padx=15)
btn_rb.pack(side=tk.LEFT, padx=5)
btn_rt.pack(side=tk.LEFT, padx=5)


# --- Frame do Left Stick (LS) ---
frame_ls = tk.LabelFrame(root, text="Left Stick", padx=10, pady=10)
frame_ls.grid(row=1, column=0, sticky="n", padx=10, pady=10)

btn_ls_up = tk.Button(frame_ls, text="Up", width=6)
btn_ls_up.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.left_joystick_float, x=0.0, y=1.0))
btn_ls_up.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.left_joystick_float))

btn_ls_left = tk.Button(frame_ls, text="Left", width=6)
btn_ls_left.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.left_joystick_float, x=-1.0, y=0.0))
btn_ls_left.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.left_joystick_float))

btn_l3 = tk.Button(frame_ls, text="L3", width=6)
btn_l3.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB))
btn_l3.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB))

btn_ls_right = tk.Button(frame_ls, text="Right", width=6)
btn_ls_right.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.left_joystick_float, x=1.0, y=0.0))
btn_ls_right.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.left_joystick_float))

btn_ls_down = tk.Button(frame_ls, text="Down", width=6)
btn_ls_down.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.left_joystick_float, x=0.0, y=-1.0))
btn_ls_down.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.left_joystick_float))

btn_ls_up.grid(row=0, column=1)
btn_ls_left.grid(row=1, column=0)
btn_l3.grid(row=1, column=1)
btn_ls_right.grid(row=1, column=2)
btn_ls_down.grid(row=2, column=1)


# --- Frame Central (Back/Start) ---
frame_center = tk.LabelFrame(root, text="Center", padx=10, pady=10)
frame_center.grid(row=1, column=1, sticky="n", pady=10)

btn_back = tk.Button(frame_center, text="Back", width=8)
btn_back.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK))
btn_back.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK))

btn_start = tk.Button(frame_center, text="Start", width=8)
btn_start.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START))
btn_start.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_START))

btn_back.pack(side=tk.LEFT, padx=5)
btn_start.pack(side=tk.LEFT, padx=5)


# --- Frame dos Botões ABXY ---
frame_abxy = tk.LabelFrame(root, text="ABXY", padx=10, pady=10)
frame_abxy.grid(row=1, column=2, sticky="n", padx=10, pady=10)

btn_y = tk.Button(frame_abxy, text="Y", width=6, bg="#FFFFE0")
btn_y.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y))
btn_y.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y))

btn_x = tk.Button(frame_abxy, text="X", width=6, bg="#ADD8E6")
btn_x.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X))
btn_x.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_X))

btn_b = tk.Button(frame_abxy, text="B", width=6, bg="#FFB6C1")
btn_b.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B))
btn_b.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B))

btn_a = tk.Button(frame_abxy, text="A", width=6, bg="#90EE90")
btn_a.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A))
btn_a.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A))

btn_y.grid(row=0, column=1)
btn_x.grid(row=1, column=0)
btn_b.grid(row=1, column=2)
btn_a.grid(row=2, column=1)


# --- Frame do D-Pad ---
frame_dpad = tk.LabelFrame(root, text="D-Pad", padx=10, pady=10)
frame_dpad.grid(row=2, column=0, sticky="n", padx=10, pady=10)

btn_d_up = tk.Button(frame_dpad, text="Up", width=6)
btn_d_up.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP))
btn_d_up.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP))

btn_d_left = tk.Button(frame_dpad, text="Left", width=6)
btn_d_left.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT))
btn_d_left.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT))

btn_d_right = tk.Button(frame_dpad, text="Right", width=6)
btn_d_right.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT))
btn_d_right.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT))

btn_d_down = tk.Button(frame_dpad, text="Down", width=6)
btn_d_down.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN))
btn_d_down.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN))

btn_d_up.grid(row=0, column=1)
btn_d_left.grid(row=1, column=0)
btn_d_right.grid(row=1, column=2)
btn_d_down.grid(row=2, column=1)


# --- Frame do Right Stick (RS) ---
frame_rs = tk.LabelFrame(root, text="Right Stick", padx=10, pady=10)
frame_rs.grid(row=2, column=2, sticky="n", padx=10, pady=10)

btn_rs_up = tk.Button(frame_rs, text="Up", width=6)
btn_rs_up.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.right_joystick_float, x=0.0, y=1.0))
btn_rs_up.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.right_joystick_float))

btn_rs_left = tk.Button(frame_rs, text="Left", width=6)
btn_rs_left.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.right_joystick_float, x=-1.0, y=0.0))
btn_rs_left.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.right_joystick_float))

btn_r3 = tk.Button(frame_rs, text="R3", width=6)
btn_r3.bind("<ButtonPress-1>", lambda event: on_press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB))
btn_r3.bind("<ButtonRelease-1>", lambda event: on_release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB))

btn_rs_right = tk.Button(frame_rs, text="Right", width=6)
btn_rs_right.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.right_joystick_float, x=1.0, y=0.0))
btn_rs_right.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.right_joystick_float))

btn_rs_down = tk.Button(frame_rs, text="Down", width=6)
btn_rs_down.bind("<ButtonPress-1>", lambda event: on_press_stick(gamepad.right_joystick_float, x=0.0, y=-1.0))
btn_rs_down.bind("<ButtonRelease-1>", lambda event: on_release_stick(gamepad.right_joystick_float))

btn_rs_up.grid(row=0, column=1)
btn_rs_left.grid(row=1, column=0)
btn_r3.grid(row=1, column=1)
btn_rs_right.grid(row=1, column=2)
btn_rs_down.grid(row=2, column=1)


# --- Função de Encerramento ---
def on_closing():
    """Chamada quando a janela é fechada."""
    print("Fechando a GUI e resetando o gamepad...")
    gamepad.reset()
    gamepad.update()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# --- Inicia a aplicação ---
print("Iniciando a GUI...")
root.mainloop()