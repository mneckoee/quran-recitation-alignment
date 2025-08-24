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
        
        # Initialize audio data
        self.audio = None
        self.samples = None
        self.sample_rate = None

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

def main():
    app = QApplication(sys.argv)
    window = WaveformViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()