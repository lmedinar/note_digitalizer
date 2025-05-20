#!/usr/bin/env python

import sys
import os
import io
import pytesseract
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QLabel,
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
    QScrollArea,
    QSlider,
    QSplitter,
    QTextEdit,
    QGroupBox,
    QFrame,
)
from PyQt5.QtCore import Qt, QRect, QPoint, QBuffer, QEvent
from PyQt5.QtGui import (
    QPixmap,
    QPainter,
    QPen,
    QColor,
    QImage,
    QClipboard,
    QTransform,
    QKeySequence,
)


class DigitizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.current_selection = None
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.is_selecting = False
        self.current_mode = "Mover"
        self.scale_factor = 1.0
        self.loaded_pixmap = None
        self.crop_pixmap = None
        self.setAcceptDrops(True)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Detectar Ctrl+V global
        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            # Si hay imagen en el clipboard, cargarla
            if clipboard.mimeData().hasImage():
                img = clipboard.image()
                # convertir QImage a QPixmap
                pix = QPixmap.fromImage(img)
                self.load_image(pix)
                return True  # consumido
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    ext = os.path.splitext(url.toLocalFile())[1].lower()
                    if ext in (".png", ".jpg", ".jpeg"):
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasUrls():
            return
        # Tomamos solo la primera
        file_path = event.mimeData().urls()[0].toLocalFile()
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".png", ".jpg", ".jpeg"):
            self.load_image(file_path)
            event.acceptProposedAction()
        else:
            event.ignore()

    def load_image(self, source):
        """
        source: o bien un path (str) o un QPixmap
        """
        if isinstance(source, str):
            pix = QPixmap(source)
        else:
            pix = source
        if pix.isNull():
            return
        self.loaded_pixmap = pix
        self.document_view.set_pixmap(pix)
        self.auto_adjust_zoom()
        self.recognized_text.clear()
        self.crop_pixmap = None
        self.crop_preview.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_crop_preview()

    def update_crop_preview(self):
        if self.crop_pixmap:
            scaled = self.crop_pixmap.scaled(
                self.crop_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.crop_preview.setPixmap(scaled)

    def export_image(self):
        if self.crop_pixmap:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Guardar imagen", "", "Imágenes PNG (*.png)"
            )
            if file_path:
                self.crop_pixmap.save(file_path, "PNG")

    def copy_to_clipboard(self):
        if self.crop_pixmap:
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(self.crop_pixmap, QClipboard.Clipboard)

    def initUI(self):
        # En lugar de añadir directamente mode_box al left_layout,
        # creamos un layout horizontal que contendrá:
        #  ┌───────────────┐ ┌───────────────┐
        #  │ mode_box      │ │ rotate_box    │
        #  └───────────────┘ └───────────────┘

        self.setWindowTitle("Digitalizador de Apuntes Universitarios")
        self.setGeometry(100, 100, 1200, 800)

        # Crear widget central y layout principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Crear splitter para dividir la interfaz en dos partes
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # ----- PANEL IZQUIERDO -----
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Botón para abrir archivo
        self.open_button = QPushButton("Abrir archivo...")
        self.open_button.clicked.connect(self.open_file)
        left_layout.addWidget(self.open_button)

        # ——— 1) Agrupación de los radio buttons ———
        # Radio buttons para seleccionar modalidad
        mode_box = QGroupBox("Modo de selección")
        mode_layout = QVBoxLayout()

        self.mode_group = QButtonGroup(self)

        self.move_radio = QRadioButton("Mover")
        self.text_book_radio = QRadioButton("Texto de libro")
        self.equation_book_radio = QRadioButton("Ecuación de libro")
        self.text_hand_radio = QRadioButton("Texto a mano")
        self.equation_hand_radio = QRadioButton("Ecuación a mano")
        self.image_radio = QRadioButton("Imagen")

        self.move_radio.setChecked(True)

        mode_layout.addWidget(self.move_radio)
        mode_layout.addWidget(self.text_book_radio)
        mode_layout.addWidget(self.equation_book_radio)
        mode_layout.addWidget(self.text_hand_radio)
        mode_layout.addWidget(self.equation_hand_radio)
        mode_layout.addWidget(self.image_radio)

        mode_box.setLayout(mode_layout)

        self.mode_group.addButton(self.move_radio)
        self.mode_group.addButton(self.text_book_radio)
        self.mode_group.addButton(self.equation_book_radio)
        self.mode_group.addButton(self.text_hand_radio)
        self.mode_group.addButton(self.equation_hand_radio)
        self.mode_group.addButton(self.image_radio)

        # ——— 2) Botones de rotación en un layout vertical ———
        rotate_box = QGroupBox("Rotar imagen")
        rotate_layout = QVBoxLayout()

        self.rotate_right_btn = QPushButton("⟳")
        self.rotate_left_btn = QPushButton("⟲")
        rotate_layout.addWidget(self.rotate_right_btn)
        rotate_layout.addWidget(self.rotate_left_btn)

        rotate_box.setLayout(rotate_layout)

        # Conectar señales
        self.rotate_right_btn.clicked.connect(lambda: self.rotate_image(90))
        self.rotate_left_btn.clicked.connect(lambda: self.rotate_image(-90))

        # Conectar radio buttons a cambio de modo
        self.move_radio.toggled.connect(lambda: self.change_mode("Mover"))
        self.text_book_radio.toggled.connect(lambda: self.change_mode("Texto de libro"))
        self.equation_book_radio.toggled.connect(
            lambda: self.change_mode("Ecuación de libro")
        )
        self.text_hand_radio.toggled.connect(lambda: self.change_mode("Texto a mano"))
        self.equation_hand_radio.toggled.connect(
            lambda: self.change_mode("Ecuación a mano")
        )
        self.image_radio.toggled.connect(lambda: self.change_mode("Imagen"))

        # mode_box.setLayout(mode_layout)
        # left_layout.addWidget(mode_box)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(mode_box)
        controls_layout.addWidget(rotate_box)
        # Finalmente lo agregamos al left_layout
        left_layout.addLayout(controls_layout)

        # Área de visualización de documento
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        self.document_view = DocumentViewer(self)
        scroll_area.setWidget(self.document_view)

        left_layout.addWidget(
            scroll_area, 1
        )  # El 1 hace que este widget tome el espacio disponible

        # Controles de zoom
        zoom_layout = QHBoxLayout()
        zoom_label = QLabel("Zoom:")
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)  # 10% a 200%
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.zoom_changed)

        zoom_layout.addWidget(zoom_label)
        zoom_layout.addWidget(self.zoom_slider)
        left_layout.addLayout(zoom_layout)

        # ----- PANEL DERECHO -----
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Vista previa del recorte
        preview_box = QGroupBox("Vista previa del recorte:  ")
        preview_layout = QVBoxLayout()

        self.crop_preview = QLabel()
        self.crop_preview.setAlignment(Qt.AlignCenter)
        self.crop_preview.setMinimumHeight(200)
        self.crop_preview.setFrameShape(QFrame.Box)

        preview_layout.addWidget(self.crop_preview)

        # Crear layout horizontal para los botones
        button_layout = QHBoxLayout()
        # Botón de exportar imagen
        self.export_button = QPushButton("Exportar imagen...")
        self.export_button.clicked.connect(self.export_image)
        button_layout.addWidget(self.export_button)

        # Botón de copiar al portapapeles
        self.copy_button = QPushButton("Copiar al clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_button)

        # Añadir layout de botones al layout del preview
        preview_layout.addLayout(button_layout)

        preview_box.setLayout(preview_layout)

        preview_box.setLayout(preview_layout)
        right_layout.addWidget(preview_box)

        # Campo de texto para el texto reconocido
        text_box = QGroupBox("Texto reconocido:  ")
        text_layout = QVBoxLayout()

        self.recognized_text = QTextEdit()

        text_layout.addWidget(self.recognized_text)
        text_box.setLayout(text_layout)
        right_layout.addWidget(text_box)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(preview_box)
        right_splitter.addWidget(text_box)
        right_layout.addWidget(right_splitter)

        # Añadir ambos paneles al splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 600])  # Tamaño inicial de cada panel

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo", "", "Archivos (*.png *.jpg *.jpeg)"
        )

        if file_path:
            # Por ahora solo manejamos imágenes
            if file_path.lower().endswith((".png", ".jpg", ".jpeg")):
                self.loaded_pixmap = QPixmap(file_path)
                self.document_view.set_pixmap(self.loaded_pixmap)
                # self.scale_factor = 1.0
                # self.zoom_slider.setValue(100)

                # Mejor ajustar zoom automáticamente para ver la imagen completa
                self.auto_adjust_zoom()

            else:
                # Aquí se implementaría la carga de PDF
                # Por ahora mostraremos un mensaje
                self.recognized_text.sexteto("Formato no soportado...")

    def auto_adjust_zoom(self):
        if not self.loaded_pixmap:
            return

        # Obtener dimensiones de la vista y la imagen
        view_size = self.document_view.size()
        img_size = self.loaded_pixmap.size()

        # Calcular factores de escala para ajustar ancho y alto
        width_ratio = view_size.width() / img_size.width()
        height_ratio = view_size.height() / img_size.height()

        # Usar el factor más pequeño para asegurar que la imagen completa sea visible
        zoom_factor = min(width_ratio, height_ratio) * 0.9  # 90% para dejar margen

        # Limitar el factor entre los valores del slider
        zoom_factor = max(0.1, min(2.0, zoom_factor))

        # Actualizar el slider y la escala
        slider_value = int(zoom_factor * 100)
        self.zoom_slider.setValue(slider_value)

        # Centrar la imagen
        self.document_view.center_image()

    def rotate_image(self, angle):
        """Gira la imagen cargada y reajusta el zoom."""
        if not self.loaded_pixmap:
            return

        transform = QTransform().rotate(angle)
        # rotar pixmap
        self.loaded_pixmap = self.loaded_pixmap.transformed(
            transform, Qt.SmoothTransformation
        )
        # actualizar vista y zoom
        self.document_view.set_pixmap(self.loaded_pixmap)
        self.auto_adjust_zoom()

    def change_mode(self, mode):
        self.current_mode = mode
        self.document_view.set_mode(mode)

    def zoom_changed(self, value):
        if self.loaded_pixmap:
            self.scale_factor = value / 100.0
            self.document_view.set_scale(self.scale_factor)

    def process_selection(self, rect, offset):
        if not self.loaded_pixmap or self.current_mode == "Mover":
            return

        # Obtener el recorte basado en la selección
        if rect.isValid():
            # Ajustar la selección considerando el offset y el factor de escala
            adjusted_rect = QRect(
                int((rect.x() - offset.x()) / self.scale_factor),
                int((rect.y() - offset.y()) / self.scale_factor),
                int(rect.width() / self.scale_factor),
                int(rect.height() / self.scale_factor),
            )

            # Asegurarse de que el rectángulo está dentro de los límites de la imagen
            img_rect = self.loaded_pixmap.rect()
            adjusted_rect = adjusted_rect.intersected(img_rect)

            if not adjusted_rect.isEmpty():
                self.crop_pixmap = self.loaded_pixmap.copy(adjusted_rect)
                self.update_crop_preview()

                # Aquí se implementaría el reconocimiento según el modo seleccionado
                self.recognize_content(self.current_mode)

    def recognize_content(self, mode):
        # Si es texto de libro, hacemos OCR con Tesseract
        if mode == "Texto de libro" and self.crop_pixmap:
            # 1) Convertir QPixmap → bytes PNG en memoria
            buffer = QBuffer()
            buffer.open(QBuffer.ReadWrite)
            self.crop_pixmap.save(buffer, "PNG")
            data = buffer.data()
            buffer.close()

            # 2) Leer bytes con PIL
            pil_img = Image.open(io.BytesIO(data))

            # 3) Llamar a pytesseract
            #    Ajusta 'lang' y 'config' si quieres mejorar precisión
            text = pytesseract.image_to_string(
                pil_img,
                lang="spa",  # español
                config="--oem 1 --psm 6",  # LSTM + segmento por bloque de texto
            )

            ###################################################
            # # DEBUG: mostrar formato crudo en terminal      #
            # print("=== OCR RAW TEXT BEGIN ===")             #
            # print(repr(text))                               #
            # print("=== OCR RAW TEXT END ===\n")             #
            # # también puedes imprimir líneas numeradas:     #
            # for i, line in enumerate(text.splitlines(), 1): #
            #     print(f"{i:03d}> {repr(line)}")             #
            # print("--- end of lines ---")                   #
            ###################################################

            # 4) Mostrar en el QTextEdit
            self.recognized_text.setPlainText(text.strip())
        else:
            # Comportamiento para los otros modos (imagen, ecuación, etc.)
            mode_text = {
                "Texto de libro": "",  # ya manejado arriba
                "Ecuación de libro": "Se reconocería una ecuación impresa aquí...",
                "Texto a mano": "Se reconocería texto manuscrito aquí...",
                "Ecuación a mano": "Se reconocería una ecuación manuscrita aquí...",
                "Imagen": "Imagen seleccionada para guardar.",
            }
            self.recognized_text.setPlainText(
                f"Modo: {mode}\n\n{mode_text.get(medo,'')}"
            )


class DocumentViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.pixmap = None
        self.mode = "Mover"
        self.scale = 1.0
        self.offset = QPoint(0, 0)
        self.last_pos = None
        self.selection_rect = QRect()
        self.is_selecting = False

        # Permitir el seguimiento del mouse
        self.setMouseTracking(True)
        self.setMinimumSize(400, 300)

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.offset = QPoint(0, 0)
        self.update()

    def set_mode(self, mode):
        self.mode = mode
        self.update()

    def set_scale(self, scale):
        self.scale = scale
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.lightGray)

        if self.pixmap:
            # Dibujar la imagen con el zoom y offset actuales
            scaled_width = int(self.pixmap.width() * self.scale)
            scaled_height = int(self.pixmap.height() * self.scale)

            # Aplicar la transformación para el offset y el zoom
            painter.translate(self.offset)
            painter.scale(self.scale, self.scale)
            painter.drawPixmap(0, 0, self.pixmap)

            # Si estamos en modo de selección y hay un rectángulo de selección
            if self.mode != "Mover" and self.is_selecting:
                # Volver a la escala normal para dibujar el rectángulo
                painter.resetTransform()
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawRect(self.selection_rect)

    def mousePressEvent(self, event):
        if not self.pixmap:
            return

        if self.mode == "Mover":
            self.last_pos = event.pos()
        else:
            self.is_selecting = True
            self.selection_rect.setTopLeft(event.pos())
            self.selection_rect.setBottomRight(event.pos())

    def mouseMoveEvent(self, event):
        if not self.pixmap:
            return

        if self.mode == "Mover" and self.last_pos:
            # Mover la imagen
            delta = event.pos() - self.last_pos
            self.offset += delta
            self.last_pos = event.pos()
        elif self.is_selecting:
            # Actualizar rectángulo de selección
            self.selection_rect.setBottomRight(event.pos())

        self.update()

    def mouseReleaseEvent(self, event):
        if not self.pixmap:
            return

        if self.mode == "Mover":
            self.last_pos = None
        elif self.is_selecting:
            self.is_selecting = False
            # Normalizar el rectángulo
            self.selection_rect = self.selection_rect.normalized()
            # Procesar la selección
            if not self.selection_rect.isEmpty():
                self.parent.process_selection(self.selection_rect, self.offset)

        self.update()

    def center_image(self):
        if not self.pixmap:
            return

        # Calcular el centro de la imagen escalada
        scaled_width = int(self.pixmap.width() * self.scale)
        scaled_height = int(self.pixmap.height() * self.scale)

        # Calcular offset para centrar
        x_offset = (self.width() - scaled_width) / 2
        y_offset = (self.height() - scaled_height) / 2

        # Establecer el nuevo offset
        self.offset = QPoint(int(x_offset), int(y_offset))
        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DigitizerApp()
    window.show()
    sys.exit(app.exec_())
