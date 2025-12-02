from typing import List, Dict, Union

try:
    import vgamepad as vg
    _VGAMEPAD_DISPONIVEL = True
except ImportError:
    _VGAMEPAD_DISPONIVEL = False

try:
    import keyboard
    _KEYBOARD_DISPONIVEL = True
except ImportError:
    _KEYBOARD_DISPONIVEL = False

class Emulator:
    _instance = None
    _is_initialized = False # Flag para garantir que o __init__ rode apenas uma vez

    # --- Configuração de Mapeamento ---
    # Os indices correspondem à ordem da entrada: [Verde, Vermelho, Amarelo, Azul]
    BOTOES = ["Verde", "Vermelho", "Amarelo", "Azul"]
    
    # Mapeamento do Controle (A, B, Y, X)
    MAP_CONTROLE: Dict[str, vg.XUSB_BUTTON] = {
        "Verde": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "Vermelho": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "Amarelo": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "Azul": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
    }
    
    # Mapeamento do Teclado (a, s, j, k)
    MAP_TECLADO: Dict[str, str] = {
        "Verde": "a",
        "Vermelho": "s",
        "Amarelo": "j",
        "Azul": "k",
    }
    
    # Tipos de emulação aceitos
    TIPO_CONTROLE = "controle"
    TIPO_TECLADO = "teclado"

    def __new__(cls, *args, **kwargs):
        """Garante que apenas uma instância da classe seja criada."""
        if cls._instance is None:
            cls._instance = super(Emulator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Inicializa os atributos da instância, roda apenas uma vez."""
        if self._is_initialized:
            return

        self.tipo_emulacao: str = self.TIPO_CONTROLE
        self.estado_anterior: List[int] = [0, 0, 0, 0] # [Verde, Vermelho, Amarelo, Azul]
        
        self.gamepad = None
        if _VGAMEPAD_DISPONIVEL:
            try:
                self.gamepad = vg.VX360Gamepad()
                print("Gamepad virtual criado (VX360Gamepad).")
            except Exception as e:
                print(f"Erro ao inicializar vgamepad: {e}")
                self.gamepad = None

        if not _KEYBOARD_DISPONIVEL:
            print("Aviso: A biblioteca 'keyboard' não está disponível. Emulação de teclado pode ser limitada.")
        self._is_initialized = True

    def set_tipo_emulacao(self, tipo: str):
        """Define o tipo de emulação: 'controle' ou 'teclado'."""
        if tipo not in [self.TIPO_CONTROLE, self.TIPO_TECLADO]:
            raise ValueError(f"Tipo de emulação inválido: '{tipo}'. Use '{self.TIPO_CONTROLE}' ou '{self.TIPO_TECLADO}'.")
        
        if self.tipo_emulacao == tipo:
            return

        self._reset_botoes_atuais()
        
        self.tipo_emulacao = tipo
        print(f"\nTipo de emulação alterado para: {self.tipo_emulacao}")

    def _get_mapeamento(self) -> Dict[str, Union[vg.XUSB_BUTTON, str]]:
        """Retorna o mapeamento ativo (controle ou teclado)."""
        if self.tipo_emulacao == self.TIPO_CONTROLE:
            return self.MAP_CONTROLE
        else: 
            return self.MAP_TECLADO

    def _executar_press(self, entrada_nome: str, acao_emulador: Union[vg.XUSB_BUTTON, str]):
        """Executa o pressionamento do botão no emulador selecionado."""
        if self.tipo_emulacao == self.TIPO_CONTROLE:
            if self.gamepad:
                self.gamepad.press_button(button=acao_emulador)
        elif self.tipo_emulacao == self.TIPO_TECLADO:
            if _KEYBOARD_DISPONIVEL:
                keyboard.press(acao_emulador)

    def _executar_release(self, entrada_nome: str, acao_emulador: Union[vg.XUSB_BUTTON, str]):
        """Executa a liberação do botão no emulador selecionado."""
        
        if self.tipo_emulacao == self.TIPO_CONTROLE:
            if self.gamepad:
                self.gamepad.release_button(button=acao_emulador)
        elif self.tipo_emulacao == self.TIPO_TECLADO:
            if _KEYBOARD_DISPONIVEL:
                keyboard.release(acao_emulador)

    def _reset_botoes_atuais(self):
        """Libera todos os botões que estavam ativos no estado anterior."""
        if any(self.estado_anterior): # Verifica se algum botão estava ativo
            mapeamento_anterior = self._get_mapeamento()
            for i, nome_botao in enumerate(self.BOTOES):
                if self.estado_anterior[i] == 1:
                    acao_emulador = mapeamento_anterior[nome_botao]
                    self._executar_release(nome_botao, acao_emulador)
            if self.gamepad and self.tipo_emulacao == self.TIPO_CONTROLE:
                self.gamepad.update()
            self.estado_anterior = [0, 0, 0, 0] 


    def atualizar_estado(self, novo_estado: List[int]):
        """
        Método principal para atualizar o estado de emulação.
        """
        if novo_estado != self.estado_anterior:
            print(f"\n🎮 [EMULATOR] Estado Anterior: {self.estado_anterior}")
            print(f"🎮 [EMULATOR] Novo Estado: {novo_estado}")
            print(f"🎮 [EMULATOR] Tipo Emulação: {self.tipo_emulacao}")
        if len(novo_estado) != 4:
            raise ValueError("O novo_estado deve ser um vetor de 4 posições.")
        if not all(isinstance(x, int) and x in [0, 1] for x in novo_estado):
            raise ValueError("Os valores do novo_estado devem ser 0 ou 1.")

        mapeamento = self._get_mapeamento()
        mudanca_detectada = False
 
        for i, nome_botao in enumerate(self.BOTOES):
            estado_atual = novo_estado[i]
            estado_anterior = self.estado_anterior[i]
            acao_emulador = mapeamento[nome_botao]
            # 1. Detetar Pressionamento (0 -> 1)
            if estado_atual == 1 and estado_anterior == 0:
                self._executar_press(nome_botao, acao_emulador)
                mudanca_detectada = True
            # 2. Detetar Liberação (1 -> 0)
            elif estado_atual == 0 and estado_anterior == 1:
                self._executar_release(nome_botao, acao_emulador)
                mudanca_detectada = True

        if mudanca_detectada:
            if self.gamepad and self.tipo_emulacao == self.TIPO_CONTROLE:
                self.gamepad.update() # Atualiza o estado do gamepad virtual

        self.estado_anterior = novo_estado[:]

    def fechar(self):
        """
        Garante que todos os botões sejam liberados e o gamepad virtual seja
        desligado quando a aplicação for encerrada.
        """
        self._reset_botoes_atuais() # Libera quaisquer botões que possam estar ativos
        if self.gamepad:
            self.gamepad.reset() # Garante que o gamepad virtual resete todos os estados
        print("Emulator encerrado.")


class InputData:
    """ 
    Interface base. 
    Na nova arquitetura com Worker, ela não busca dados, 
    apenas define o contrato para os instrumentos processarem.
    """
    def process_data(self, data, mappings, emulator):
        pass

"""
# --- Exemplo de Uso ---

import time
time.sleep(2)

# Criação do emulador
emu1 = Emulator()

# --- Teste de Emulação de CONTROLE (Padrão) ---
print("\n--- Teste de Emulação de Controle ---")

print("\nEnviando: [1, 0, 0, 0]")
emu1.atualizar_estado([1, 0, 0, 0])
time.sleep(0.5) # Pequena pausa para ver a ação

print("\nEnviando: [0, 1, 0, 0]")
emu1.atualizar_estado([0, 1, 0, 0])
time.sleep(0.5)

print("\nEnviando: [0, 0, 1, 0]")
emu1.atualizar_estado([0, 0, 1, 0])
time.sleep(0.5)

print("\nEnviando: [0, 0, 0, 1]")
emu1.atualizar_estado([0, 0, 0, 1])
time.sleep(0.5)

print("\nEnviando: [1, 1, 1, 1]")
emu1.atualizar_estado([1, 1, 1, 1])
time.sleep(0.5)

print("\nEnviando: [0, 0, 0, 0]")
emu1.atualizar_estado([0, 0, 0, 0])
time.sleep(0.5)

# --- Alterar para Emulação de TECLADO ---
print("\n--- Alterando para Emulação de Teclado ---")
emu1.set_tipo_emulacao(Emulator.TIPO_TECLADO)
time.sleep(0.5)

print("\nEnviando: [1, 0, 0, 0]")
emu1.atualizar_estado([1, 0, 0, 0])
time.sleep(0.5)

print("\nEnviando: [0, 1, 0, 0]")
emu1.atualizar_estado([0, 1, 0, 0])
time.sleep(0.5)

print("\nEnviando: [0, 0, 1, 0]")
emu1.atualizar_estado([0, 0, 1, 0])
time.sleep(0.5)

print("\nEnviando: [0, 0, 0, 1]")
emu1.atualizar_estado([0, 0, 0, 1])
time.sleep(0.5)

print("\nEnviando: [1, 1, 1, 1]")
emu1.atualizar_estado([1, 1, 1, 1])
time.sleep(0.5)

print("\nEnviando: [0, 0, 0, 0]")
emu1.atualizar_estado([0, 0, 0, 0])
time.sleep(0.5)

# --- Finalização segura ---
print("\n--- Encerrando Emulador ---")
emu1.fechar()
"""