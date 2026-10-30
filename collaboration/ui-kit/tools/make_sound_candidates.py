"""以原創程式合成十個輕量非語音音效；輸出僅為 48 kHz WAV 候選。"""  # 不依賴付費生成服務或未核准編碼器。
from __future__ import annotations  # 型別可在 Python 3.12 穩定使用。
import json  # 保存可查證輸出清單。
import hashlib  # 每個實際音檔提供完整性雜湊。
import math  # 將峰值換算為 dBFS。
import wave  # 使用標準庫寫 PCM WAV。
from pathlib import Path  # 輸出限制在本套件資產目錄。
import numpy as np  # 本機已安裝，用於可重現的波形合成。

RATE = 48_000  # 規格要求原稿 48 kHz。
ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'audio-candidates'  # 不寫正式 App。
OUT = ROOT / 'wav'  # 播放版編碼器未備妥，單獨標示 WAV。
OUT.mkdir(parents=True, exist_ok=True)  # 僅建立本候選輸出目錄。

DESIGNS = {  # 每事件兩種可分辨的頻率、節奏與時長；全為原創程式波形。
    'ui-tap': [(.08, [(0.00, .065, 740, .22)], '柔和單擊'), (.09, [(0.00, .06, 560, .18), (.028, .052, 840, .10)], '雙層輕觸')],  # 操作回饋限制於 0.03–0.10 秒。
    'draft-saved': [(.28, [(0.00, .17, 523, .18), (.10, .16, 659, .15)], '上行兩音'), (.33, [(0.00, .20, 440, .16), (.13, .18, 587, .16)], '低暖兩音')],  # 保存提示限制於 0.15–0.35 秒。
    'experience-confirmed': [(.76, [(0.00, .52, 392, .14), (.12, .50, 494, .13), (.24, .46, 587, .12)], '溫和三音'), (.78, [(0.00, .48, 330, .12), (.18, .47, 440, .13), (.34, .42, 523, .13)], '緩升和聲')],  # 確認事件限制於 0.4–0.8 秒。
    'first-hatch': [(1.62, [(0.00, .62, 392, .10), (.28, .55, 523, .11), (.57, .55, 659, .11), (.88, .65, 784, .10)], '四音破曉'), (1.76, [(0.00, .70, 349, .09), (.36, .63, 440, .10), (.72, .59, 587, .11), (1.10, .60, 698, .10)], '慢速甦醒')],  # 首次孵化不循環。
    'goal-completed': [(1.18, [(0.00, .73, 392, .12), (.12, .72, 494, .11), (.25, .78, 587, .11)], '明亮收束'), (1.28, [(0.00, .78, 330, .11), (.20, .75, 440, .10), (.42, .74, 523, .11)], '沉穩收束')],  # 完成回執才可播放。
}  # 這些參數是設計候選，非 Boyi 已選定音色。

def render(total_seconds: float, notes: list[tuple[float, float, int, float]]) -> np.ndarray:  # 合成後留安全峰值。
    signal = np.zeros(round(total_seconds * RATE), dtype=np.float64)  # 全長固定取樣數。
    for start, duration, frequency, gain in notes:  # 每個音獨立包絡避免剪切。
        count = round(duration * RATE)  # 該音取樣長度。
        times = np.arange(count, dtype=np.float64) / RATE  # 正確時間軸。
        attack = np.minimum(1.0, times / .008)  # 8 ms 緩入避免點擊雜音。
        release = np.minimum(1.0, np.maximum(0.0, (duration - times) / .06))  # 60 ms 緩出。
        decay = np.exp(-times * 3.0 / duration)  # 輕量鐘音衰減。
        tone = np.sin(2 * np.pi * frequency * times) + .18 * np.sin(2 * np.pi * frequency * 2 * times)  # 兩個諧波，不用隨機噪音。
        begin = round(start * RATE)  # 音符起點。
        end = min(begin + count, len(signal))  # 不超出音效全長。
        signal[begin:end] += gain * tone[:end - begin] * attack[:end - begin] * release[:end - begin] * decay[:end - begin]  # 疊加時保留包絡。
    if np.max(np.abs(signal)) > 0: signal *= .24 / np.max(np.abs(signal))  # 峰值限制在約 -12.4 dBFS。
    return signal  # 聽審前只證明技術條件。

manifest = {'version': 'v1.1-candidate-wav-only', 'method': 'Original deterministic Python 3.12 + NumPy additive synthesis', 'sampleRate': RATE, 'channels': 1, 'format': 'PCM 16-bit WAV', 'usageScope': 'product_candidate', 'status': 'WAV candidates only; AAC/M4A and Ogg not produced; Boyi listening review pending', 'events': []}  # 不宣稱 AI 生成或完整播放版。
for event, candidates in DESIGNS.items():  # 五事件各兩種可實際播放 WAV。
    for index, (duration, notes, description) in enumerate(candidates, start=1):  # 固定編號使重跑可核對。
        samples = render(duration, notes)  # 合成一段波形。
        filename = f'{event}-{index:02d}.wav'  # 清楚的資產 ID。
        output = OUT / filename  # 僅寫套件候選檔。
        pcm = np.round(samples * 32767).astype('<i2')  # 16-bit little-endian PCM。
        with wave.open(str(output), 'wb') as wav:  # 標準 RIFF WAVE 容器。
            wav.setnchannels(1)  # 單聲道避免不必要的空間定位。
            wav.setsampwidth(2)  # 16-bit。
            wav.setframerate(RATE)  # 48 kHz。
            wav.writeframes(pcm.tobytes())  # 完整寫入真實音檔。
        peak = float(np.max(np.abs(samples)))  # 峰值由波形計算。
        rms = float(np.sqrt(np.mean(samples * samples)))  # RMS 僅供技術參考，非 LUFS。
        manifest['events'].append({'id': f'{event}-{index:02d}', 'event': event, 'candidate': index, 'path': f'wav/{filename}', 'description': description, 'durationSeconds': round(len(samples) / RATE, 3), 'peakDbfs': round(20 * math.log10(peak), 2), 'rmsDbfs': round(20 * math.log10(rms), 2), 'bytes': output.stat().st_size, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'playbackFormatsPending': ['AAC/M4A', 'Ogg']})  # 每檔來源、量測及雜湊可追溯。
(ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')  # 保留真實工具與限制。
print(f'Generated {len(manifest["events"])} WAV candidates at {RATE} Hz; AAC/M4A and Ogg pending.')  # 不宣稱聽審通過。
