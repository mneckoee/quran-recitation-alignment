import sys
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, 
    QFileDialog, QTextEdit, QLabel
)
from PyQt5.QtCore import Qt
from pydub import AudioSegment
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

class Marker:
    def __init__(self, index, word, x, y_min, y_max, ax):
        self.index = index
        self.word = word
        self.x = x
        self.ax = ax
        self.selected = False

        # Vertical line across waveform
        self.line = Line2D([x, x], [y_min, y_max], color='blue', linewidth=1.5)
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
        self.label = ax.text(
            x, self.box_y + box_size / 2,
            f"{word}:{index}",
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
            self.line.set_color("green")
            self.box.set_edgecolor("green")
            self.box.set_facecolor("lightgreen")
        else:
            self.line.set_color("blue")
            self.box.set_edgecolor("blue")
            self.box.set_facecolor("lightblue")


class WaveformViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Waveform Viewer with Markers")
        self.setGeometry(100, 100, 900, 800)

        # Layout
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Load button
        self.load_button = QPushButton("Load MP3 File")
        self.load_button.clicked.connect(self.load_mp3)
        self.layout.addWidget(self.load_button)

        # Canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        # Transcription field
        self.trans_label = QLabel("Transcription:")
        self.layout.addWidget(self.trans_label)
        self.transcription = QTextEdit()
        self.transcription.setPlaceholderText("Type or paste transcription...")
        self.layout.addWidget(self.transcription)
        self.transcription.installEventFilter(self)

        # Submit button
        self.submit_button = QPushButton("Submit Transcription")
        self.submit_button.clicked.connect(self.add_markers)
        self.layout.addWidget(self.submit_button)

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

        # Canvas events
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)

        # Playback
        self.stream = None
        self.playback_position = 0
        self.timer_id = self.startTimer(10)

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
        duration_ms = len(self.samples)/self.sample_rate*1000
        self.ax.set_xlim(0, duration_ms)
        self.update_waveform("Waveform of " + file_path.split("/")[-1])
        if self.playhead_line:
            self.playhead_line.remove()
            self.playhead_line = None
        # Remove old markers
        for m in self.markers:
            m.line.remove()
            m.box.remove()
            m.label.remove()
        self.markers.clear()
        self.transcription.clear()
        self.selected_marker = None

    # -------------------------
    # Update waveform
    # -------------------------
    def update_waveform(self, title="Waveform"):
        if self.samples is None:
            return
        x_min, x_max = self.ax.get_xlim()
        total_ms = len(self.samples)/self.sample_rate*1000
        x_min = max(0, x_min)
        x_max = min(total_ms, x_max)
        start_idx = int(x_min/1000*self.sample_rate)
        end_idx = int(x_max/1000*self.sample_rate)
        if end_idx <= start_idx:
            return
        visible_samples = end_idx - start_idx
        canvas_width = max(1, self.canvas.width())
        step = max(1, int(visible_samples/(2*canvas_width)))
        dec_samples = self.samples[start_idx:end_idx:step]
        dec_time = np.linspace(x_min, x_max, num=len(dec_samples))
        if self.line is None:
            self.line, = self.ax.plot(dec_time, dec_samples, linewidth=0.8)
            self.ax.set_xlim(x_min, x_max)
            self.ax.set_ylim(self.y_min, self.y_max)
            self.ax.set_xlabel("Time (ms)")
            self.ax.set_ylabel("Amplitude")
            self.ax.set_title(title)
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
        zoom_in_factor = 0.8
        zoom_out_factor = 1.25

        if hasattr(event, "step") and event.step != 0:
            scale_factor = zoom_in_factor if event.step > 0 else zoom_out_factor
        else:
            if event.button == "up":
                scale_factor = zoom_in_factor
            elif event.button == "down":
                scale_factor = zoom_out_factor
            else:
                return

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
            if abs(event.xdata - m.x) < 10:
                self._drag_marker = m
                m.drag_active = True
                self.select_marker(m)   # highlight selection
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
            total_ms = len(self.samples)/self.sample_rate*1000
            new_x_min = max(0, x_min+dx)
            new_x_max = min(total_ms, x_max+dx)
            self.ax.set_xlim(new_x_min, new_x_max)
            self.update_waveform()
            self._last_xdata = event.xdata

    def select_marker(self, marker: Marker):
        for m in self.markers:
            m.set_selected(False)
        marker.set_selected(True)
        self.selected_marker = marker
        self.canvas.draw_idle()

    # -------------------------
    # Spacebar play/pause
    # -------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            if self.stream is None or not self.stream.active:
                self.start_playback()
            else:
                self.stream.stop()

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

    def start_playback(self):
        if self.stream:
            self.stream.stop()
        # start from selected marker (ms) if exists
        if self.selected_marker:
            start_ms = self.selected_marker.x
            self.playback_position = int(start_ms/1000 * self.sample_rate)
        else:
            self.playback_position = 0

        self.stream = sd.OutputStream(
            samplerate=self.sample_rate, channels=1, dtype='float32',
            callback=self.sd_callback
        )
        self.stream.start()

    def sd_callback(self, outdata, frames, time, status):
        end = min(self.playback_position+frames, len(self.samples))
        outdata[:end-self.playback_position,0] = self.samples[self.playback_position:end]
        if end-self.playback_position < frames:
            outdata[end-self.playback_position:] = 0
        self.playback_position = end
        if self.playback_position >= len(self.samples):
            raise sd.CallbackStop()

    # -------------------------
    # Timer for playhead
    # -------------------------
    def timerEvent(self, event):
        if self.stream and self.stream.active:
            current_ms = self.playback_position/self.sample_rate*1000
            if self.playhead_line:
                self.playhead_line.set_xdata([current_ms, current_ms])
            else:
                self.playhead_line = Line2D([current_ms, current_ms],[self.y_min,self.y_max],color='red')
                self.ax.add_line(self.playhead_line)
            self.canvas.draw_idle()

    # -------------------------
    # Submit transcription → add markers
    # -------------------------
    def add_markers(self):
        text = self.transcription.toPlainText().strip()
        if not text or self.samples is None:
            return
        
        # disable after submit
        self.transcription.setDisabled(True)

        words = text.split()
        total_ms = len(self.samples)/self.sample_rate*1000
        spacing = total_ms / max(len(words), 1)
        # Remove previous markers
        for m in self.markers:
            m.line.remove()
            m.box.remove()
            m.label.remove()
        self.markers.clear()
        self.selected_marker = None
        for i, w in enumerate(words):
            x = spacing * (i+1)
            m = Marker(i+1, w, x, self.y_min, self.y_max, self.ax)
            self.markers.append(m)
        self.canvas.draw_idle()

    def eventFilter(self, obj, event):
        if obj == self.transcription and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Space:
                if self.stream is None or not self.stream.active:
                    self.start_playback()
                else:
                    self.stream.stop()
                return True
        return super().eventFilter(obj, event)

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
