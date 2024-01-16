import os
import subprocess
import shutil
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QFileDialog, QMessageBox, QLineEdit, QLabel, QVBoxLayout, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal
import sys
from runas import runas

class ExtractionThread(QThread):
    update_progress = pyqtSignal(int)

    def __init__(self, command, destination_path):
        super(ExtractionThread, self).__init__()
        self.command = command
        self.destination_path = destination_path

    def run(self):
        try:
            process = subprocess.Popen(self.command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       stdin=subprocess.PIPE, universal_newlines=True)

            # Processa a saída em tempo real
            for line in process.stdout:
                print(line.strip())  # Saída do processo
                if "Do you want to replace it? (Y/N)" in line:
                    process.stdin.write("Y\n")  # Substituir automaticamente
                if "complete" in line:
                    progress = int(line.split()[0])
                    self.update_progress.emit(progress)

            process.stdin.close()  # Feche a entrada padrão para finalizar o processo

            # Aguarde o processo terminar
            stdout, stderr = process.communicate()

            if process.returncode == 0:
                self.finished.emit(0, stdout)
            else:
                self.finished.emit(1, stderr)
        except Exception as e:
            self.finished.emit(1, str(e))


class TableExtractor(QWidget):
    def __init__(self):
        super(TableExtractor, self).__init__()

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Table Extractor')
        self.setGeometry(300, 300, 400, 200)

        self.file_path = None
        self.destination_path = None

        self.file_label = QLabel('Selecionar arquivo de log:')
        self.file_button = QPushButton('Procurar')
        self.file_button.clicked.connect(self.show_file_dialog)

        self.table_label = QLabel('Nome da tabela:')
        self.table_input = QLineEdit()

        self.progress_label = QLabel('Progresso:')
        self.progress_bar = QProgressBar()

        self.extract_button = QPushButton('Extrair Tabela')
        self.extract_button.clicked.connect(self.move_and_extract)

        layout = QVBoxLayout()
        layout.addWidget(self.file_label)
        layout.addWidget(self.file_button)
        layout.addWidget(self.table_label)
        layout.addWidget(self.table_input)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.extract_button)

        self.setLayout(layout)

    def show_file_dialog(self):
        options = QFileDialog.Options()
        file_dialog = QFileDialog()
        file_dialog.setOptions(options)
        file_dialog.setNameFilter('Log Files (*.log)')
        file_dialog.fileSelected.connect(self.file_selected)
        file_dialog.exec_()

    def file_selected(self, file_path):
        self.file_path = file_path
        self.destination_path = f'C:\\Program Files\\SQL Anywhere 12\\Bin64\\{os.path.basename(self.file_path)}'
        self.check_destination()

    def check_destination(self):
        if os.path.exists(self.destination_path):
            reply = QMessageBox.question(self, 'Aviso', 'Já existe um arquivo com o mesmo nome. Deseja substituir?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.No:
                return

        try:
            shutil.copy(self.file_path, self.destination_path)
            self.make_file_writable(self.destination_path)  # Adiciona permissão de escrita ao arquivo
            QMessageBox.information(self, 'Concluído', 'Arquivo movido com sucesso.')
        except PermissionError:
            QMessageBox.critical(self, 'Erro de Permissão', 'Você não tem permissão para escrever no diretório. Execute o programa como administrador.')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Erro ao transferir arquivo: {str(e)}')

    def make_file_writable(self, file_path):
        os.chmod(file_path, 0o777)  # Concede permissões de escrita ao arquivo

    def move_and_extract(self):
        if not self.file_path or not os.path.exists(self.destination_path):
            QMessageBox.warning(self, 'Aviso', 'Erro ao transferir o arquivo.')
            return

        table_name = self.table_input.text().strip()
        if not table_name:
            QMessageBox.warning(self, 'Aviso', 'Digite o nome da tabela.')
            return

        # Mude para o diretório Bin64 antes de executar o comando
        bin64_path = r'C:\Program Files\SQL Anywhere 12\Bin64'
        os.chdir(bin64_path)

        # Escolher um diretório para o arquivo .txt
        txt_path, _ = QFileDialog.getSaveFileName(self, 'Escolha o local para salvar o arquivo .txt',
                                                  f'c:\\abase\\{table_name}.txt', 'Text Files (*.txt)')
        if not txt_path:
            return

        # Atualizar o comando de extração para incluir o novo caminho do arquivo .txt
        command = f'dbtran -s -r {os.path.basename(self.destination_path)} -it dba.{table_name} -n {txt_path}'

        # Executar o processo em uma thread separada
        self.extraction_thread = ExtractionThread(command, self.destination_path)
        self.extraction_thread.finished.connect(self.process_extraction_result)
        self.extraction_thread.update_progress.connect(self.update_progress_bar)
        self.extraction_thread.start()

    def update_progress_bar(self, progress):
        self.progress_bar.setValue(progress)

    def process_extraction_result(self, return_code, result):
        # Manipular os resultados da extração
        if return_code == 0:
            QMessageBox.information(self, 'Concluído', 'Extração concluída com sucesso.')
        else:
            QMessageBox.critical(self, 'Erro', f'Erro durante a extração: {result}')

        # Volte para o diretório original
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        self.table_input.clear()
        self.progress_bar.reset()


if __name__ == '__main__':
    # Verifica se o programa está sendo executado como administrador
    if os.name == 'nt' and sys.platform == 'win32' and not ctypes.windll.shell32.IsUserAnAdmin():
        # Se não estiver sendo executado como administrador, executa novamente como administrador
        runas(runas.kwargs['python'], arguments=[sys.executable] + sys.argv, wait=False)
        sys.exit()

    app = QApplication(sys.argv)
    window = TableExtractor()
    window.show()
    sys.exit(app.exec_())
