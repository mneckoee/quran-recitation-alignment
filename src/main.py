import sys
import numpy as np
import sounddevice as sd
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QFileDialog
from PyQt5.QtCore import Qt
from pydub import AudioSegment
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.lines import Line2D

class WaveformViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Waveform Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Main widget & layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Load button
        self.load_button = QPushButton("Load MP3 File", self)
        self.load_button.clicked.connect(self.load_mp3)
        self.layout.addWidget(self.load_button)

        # Matplotlib canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        # Events
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("axes_enter_event", self.on_axes_enter)
        self.canvas.mpl_connect("axes_leave_event", self.on_axes_leave)

        # State
        self.audio = None
        self.samples = None
        self.sample_rate = None
        self.y_min = None
        self.y_max = None
        self.line = None
        self.playhead_line = None

        # Drag
        self._drag_active = False
        self._last_xdata = None

        # Playback
        self.stream = None
        self.playback_position = 0
        self.timer_id = self.startTimer(10)  # 100 FPS

    # ---------------------------
    # Load MP3
    # ---------------------------
    def load_mp3(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select MP3 File", "", "MP3 Files (*.mp3);;All Files (*)"
        )
        if not file_path:
            return
        try:
            # Load audio
            self.audio = AudioSegment.from_mp3(file_path)
            self.samples = np.array(self.audio.get_array_of_samples(), dtype=np.float32)
            if self.audio.channels == 2:
                self.samples = self.samples.reshape((-1, 2)).mean(axis=1)
            self.samples /= np.max(np.abs(self.samples))  # normalize

            self.sample_rate = self.audio.frame_rate
            self.y_min, self.y_max = float(np.min(self.samples)), float(np.max(self.samples))

            # X-limits in ms
            duration_ms = len(self.samples) / self.sample_rate * 1000
            self.ax.set_xlim(0, duration_ms)

            # Draw waveform
            self.update_waveform(title="Waveform of " + file_path.split("/")[-1])

            # Reset playhead
            if self.playhead_line:
                self.playhead_line.remove()
                self.playhead_line = None

            # Stop previous playback
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.playback_position = 0

        except Exception as e:
            print(f"Error loading MP3: {e}")

    # ---------------------------
    # Update waveform
    # ---------------------------
    def update_waveform(self, title="Waveform"):
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

        decimated_samples = self.samples[start_idx:end_idx:step]
        decimated_time = np.linspace(x_min, x_max, num=len(decimated_samples))

        if self.line is None:
            self.line, = self.ax.plot(decimated_time, decimated_samples, linewidth=0.8)
            self.ax.set_xlim(x_min, x_max)
            self.ax.set_ylim(self.y_min, self.y_max)
            self.ax.set_xlabel("Time (ms)")
            self.ax.set_ylabel("Amplitude")
            self.ax.set_title(title)
        else:
            self.line.set_data(decimated_time, decimated_samples)
            self.ax.set_xlim(x_min, x_max)

        self.canvas.draw_idle()

    # ---------------------------
    # Scroll zoom
    # ---------------------------
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

    # ---------------------------
    # Pan drag
    # ---------------------------
    def on_axes_enter(self, event):
        if event.inaxes is self.ax and not self._drag_active:
            self.canvas.setCursor(Qt.OpenHandCursor)

    def on_axes_leave(self, event):
        if not self._drag_active:
            self.canvas.setCursor(Qt.ArrowCursor)

    def on_press(self, event):
        if event.inaxes is not self.ax or event.button != 1 or self.samples is None:
            return
        if event.xdata is None:
            return
        self._drag_active = True
        self._last_xdata = event.xdata
        self.canvas.setCursor(Qt.ClosedHandCursor)

    def on_release(self, event):
        if event.button != 1:
            return
        self._drag_active = False
        self._last_xdata = None
        self.canvas.setCursor(Qt.OpenHandCursor if event.inaxes is self.ax else Qt.ArrowCursor)

    def on_motion(self, event):
        if not self._drag_active or self.samples is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or self._last_xdata is None:
            return

        dx = self._last_xdata - event.xdata
        x_min, x_max = self.ax.get_xlim()
        x_range = x_max - x_min
        total_ms = len(self.samples) / self.sample_rate * 1000

        if x_range >= total_ms:
            self.ax.set_xlim(0, total_ms)
            self.update_waveform()
            self._last_xdata = event.xdata
            return

        new_x_min = x_min + dx
        new_x_max = x_max + dx
        if new_x_min < 0:
            new_x_min = 0
            new_x_max = x_range
        if new_x_max > total_ms:
            new_x_max = total_ms
            new_x_min = total_ms - x_range

        self.ax.set_xlim(new_x_min, new_x_max)
        self.update_waveform()
        self._last_xdata = event.xdata

    # ---------------------------
    # Spacebar play/pause
    # ---------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and self.samples is not None:
            if self.stream is None or not self.stream.active:
                self.start_playback()
            else:
                self.stream.stop()

    # ---------------------------
    # SoundDevice playback
    # ---------------------------
    def start_playback(self):
        if self.stream:
            self.stream.stop()
            self.playback_position = 0

        self.playback_position = 0
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self.sd_callback
        )
        self.stream.start()

    def sd_callback(self, outdata, frames, time, status):
        end = min(self.playback_position + frames, len(self.samples))
        outdata[:end - self.playback_position, 0] = self.samples[self.playback_position:end]
        if end - self.playback_position < frames:
            outdata[end - self.playback_position:] = 0
        self.playback_position = end
        if self.playback_position >= len(self.samples):
            raise sd.CallbackStop()

    # ---------------------------
    # Timer for red playhead
    # ---------------------------
    def timerEvent(self, event):
        if self.stream and self.stream.active:
            current_ms = self.playback_position / self.sample_rate * 1000
            if self.playhead_line:
                self.playhead_line.set_xdata([current_ms, current_ms])
            else:
                self.playhead_line = Line2D([current_ms, current_ms], [self.y_min, self.y_max], color='red')
                self.ax.add_line(self.playhead_line)
            self.canvas.draw_idle()


# ---------------------------
# Main
# ---------------------------
def main():
    app = QApplication(sys.argv)
    window = WaveformViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
