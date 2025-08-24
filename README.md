# 🎶 MP3 Waveform Viewer with Transcription Markers

This project is a **PyQt5 desktop application** that lets you:

- Load an MP3 file and visualize its **waveform** using Matplotlib.
- Enter a **transcription** of the audio, which automatically places **markers** along the waveform.
- **Select & drag markers** to adjust their positions.
- Use **arrow keys** to fine-tune marker positions (movement step depends on zoom level).
- Press **spacebar** to play/pause audio — playback starts from the **selected marker** (if any).
- **Export markers** as an array of timestamps (in milliseconds) and automatically copy them to your clipboard.

---

## ✨ Features

- 🎵 Load and visualize MP3 waveform.
- 📝 Add transcription text → markers are auto-placed across the audio.
- 🎯 Select markers (turns green when selected).
- 🖱️ Drag and drop markers.
- ⌨️ Adjust marker position with **Left/Right Arrow** keys.
- ⏯️ Play/Pause audio with **Spacebar**.
- 📤 Export marker times as an array (copied directly to clipboard).

---

## 🚀 Installation

### 1. Clone this repository:

```bash
git clone https://github.com/your-username/mp3-waveform-viewer.git
cd mp3-waveform-viewer
```

### 2. Create a virtual environment (optional but recommended):

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Run the app:

```bash
python main.py
```

---

## 📦 Requirements

- Python 3.8+
- [PyQt5](https://pypi.org/project/PyQt5/)
- [matplotlib](https://pypi.org/project/matplotlib/)
- [numpy](https://pypi.org/project/numpy/)
- [sounddevice](https://pypi.org/project/sounddevice/)
- [pydub](https://pypi.org/project/pydub/) (requires ffmpeg installed)

You can install them manually if needed:

```bash
pip install PyQt5 matplotlib numpy sounddevice pydub
```

⚠️ **Note:**  
`pydub` requires **FFmpeg**.

- On macOS: `brew install ffmpeg`
- On Linux: `sudo apt install ffmpeg`
- On Windows: [Download FFmpeg](https://ffmpeg.org/download.html) and add it to PATH.

---

## 🎹 Controls

- **Load MP3 File** → Opens file dialog to load audio.
- **Transcription Field** → Paste or type text, then press **Submit Transcription** to add markers.
- **Spacebar** → Play/Pause audio (starts from selected marker if available).
- **Left/Right Arrow Keys** → Move selected marker slightly left/right (step depends on zoom).
- **Mouse Drag** → Pan waveform.
- **Scroll Wheel** → Zoom in/out on waveform.
- **Click/Drag Marker** → Select and move a marker (turns green).
- **Export Button** → Copies marker timestamps (in ms) as array to clipboard.

---

## 📤 Example Export

If you added 4 markers, pressing **Export** might give:

```
[1200, 4500, 12300, 17890]
```

This array is automatically copied to your clipboard.

---

## 📸 Screenshots (optional)

_(Add some screenshots of the waveform with markers, transcription field, and export result here.)_

---

## 🛠️ Future Improvements

- Save & load marker configurations.
- Support for multiple transcriptions.
- Export to JSON/CSV with word labels.
- Real-time alignment assistance.

---

## 📝 License

MIT License © 2025 Your Name
