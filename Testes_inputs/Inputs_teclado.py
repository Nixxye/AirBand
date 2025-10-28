# pip install pyautogui
# pip install keyboard
import pyautogui
import keyboard  # Biblioteca para ouvir o teclado em segundo plano
import time

print("--- Script de Teste com Hotkeys ---")
print("INSTRUÇÕES:")
print("1. Clique na janela do seu jogo ou Bloco de Notas para focar.")
print("2. Pressione as teclas F1, F2, F3 ou F4.")
print("\nMAPEAMENTO:")
print("   F1  ->  Envia 'a'")
print("   F2  ->  Envia 's'")
print("   F3  ->  Envia 'j'")
print("   F4  ->  Envia 'k'")
print("\n*** Pressione 'ESC' a qualquer momento para FECHAR o script. ***")

def send_key(key):
    """Função que envia o pressionamento da tecla"""
    print(f"Hotkey detectada! Enviando tecla: '{key}'")
    pyautogui.press(key)

# 1. Mapeia as 'hotkeys'
#    Quando 'f1' for pressionado, chame a função send_key('a')
#    'suppress=True' impede que a tecla 'F1' real também seja enviada.
try:
    keyboard.add_hotkey('f1', lambda: send_key('a'), suppress=True)
    keyboard.add_hotkey('f2', lambda: send_key('s'), suppress=True)
    keyboard.add_hotkey('f3', lambda: send_key('j'), suppress=True)
    keyboard.add_hotkey('f4', lambda: send_key('k'), suppress=True)

    # 2. Mantém o script rodando em segundo plano
    #    Ele ficará "travado" aqui, ouvindo as teclas,
    #    até você pressionar 'esc'.
    keyboard.wait('esc')

except PermissionError:
    print("\n[ERRO] Permissão negada.")
    print("Você precisa rodar este script como Administrador (ou 'sudo' no Linux/Mac)")
    print("para que ele possa controlar o teclado.")
    input("Pressione Enter para sair.")
except Exception as e:
    print(f"\nOcorreu um erro: {e}")

print("\nScript terminado.")