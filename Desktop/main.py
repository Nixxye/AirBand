from gui import MainApplication
import qt_material
import sys
from PyQt5.QtWidgets import QApplication


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Aplica o tema Qt-Material
    qt_material.apply_stylesheet(app, theme='dark_blue.xml')

    window = MainApplication()
    window.show()
    sys.exit(app.exec_())
