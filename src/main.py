import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QFileDialog
from PyQt5.QtCore import Qt
from pydub import AudioSegment
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtGui import QCursor

class WaveformViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Waveform Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create main widget and layout
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.layout = QVBoxLayout(self.main_widget)

        # Create button for loading MP3
        self.load_button = QPushButton("Load MP3 File", self)
        self.load_button.clicked.connect(self.load_mp3)
        self.layout.addWidget(self.load_button)

        # Create matplotlib figure and canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        # Connect scroll event for zooming
        self.canvas.mpl_connect("scroll_event", self.on_scroll)

        # Initialize audio data
        self.audio = None
        self.samples = None
        self.sample_rate = None
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("axes_enter_event", self.on_axes_enter)
        self.canvas.mpl_connect("axes_leave_event", self.on_axes_leave)

        self._drag_active = False
        self._last_xdata = None

    def load_mp3(self):
        # Open file dialog to select MP3 file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MP3 File",
            "",
            "MP3 Files (*.mp3);;All Files (*)"
        )

        if file_path:
            try:
                # Load MP3 file using pydub
                self.audio = AudioSegment.from_mp3(file_path)
                self.samples = np.array(self.audio.get_array_of_samples())
                self.sample_rate = self.audio.frame_rate

                # Clear previous plot
                self.ax.clear()

                # Plot waveform
                time = np.linspace(0, len(self.samples) / self.sample_rate, num=len(self.samples))
                self.ax.plot(time, self.samples)
                self.ax.set_xlabel("Time (s)")
                self.ax.set_ylabel("Amplitude")
                self.ax.set_title("Waveform of " + file_path.split("/")[-1])

                # Update canvas
                self.canvas.draw()

            except Exception as e:
                print(f"Error loading MP3 file: {str(e)}")

    def on_scroll(self, event):
        """ Zoom in/out on scroll (x-axis only, supports macOS trackpad) """
        if self.samples is None:
            return

        # Current x-limits
        x_min, x_max = self.ax.get_xlim()
        x_range = x_max - x_min
        x_mid = event.xdata if event.xdata is not None else (x_min + x_max) / 2

        # Zoom factors
        zoom_in_factor = 0.8   # 20% zoom in
        zoom_out_factor = 1.25 # 25% zoom out

        # Detect scroll direction
        if hasattr(event, "step") and event.step != 0:  
            # Trackpad (continuous)
            if event.step > 0:
                scale_factor = zoom_in_factor
            else:
                scale_factor = zoom_out_factor
        else:
            # Mouse wheel fallback
            if event.button == "up":
                scale_factor = zoom_in_factor
            elif event.button == "down":
                scale_factor = zoom_out_factor
            else:
                return

        # Apply zoom
        new_range = x_range * scale_factor
        new_x_min = x_mid - (x_mid - x_min) * scale_factor
        new_x_max = x_mid + (x_max - x_mid) * scale_factor

        # Clamp to audio duration
        total_duration = len(self.samples) / self.sample_rate
        if new_x_min < 0:
            new_x_min = 0
        if new_x_max > total_duration:
            new_x_max = total_duration

        self.ax.set_xlim(new_x_min, new_x_max)
        self.canvas.draw_idle()

        """ Zoom in/out on scroll (x-axis only) """
        if self.samples is None:
            return

        # Get current x-limits
        x_min, x_max = self.ax.get_xlim()
        x_range = (x_max - x_min)
        x_mid = event.xdata if event.xdata is not None else (x_min + x_max) / 2

        # Zoom factor
        zoom_in_factor = 0.8   # 20% zoom in
        zoom_out_factor = 1.25 # 25% zoom out

        if event.button == 'up':  # scroll up -> zoom in
            scale_factor = zoom_in_factor
        elif event.button == 'down':  # scroll down -> zoom out
            scale_factor = zoom_out_factor
        else:
            scale_factor = 1.0

        new_range = x_range * scale_factor

        # Calculate new limits, keeping zoom centered on mouse
        new_x_min = x_mid - (x_mid - x_min) * scale_factor
        new_x_max = x_mid + (x_max - x_mid) * scale_factor

        # Prevent zooming out beyond total duration
        total_duration = len(self.samples) / self.sample_rate
        if new_x_min < 0:
            new_x_min = 0
        if new_x_max > total_duration:
            new_x_max = total_duration

        self.ax.set_xlim(new_x_min, new_x_max)
        self.canvas.draw_idle()
    def on_axes_enter(self, event):
        if event.inaxes is self.ax and not self._drag_active:
            self.canvas.setCursor(Qt.OpenHandCursor)

    def on_axes_leave(self, event):
        if not self._drag_active:
            self.canvas.setCursor(Qt.ArrowCursor)

    def on_press(self, event):
        """Start panning with left click inside the axes."""
        if event.inaxes is not self.ax or event.button != 1 or self.samples is None:
            return
        if event.xdata is None:
            return
        self._drag_active = True
        self._last_xdata = event.xdata
        self.canvas.setCursor(Qt.ClosedHandCursor)

    def on_release(self, event):
        """Stop panning."""
        if event.button != 1:
            return
        self._drag_active = False
        self._last_xdata = None
        # If still over axes, show open hand, else arrow
        self.canvas.setCursor(Qt.OpenHandCursor if event.inaxes is self.ax else Qt.ArrowCursor)

    def on_motion(self, event):
        """Pan left/right while dragging (x-axis only)."""
        if not self._drag_active or self.samples is None:
            return
        if event.inaxes is not self.ax or event.xdata is None or self._last_xdata is None:
            return

        # How far the mouse moved in data coords
        dx = self._last_xdata - event.xdata   # positive when dragging right

        x_min, x_max = self.ax.get_xlim()
        x_range = x_max - x_min
        if self.sample_rate is None or self.sample_rate == 0:
            return
        total_duration = len(self.samples) / float(self.sample_rate)

        # If the current view is wider than the content, pin to [0, total_duration]
        if x_range >= total_duration:
            self.ax.set_xlim(0, total_duration)
            self.canvas.draw_idle()
            self._last_xdata = event.xdata
            return

        # Shift and clamp
        new_x_min = x_min + dx
        new_x_max = x_max + dx
        if new_x_min < 0:
            new_x_min = 0
            new_x_max = x_range
        if new_x_max > total_duration:
            new_x_max = total_duration
            new_x_min = total_duration - x_range

        self.ax.set_xlim(new_x_min, new_x_max)
        self.canvas.draw_idle()

        # Update for incremental motion
        self._last_xdata = event.xdata


def main():
    app = QApplication(sys.argv)
    window = WaveformViewer()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
