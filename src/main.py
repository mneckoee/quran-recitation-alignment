import sys
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QFileDialog, QTextEdit, QLabel, QHBoxLayout, QFrame, QSizePolicy, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from pydub import AudioSegment
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import arabic_reshaper
from bidi.algorithm import get_display

class Marker:
    def __init__(self, index, word, x, y_min, y_max, ax):
        self.index = index
        self.word = word
        self.x = x
        self.ax = ax
        self.selected = False

        # Vertical line across waveform
        self.line = Line2D([x, x], [y_min, y_max], color='green', linewidth=1.5)
        ax.add_line(self.line)

        # Box for grabbing (below waveform)
        box_size = (y_max - y_min) * 0.05
        self.box_y = y_min - box_size * 2   # place a bit lower
        self.box_size = box_size

        self.box = Rectangle(
            (x - box_size, self.box_y),
            box_size * 2, box_size,
            facecolor='lightblue', edgecolor='blue'
        )
        ax.add_patch(self.box)

        # Text label inside the box (vertical)
        bidi_text = persian_text(word)
        self.label = ax.text(
            x, self.box_y + box_size / 2,
            f"{bidi_text}:{index}",
            ha="center", va="center",
            fontsize=8, color="black", rotation=90
        )

        self.drag_active = False

    def update_position(self, x):
        self.x = x
        self.line.set_xdata([x, x])
        self.box.set_x(x - self.box_size)
        self.label.set_x(x)

    def set_selected(self, selected: bool):
        self.selected = selected
        if selected:
            self.line.set_color("blue")
        else:
            self.line.set_color("green")
        self.ax.figure.canvas.draw_idle()

    def set_visibility(self, visible):
        self.line.set_visible(visible)
        self.box.set_visible(visible)
        self.label.set_visible(visible)
        self.ax.figure.canvas.draw_idle()

class WaveformViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Waveform Viewer with Markers")
        self.setFixedSize(900, 700)
        self.setStyleSheet("background-color: #1a1a1a; color: #e0e0e0;")

        # Central widget and layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)

        # --- Header (Logo and Load MP3 button) ---
        self.header_frame = QFrame()
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(10, 10, 10, 10)
        self.logo_label = QLabel("logo")
        self.logo_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        self.header_layout.addWidget(self.logo_label)
        self.header_layout.addStretch(1)
        self.load_button = QPushButton("Load MP3")
        self.load_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.load_button.clicked.connect(self.load_mp3)
        self.header_layout.addWidget(self.load_button)
        self.layout.addWidget(self.header_frame)

        # --- Audio Waveform section ---
        self.waveform_frame = QFrame()
        self.waveform_frame.setStyleSheet("background-color: #2b2b2b; border-radius: 8px;")
        self.waveform_layout = QVBoxLayout(self.waveform_frame)
        self.waveform_layout.setContentsMargins(20, 15, 20, 15)
        self.waveform_title = QLabel("Audio Waveform")
        self.waveform_title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.waveform_layout.addWidget(self.waveform_title)

        # Matplotlib canvas for the waveform
        self.figure, self.ax = plt.subplots(facecolor='#2b2b2b')
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.waveform_layout.addWidget(self.canvas)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['bottom'].set_visible(False)
        self.ax.spines['left'].set_visible(False)

        # Playback controls
        self.playback_controls = QWidget()
        self.playback_layout = QHBoxLayout(self.playback_controls)
        self.playback_layout.setContentsMargins(0, 0, 0, 0)
        self.play_button = QPushButton()
        self.play_button.setIcon(QIcon("icons/play.png"))
        self.play_button.setStyleSheet("background-color: transparent; border: none;")
        self.play_button.clicked.connect(self.toggle_playback)
        self.playback_layout.addWidget(self.play_button)
        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: #888;")
        self.playback_layout.addSpacing(10)
        self.playback_layout.addWidget(self.time_label)
        self.playback_layout.addStretch(1)
        self.layout.addWidget(self.playback_controls)
        self.layout.addWidget(self.waveform_frame)

        # --- Transcription Editor section ---
        self.transcription_frame = QFrame()
        self.transcription_frame.setStyleSheet("background-color: #2b2b2b; border-radius: 8px;")
        self.transcription_layout = QVBoxLayout(self.transcription_frame)
        self.transcription_layout.setContentsMargins(20, 15, 20, 15)
        self.transcription_title = QLabel("Transcription Editor")
        self.transcription_title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.transcription_layout.addWidget(self.transcription_title)

        self.input_container = QHBoxLayout()
        self.transcription = QTextEdit()
        self.transcription.setPlaceholderText("one line transcription")
        self.transcription.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        self.transcription.setMaximumHeight(100)
        self.transcription.textChanged.connect(self.handle_transcription_change)
        self.transcription.installEventFilter(self)
        self.input_container.addWidget(self.transcription)

        self.submit_button = QPushButton("Submit Transcription")
        self.submit_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.submit_button.clicked.connect(self.add_markers)
        self.input_container.addWidget(self.submit_button)
        
        # Checkbox for manual markers
        self.add_markers_checkbox = QCheckBox("Add markers on 'M' keypress")
        self.add_markers_checkbox.setStyleSheet("QCheckBox { color: #e0e0e0; }")
        self.add_markers_checkbox.setChecked(False)
        self.add_markers_checkbox.stateChanged.connect(self.toggle_add_markers_mode)
        self.input_container.addWidget(self.add_markers_checkbox)
        
        self.transcription_layout.addLayout(self.input_container)
        self.layout.addWidget(self.transcription_frame)

        # --- Export Markers button ---
        self.export_button = QPushButton("Export Markers")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #383838;
            }
        """)
        self.export_button.clicked.connect(self.export_markers)
        self.layout.addWidget(self.export_button, alignment=Qt.AlignRight)

        # State
        self.audio = None
        self.samples = None
        self.sample_rate = None
        self.y_min = None
        self.y_max = None
        self.line = None
        self.playhead_line = None
        self.markers = []
        self._drag_marker = None
        self._drag_active = False
        self._last_xdata = None
        self.selected_marker = None
        self.add_markers_on_keypress = False  # New state variable
        self.next_marker_index = 0 # New state variable

        # Canvas events
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)

        # Playback
        self.stream = None
        self.playback_position = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_playback_and_ui)

        self.current_word_label = None
        try:
            self.vazir_font = fm.FontProperties(fname="fonts/vazir_medium.ttf")
        except FileNotFoundError:
            self.vazir_font = fm.FontProperties()
            print("Vazir font not found. Using default font.")

        # Initial plot
        self.ax.set_title("Audio Waveform", color='#e0e0e0')
        self.canvas.draw_idle()

    # -------------------------
    # Load audio
    # -------------------------
    def load_mp3(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select MP3", "", "MP3 Files (*.mp3)")
        if not file_path:
            return
        self.audio = AudioSegment.from_mp3(file_path)
        self.samples = np.array(self.audio.get_array_of_samples(), dtype=np.float32)
        if self.audio.channels == 2:
            self.samples = self.samples.reshape((-1, 2)).mean(axis=1)
        self.samples /= np.max(np.abs(self.samples))
        self.sample_rate = self.audio.frame_rate
        self.y_min, self.y_max = float(np.min(self.samples)), float(np.max(self.samples))
        self.y_min *= 1.1
        self.y_max *= 1.1
        duration_ms = len(self.samples) / self.sample_rate * 1000
        self.ax.set_xlim(0, duration_ms)
        self.update_waveform()
        self.clear_markers()
        self.transcription.clear()
        self.transcription.setDisabled(False)
        self.submit_button.setDisabled(False)
        self.add_markers_checkbox.setDisabled(False)
        self.update_playback_ui()

    def clear_markers(self):
        for m in self.markers:
            m.line.remove()
            m.box.remove()
            m.label.remove()
        self.markers.clear()
        self.selected_marker = None
        if self.playhead_line:
            self.playhead_line.remove()
            self.playhead_line = None
        self.canvas.draw_idle()
        self.next_marker_index = 0 # Reset marker index

    # New method to toggle marker mode
    def toggle_add_markers_mode(self, state):
        self.add_markers_on_keypress = (state == Qt.Checked)
        if self.add_markers_on_keypress:
            self.submit_button.setDisabled(True)
            self.transcription.setDisabled(False)
            self.clear_markers()
            self.next_marker_index = 0
        else:
            self.submit_button.setDisabled(False)
            self.transcription.setDisabled(False)

    # -------------------------
    # Update waveform
    # -------------------------
    def update_waveform(self):
        if self.samples is None:
            return
        x_min, x_max = self.ax.get_xlim()
        total_ms = len(self.samples) / self.sample_rate * 1000
        x_min = max(0, x_min)
        x_max = min(total_ms, x_max)
        start_idx = int(x_min / 1000 * self.sample_rate)
        end_idx = int(x_max / 1000 * self.sample_rate)
        if end_idx <= start_idx:
            return
        visible_samples = end_idx - start_idx
        canvas_width = max(1, self.canvas.width())
        step = max(1, int(visible_samples / (2 * canvas_width)))
        dec_samples = self.samples[start_idx:end_idx:step]
        dec_time = np.linspace(x_min, x_max, num=len(dec_samples))

        if self.line is None:
            self.line, = self.ax.plot(dec_time, dec_samples, color='#4CAF50', linewidth=1.2)
            self.ax.set_ylim(self.y_min, self.y_max)
        else:
            self.line.set_data(dec_time, dec_samples)
            self.ax.set_xlim(x_min, x_max)
        self.canvas.draw_idle()

    # -------------------------
    # Scroll zoom
    # -------------------------
    def on_scroll(self, event):
        if self.samples is None:
            return
        x_min, x_max = self.ax.get_xlim()
        x_mid = event.xdata if event.xdata is not None else (x_min + x_max) / 2
        scale_factor = 0.8 if event.button == "up" else 1.25
        new_x_min = x_mid - (x_mid - x_min) * scale_factor
        new_x_max = x_mid + (x_max - x_mid) * scale_factor
        total_ms = len(self.samples) / self.sample_rate * 1000
        new_x_min = max(0, new_x_min)
        new_x_max = min(total_ms, new_x_max)
        self.ax.set_xlim(new_x_min, new_x_max)
        self.update_waveform()

    # -------------------------
    # Drag markers & pan
    # -------------------------
    def on_press(self, event):
        if self.samples is None or event.xdata is None:
            return
        # Check marker grab
        for m in self.markers:
            if abs(event.xdata - m.x) < 20 and m.line.get_visible():
                self._drag_marker = m
                m.drag_active = True
                self.select_marker(m)
                return
        self._drag_active = True
        self._last_xdata = event.xdata

    def on_release(self, event):
        if self._drag_marker:
            self._drag_marker.drag_active = False
            self._drag_marker = None
        self._drag_active = False
        self._last_xdata = None

    def on_motion(self, event):
        if event.xdata is None:
            return
        # Drag marker
        if self._drag_marker and self._drag_marker.drag_active:
            self._drag_marker.update_position(event.xdata)
            self.canvas.draw_idle()
            return
        # Pan waveform
        if self._drag_active:
            dx = self._last_xdata - event.xdata
            x_min, x_max = self.ax.get_xlim()
            total_ms = len(self.samples) / self.sample_rate * 1000
            new_x_min = max(0, x_min + dx)
            new_x_max = min(total_ms, x_max + dx)
            self.ax.set_xlim(new_x_min, new_x_max)
            self.update_waveform()
            self._last_xdata = event.xdata

    def select_marker(self, marker: Marker):
        for m in self.markers:
            m.set_selected(False)
        marker.set_selected(True)
        self.selected_marker = marker

    # -------------------------
    # Playback
    # -------------------------
    def toggle_playback(self):
        if self.stream is None or not self.stream.active:
            self.start_playback()
        else:
            self.stop_playback()

    def start_playback(self):
        if self.samples is None:
            return
        self.stop_playback()
        
        start_ms = 0
        if self.add_markers_on_keypress:
            if self.selected_marker:
                start_ms = self.selected_marker.x
            elif self.markers:
                # Start from the last placed marker if none are selected
                start_ms = self.markers[-1].x
            else:
                start_ms = 0
        else:
            if self.selected_marker:
                start_ms = self.selected_marker.x
            else:
                start_ms = 0

        self.playback_position = int(start_ms / 1000 * self.sample_rate)
        
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate, channels=1, dtype='float32',
            callback=self.sd_callback, finished_callback=self.playback_finished
        )
        self.stream.start()
        self.timer.start(10)
        self.update_playback_ui()

    def stop_playback(self):
        if self.stream and self.stream.active:
            self.stream.stop()
        self.timer.stop()
        self.update_playback_ui()

    def playback_finished(self):
        self.stop_playback()
        self.playback_position = 0
        if self.playhead_line:
            self.playhead_line.set_xdata([0, 0])
        self.update_playback_ui()

    def sd_callback(self, outdata, frames, time, status):
        end = min(self.playback_position + frames, len(self.samples))
        outdata[:end - self.playback_position, 0] = self.samples[self.playback_position:end]
        if end - self.playback_position < frames:
            outdata[end - self.playback_position:] = 0
        self.playback_position = end
        if self.playback_position >= len(self.samples):
            raise sd.CallbackStop()

    def update_playback_and_ui(self):
        current_ms = self.playback_position / self.sample_rate * 1000
        # Update time label
        minutes = int(current_ms / 60000)
        seconds = int((current_ms % 60000) / 1000)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")

        # Update playhead line
        if self.playhead_line:
            self.playhead_line.set_xdata([current_ms, current_ms])
        else:
            self.playhead_line = Line2D([current_ms, current_ms], [self.y_min, self.y_max], color='red')
            self.ax.add_line(self.playhead_line)

        # --- Find first marker left of playhead ---
        left_markers = [m for m in self.markers if m.x <= current_ms]
        if left_markers:
            nearest = max(left_markers, key=lambda m: m.x)  # closest marker on left
            word = nearest.word
            bidi_word = persian_text(word)

            # Show word in center of waveform
            if self.current_word_label is None:
                self.current_word_label = self.ax.text(
                    0.5, 0.9, bidi_word, transform=self.ax.transAxes,
                    ha="center", va="center", fontsize=14,
                    fontproperties=self.vazir_font,
                    color="darkred", fontweight="bold", bbox=dict(facecolor="white", alpha=0.6, edgecolor="none")
                )
            else:
                self.current_word_label.set_text(bidi_word)
        else:
            # If no marker yet, clear the text
            if self.current_word_label:
                self.current_word_label.set_text("")
        self.canvas.draw_idle()

    def update_playback_ui(self):
        if self.stream and self.stream.active:
            self.play_button.setIcon(QIcon("icons/pause.png"))
        else:
            self.play_button.setIcon(QIcon("icons/play.png"))

    # -------------------------
    # Submit transcription → add markers
    # -------------------------
    def add_markers(self):
        text = self.transcription.toPlainText().strip()
        if not text or self.samples is None:
            return
        
        words = text.split()
        if not words:
            return
        
        self.clear_markers()
        
        self.transcription.setDisabled(True)
        self.submit_button.setDisabled(True)

        if not self.add_markers_on_keypress:
            total_ms = len(self.samples) / self.sample_rate * 1000
            spacing = total_ms / (len(words) + 1)
            for i, w in enumerate(words):
                x = spacing * (i + 1)
                m = Marker(i + 1, w, x, self.y_min, self.y_max, self.ax)
                self.markers.append(m)

            self.canvas.draw_idle()
        

    def handle_transcription_change(self):
        self.transcription.setDisabled(False)
        self.submit_button.setDisabled(False)
        self.clear_markers()

    # -------------------------
    # Key press events
    # -------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.toggle_playback()
            return
        
        # New: Manual marker placement
        if self.add_markers_on_keypress and event.key() == Qt.Key_M:
            if not self.stream or not self.stream.active:
                print("Cannot add marker, playback is paused. Press space to play first.")
                return

            current_ms = self.playback_position / self.sample_rate * 1000
            words = self.transcription.toPlainText().strip().split()

            if self.next_marker_index < len(words):
                word = words[self.next_marker_index]
                if self.next_marker_index < len(self.markers):
                    # Update existing marker
                    m = self.markers[self.next_marker_index]
                    m.update_position(current_ms)
                    self.select_marker(m)
                else:
                    # Add new marker
                    m = Marker(self.next_marker_index + 1, word, current_ms, self.y_min, self.y_max, self.ax)
                    self.markers.append(m)
                    self.select_marker(m)
                
                self.next_marker_index += 1
                self.canvas.draw_idle()
            else:
                print("No more words to mark. Add more to transcription.")
            return

        # Rest of the keypress logic
        if self.selected_marker is not None:
            xmin, xmax = self.ax.get_xlim()
            step = (xmax - xmin) * 0.01  # adjust fraction as needed

            newx_x = self.selected_marker.x
            if event.key() == Qt.Key_Left:
                newx_x -= step
            elif event.key() == Qt.Key_Right:
                newx_x += step

            # update marker position
            self.selected_marker.update_position(newx_x)
            self.canvas.draw_idle()
        else:
            # no marker selected, fall back to other shortcuts (like play/pause on space)
            super().keyPressEvent(event)
    
    def eventFilter(self, obj, event):
        if obj == self.transcription and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                self.toggle_playback()
                return True
        return super().eventFilter(obj, event)

    def export_markers(self):
        times = [int(m.x) for m in self.markers]
        array_str = "[" + ", ".join(map(str, times)) + "]"
        clipboard = QApplication.clipboard()
        clipboard.setText(array_str)
        print("Exported:", array_str)

def persian_text(word: str):
    """Convert plain Persian text to shaped RTL text"""
    reshaped = arabic_reshaper.reshape(word)
    return get_display(reshaped)

# -------------------------
# Main
# -------------------------
def main():
    app = QApplication(sys.argv)
    window = WaveformViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()