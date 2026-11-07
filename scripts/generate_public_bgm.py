"""重製三段原創程序BGM，不使用模型、外部音源或現有旋律。"""
from pathlib import Path
import math,wave,array,argparse

def main():
    """僅寫登入／設定目標／世界三個已命名WAV；不改其他素材。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('app/static/audio'))
    audio=parser.parse_args().output_dir
    audio.mkdir(parents=True,exist_ok=True)
    rate=24000;duration=16
    for scene,base in [('login',57),('goals',60),('world',62)]:
     samples=[]
     for i in range(rate*duration):
      t=i/rate;bar=int(t//4);position=t%4
      root=base+[0,5,7,0][bar];value=0.0
      envelope=min(1,position/.65,(4-position)/.9)
      for step in [0,7,12,16]:
       f=440*2**((root+step-69)/12);value+=.027*envelope*(math.sin(2*math.pi*f*t)+.18*math.sin(4*math.pi*f*t))
      # 簡短、稀疏的原創五聲音階點綴；與柔和pad分層。
      beat=t%2;note=base+12+[0,4,7,9,7,4,2,0][int(t//2)]
      f=440*2**((note-69)/12);value+=.045*math.exp(-beat*3.8)*min(1,beat/.025)*math.sin(2*math.pi*f*t)
      value*=min(1,t/.4,(duration-t)/.4);samples.append(max(-32767,min(32767,round(value*32767))))
     dst=audio/(scene+'-bgm.wav')
     with wave.open(str(dst),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(array.array('h',samples).tobytes())
     rms=math.sqrt(sum((x/32768)**2 for x in samples)/len(samples));peak=max(abs(x) for x in samples)/32768

if __name__=='__main__':main()
