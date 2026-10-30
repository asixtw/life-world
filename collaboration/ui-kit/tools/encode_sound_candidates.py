"""使用明示的既有 FFmpeg，從已驗證 WAV 產生可播放候選格式。"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def run(args):
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout + result.stderr


parser = argparse.ArgumentParser()
parser.add_argument('--ffmpeg', required=True, help='明確指定已核准、可執行的 FFmpeg 路徑')
args = parser.parse_args()
ffmpeg = Path(args.ffmpeg)
assert ffmpeg.is_file(), 'FFmpeg 不存在'
version = run([str(ffmpeg), '-hide_banner', '-version']).splitlines()[0]
root = Path(__file__).resolve().parents[1] / 'assets' / 'audio-candidates'
manifest_file = root / 'manifest.json'
manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
assert len(manifest['events']) == 10
for folder in ('m4a', 'ogg'):
    (root / folder).mkdir(exist_ok=True)
for item in manifest['events']:
    source = root / item['path']
    assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256']
    versions = {}
    for fmt, options in {
        'm4a': ['-c:a', 'aac', '-b:a', '96k', '-ar', '48000'],
        'ogg': ['-ac', '2', '-c:a', 'vorbis', '-strict', '-2', '-b:a', '96k', '-ar', '48000'],
    }.items():
        target = root / fmt / f"{item['id']}.{fmt}"
        run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), *options, str(target)])
        data = target.read_bytes()
        assert len(data) > 100 and (b'ftyp' in data[:16] if fmt == 'm4a' else data[:4] == b'OggS')
        versions[fmt] = {'path': f"{fmt}/{item['id']}.{fmt}", 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'sampleRate': 48000, 'channels': 1 if fmt == 'm4a' else 2}
    item['playbackVersions'] = versions
    item.pop('playbackFormatsPending', None)
manifest['version'] = 'v1.1-candidate-three-formats'
manifest['status'] = 'WAV + AAC/M4A + Ogg candidates; browser decode and Boyi listening review pending'
manifest['playbackEncoder'] = {'version': version, 'aac': 'FFmpeg native AAC, 96 kbps, mono', 'ogg': 'FFmpeg experimental native Vorbis, 96 kbps, stereo duplicated from mono'}
manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"Encoded {len(manifest['events'])} AAC/M4A and {len(manifest['events'])} Ogg candidate files with {version}")
