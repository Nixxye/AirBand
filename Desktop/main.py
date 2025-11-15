# main.py
import sys
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme

# Importa a janela principal do arquivo ui
from app_ui import MainApplication

# ===================================================================
# 3. EXECUÇÃO DA APLICAÇÃO
# ===================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Define o tema (Dark)
    setTheme(Theme.DARK)

    window = MainApplication()
    window.show()

    sys.exit(app.exec())