import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QFileDialog
from PyQt5.QtCore import Qt
from pydub import AudioSegment
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class WaveformViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Waveform Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Main widget and layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Button to load MP3
        self.load_button = QPushButton("Load MP3 File", self)
        self.load_button.clicked.connect(self.load_mp3)
        self.layout.addWidget(self.load_button)

        # Matplotlib figure and canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        # Connect events
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
        self._drag_active = False
        self._last_xdata = None

    # ---------------------------
    # File loading
    # ---------------------------
    def load_mp3(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MP3 File",
            "",
            "MP3 Files (*.mp3);;All Files (*)"
        )
        if not file_path:
            return

        try:
            # Load MP3
            self.audio = AudioSegment.from_mp3(file_path)
            self.samples = np.array(self.audio.get_array_of_samples())
            self.sample_rate = self.audio.frame_rate

            # Stereo fix: convert to mono
            if self.audio.channels == 2:
                self.samples = self.samples.reshape((-1, 2)).mean(axis=1)

            # Set initial x-limits to full duration
            duration = len(self.samples) / self.sample_rate
            self.ax.set_xlim(0, duration)

            # Draw waveform
            self.update_waveform(title="Waveform of " + file_path.split("/")[-1])

        except Exception as e:
            print(f"Error loading MP3 file: {e}")

    # ---------------------------
    # Waveform drawing
    # ---------------------------
    def update_waveform(self, title="Waveform"):
        """Draw waveform with dynamic downsampling."""
        if self.samples is None or self.sample_rate is None:
            return

        # Visible x-range
        x_min, x_max = self.ax.get_xlim()
        total_duration = len(self.samples) / self.sample_rate

        # Clamp
        x_min = max(0, x_min)
        x_max = min(total_duration, x_max)

        # Convert to sample indices
        start_idx = int(x_min * self.sample_rate)
        end_idx = int(x_max * self.sample_rate)
        if end_idx <= start_idx:
            return

        visible_samples = end_idx - start_idx
        canvas_width = max(1, self.canvas.width())

        # Downsample factor
        samples_per_pixel = visible_samples / (2*canvas_width)
        step = max(1, int(samples_per_pixel))

        # Decimate
        decimated_samples = self.samples[start_idx:end_idx:step]
        decimated_time = np.linspace(x_min, x_max, num=len(decimated_samples))

        # Clear and redraw
        self.ax.clear()
        self.ax.plot(decimated_time, decimated_samples, linewidth=0.8)
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Amplitude")
        self.ax.set_title(title)

        self.canvas.draw_idle()

    # ---------------------------
    # Scroll zoom
    # ---------------------------
    def on_scroll(self, event):
        if self.samples is None:
            return

        x_min, x_max = self.ax.get_xlim()
        x_range = x_max - x_min
        x_mid = event.xdata if event.xdata is not None else (x_min + x_max) / 2

        zoom_in_factor = 0.8
        zoom_out_factor = 1.25

        if hasattr(event, "step") and event.step != 0:  # macOS trackpad
            scale_factor = zoom_in_factor if event.step > 0 else zoom_out_factor
        else:  # mouse wheel
            if event.button == "up":
                scale_factor = zoom_in_factor
            elif event.button == "down":
                scale_factor = zoom_out_factor
            else:
                return

        new_x_min = x_mid - (x_mid - x_min) * scale_factor
        new_x_max = x_mid + (x_max - x_mid) * scale_factor

        # Clamp
        total_duration = len(self.samples) / self.sample_rate
        if new_x_min < 0:
            new_x_min = 0
        if new_x_max > total_duration:
            new_x_max = total_duration

        self.ax.set_xlim(new_x_min, new_x_max)
        self.update_waveform()

    # ---------------------------
    # Pan with drag
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
        total_duration = len(self.samples) / self.sample_rate

        if x_range >= total_duration:
            self.ax.set_xlim(0, total_duration)
            self.update_waveform()
            self._last_xdata = event.xdata
            return

        new_x_min = x_min + dx
        new_x_max = x_max + dx

        if new_x_min < 0:
            new_x_min = 0
            new_x_max = x_range
        if new_x_max > total_duration:
            new_x_max = total_duration
            new_x_min = total_duration - x_range

        self.ax.set_xlim(new_x_min, new_x_max)
        self.update_waveform()
        self._last_xdata = event.xdata


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
