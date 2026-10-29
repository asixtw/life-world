"""獨立核對 WAV 檔頭、取樣、峰值、長度與 manifest，不作主觀聽審。"""  # 音效真檔驗證與 Boyi 聽審分開。
import hashlib  # 比對實際檔案雜湊。
import json  # 讀取交付清單。
import math  # 峰值換算 dBFS。
import wave  # 標準庫讀 WAV header。
from pathlib import Path  # 路徑限 ui-kit 候選資產。
import numpy as np  # 精確讀取 16-bit PCM。

root = Path(__file__).resolve().parents[1] / 'assets' / 'audio-candidates'  # 不讀正式 App。
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))  # 清單為核對基準。
assert manifest['sampleRate'] == 48_000 and len(manifest['events']) == 10  # 五事件各兩候選。
assert set(item['event'] for item in manifest['events']) == {'ui-tap', 'draft-saved', 'experience-confirmed', 'first-hatch', 'goal-completed'}  # 事件清單完整。
assert all(sorted(item['candidate'] for item in manifest['events'] if item['event'] == event) == [1, 2] for event in {item['event'] for item in manifest['events']})  # 每事件恰兩個。
for item in manifest['events']:  # 每個音檔單獨檢查。
    file = root / item['path']  # 使用清單相對路徑。
    assert file.is_file() and file.stat().st_size == item['bytes']  # 無占位路徑或假大小。
    assert hashlib.sha256(file.read_bytes()).hexdigest() == item['sha256']  # bytes 與清單一致。
    with wave.open(str(file), 'rb') as wav:  # 檢查實際 RIFF WAVE。
        assert wav.getframerate() == 48_000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2  # 48kHz 單聲道 16-bit。
        frames = wav.readframes(wav.getnframes())  # 讀完全部 PCM。
        duration = wav.getnframes() / wav.getframerate()  # 由檔頭實測長度。
    samples = np.frombuffer(frames, dtype='<i2').astype(np.float64) / 32767  # 不依賴生成時浮點波形。
    peak = float(np.max(np.abs(samples)))  # 真檔峰值。
    assert abs(duration - item['durationSeconds']) < .002  # 清單時長不可編造。
    assert abs(20 * math.log10(peak) - item['peakDbfs']) < .05  # 量化後峰值近似清單值。
    assert peak < .5 and peak > .05  # 峰值保留餘裕且非無聲檔。
print('Verified 10 true 48 kHz PCM WAV candidates; metadata, hashes, durations and peaks match. AAC/M4A/Ogg and listening approval pending.')  # 範圍清楚。
