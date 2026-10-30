"""獨立核對 WAV 檔頭、取樣、峰值、長度與 manifest，不作主觀聽審。"""  # 音效真檔驗證與 Boyi 聽審分開。
import hashlib  # 比對實際檔案雜湊。
import json  # 讀取交付清單。
import math  # 峰值換算 dBFS。
import wave  # 標準庫讀 WAV header。
import argparse  # 編碼容器的實際時長可選用本機工具再查。
import re  # 解析 FFmpeg 列出的時間與取樣率。
import subprocess  # 不送出任何網路請求。
from pathlib import Path  # 路徑限 ui-kit 候選資產。
import numpy as np  # 精確讀取 16-bit PCM。

root = Path(__file__).resolve().parents[1] / 'assets' / 'audio-candidates'  # 不讀正式 App。
parser = argparse.ArgumentParser()
parser.add_argument('--ffmpeg', help='可選：明確指定已安裝工具，讀取三格式容器 metadata')
args = parser.parse_args()
if args.ffmpeg: assert Path(args.ffmpeg).is_file(), '指定的 FFmpeg 不存在'
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))  # 清單為核對基準。
assert manifest['sampleRate'] == 48_000 and len(manifest['events']) == 10  # 五事件各兩候選。
assert set(item['event'] for item in manifest['events']) == {'ui-tap', 'draft-saved', 'experience-confirmed', 'first-hatch', 'goal-completed'}  # 事件清單完整。
assert all(sorted(item['candidate'] for item in manifest['events'] if item['event'] == event) == [1, 2] for event in {item['event'] for item in manifest['events']})  # 每事件恰兩個。
duration_ranges = {'ui-tap': (.03, .10), 'draft-saved': (.15, .35), 'experience-confirmed': (.4, .8), 'first-hatch': (1.5, 3.0), 'goal-completed': (.8, 1.5)}  # v1.1 逐事件範圍，不只全域上限。
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
    assert duration_ranges[item['event']][0] <= duration <= duration_ranges[item['event']][1], f"{item['id']} duration {duration} outside event range"  # 候選需符合本事件規格。
    assert abs(20 * math.log10(peak) - item['peakDbfs']) < .05  # 量化後峰值近似清單值。
    assert peak < .5 and peak > .05  # 峰值保留餘裕且非無聲檔。
    if 'playbackVersions' in item:  # 僅在真正產出播放版後查驗。
        for fmt, signature in [('m4a', b'ftyp'), ('ogg', b'OggS')]:
            version = item['playbackVersions'][fmt]  # 清單需包含各格式真路徑。
            playback = root / version['path']  # 不讀目錄外資料。
            data = playback.read_bytes()  # 避免只核路徑而漏掉空檔。
            assert len(data) == version['bytes'] and hashlib.sha256(data).hexdigest() == version['sha256']  # 真檔核對。
            assert (signature in data[:16]) if fmt == 'm4a' else data.startswith(signature)  # 容器檔頭。
            assert version['sampleRate'] == 48_000  # 轉碼參數與清單一致，解碼由瀏覽器另驗。
            if args.ffmpeg:
                info = subprocess.run([args.ffmpeg, '-hide_banner', '-i', str(playback)], capture_output=True, text=True).stderr
                match = re.search(r'Duration: (\d\d):(\d\d):(\d\d\.\d+)', info)
                assert match and '48000 Hz' in info, f"{item['id']}.{fmt} has invalid container metadata"
                actual = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
                low, high = duration_ranges[item['event']]
                assert low - .01 <= actual <= high + .01, f"{item['id']}.{fmt} duration {actual} outside event range"
print('Verified 10 true 48 kHz PCM WAV candidates and available playback files' + (' including 20 probed container durations' if args.ffmpeg else '') + '; Boyi listening approval pending.')  # 範圍清楚。
