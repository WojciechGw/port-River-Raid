"""Unscaled, sliding splash overlay and restoration alongside live demo."""
import struct
from pathlib import Path


def run_demo_splash_checks(case,sym,boot,output,assets):
    scenes={}
    assert 'demo-splash.bin' not in assets
    for scene in ('plane','areyouready','gameover'):
        source=Path(__file__).resolve().parents[1]/f'assets/splash_{scene}.bmp'
        bmp=source.read_bytes()
        offset=struct.unpack_from('<I',bmp,10)[0]
        height=struct.unpack_from('<i',bmp,22)[0]
        rows=[bmp[offset+y*128:offset+(y+1)*128] for y in range(64)]
        if height>0: rows.reverse()
        asset=assets[f'splash-{scene}.bin']
        assert len(asset)==9216
        assert b''.join(asset[y*64:(y+1)*64]+asset[4096+y*64:4096+(y+1)*64]
                        for y in range(64))==b''.join(rows), 'Splash pixels were scaled or cropped'
        palettes=(asset[8192:8704],asset[8704:9216])
        assert palettes[0][:2]==palettes[1][:2]==b'\0\0', 'Black background must be transparent'
        # Compare all 256 entries to the BMP, including indices above the old
        # 64-color limit and the transparency bits of the monochrome version.
        dib=struct.unpack_from('<I',bmp,14)[0]
        count=struct.unpack_from('<I',bmp,46)[0] or 256
        for index,(color,mono) in enumerate(zip(struct.unpack('<256H',palettes[0]),
                                               struct.unpack('<256H',palettes[1]))):
            b,g,r=bmp[14+dib+4*index:17+dib+4*index] if index<count else (0,0,0)
            alpha=32 if r or g or b else 0
            r,g,b=r>>3,g>>3,b>>3
            gray=(r+2*g+b)//4
            assert color==(b<<11)|(g<<6)|alpha|r, index
            assert mono==(gray<<11)|(gray<<6)|alpha|gray, index
        scenes[scene]=(asset,palettes)
    asset,palettes=scenes['areyouready']
    opening=['press f1','wait xram:0x00b0 2 120','release f1','wait xram:0x02a4 222 5']
    closing=['press z','run 3','release z','wait xram:0x0080 82 320','run 4']
    frame=['dump xram:0x7500 40','dump xram:0x7580 512','dump xram:0x03e6 20']

    def check_frame(data,visible,mono=False,x=None,scene=None):
        descriptors,palette,jets=data
        assert descriptors[:20]==jets, 'Overlay list lost either player sprite'
        if x is None: x=200 if visible else -128
        for i in range(2):
            actual=struct.unpack_from('<hhHHBB',descriptors,20+i*10)
            assert actual==(x+64*i,4 if visible else -256,
                            0x6500 if i==0 else 0xd600,0x7580,0xff,3), actual
        if scene is None: scene='areyouready' if visible else 'plane'
        assert palette==scenes[scene][1][mono], 'Sliding splash faded or F4 failed'

    xpos=f'0x{sym["demo_splash_x"]:04x}'
    leaving=f'0x{sym["demo_splash_out"]:04x}'
    done=f'0x{sym["demo_splash_done"]:04x}'
    hidden=['peek xram:0x7516 0 255','peek xram:0x7520 0 255']
    visible=['peek xram:0x7516 4 0','peek xram:0x7520 4 0']
    restart=['press f2','run 3','release f2','run 3']
    snapshot=[f'dump {xpos} 2','dump xram:0x7580 512']
    commands=boot+restart
    entering=list(range(300,199,-2))
    exiting=list(range(144,-129,-16))  # Sample every two exit frames.
    for x in entering:
        commands += [f'wait xram:0x751e {(x+64)&255} 10']+frame
    commands+=['press space',f'wait {leaving} 1 3','release space']
    for x in exiting:
        commands += [f'wait xram:0x751e {(x+64)&255} 10']+frame
    commands+=hidden+['run 100','peek xram:0x0082 1']
    _,data=case('demo-splash-slide-in-out',commands)
    # Synchronize on published positions instead of sampling a descriptor
    # while the CPU is still preparing the next frame's palette/HUD.
    for i,x in enumerate(entering+exiting):
        check_frame(data[i*3:i*3+3],x>-128,x=x,scene='plane')

    _,data=case('demo-splash-slide-pause-f1',boot+restart+['run 20',
        'press p','run 3','release p','run 3']+snapshot+['run 150']+snapshot+
        opening+closing+snapshot+['press p','run 3','release p','run 3','run 80']+visible)
    assert data[:2]==data[2:4]==data[4:6] and 200<struct.unpack('<h',data[0])[0]<320, 'Pause/F1 moved the splash'

    # A short tap during entry immediately switches to the faster leftward
    # exit; the request remains latched until the entire image leaves.
    case('demo-splash-start-during-entry',boot+restart+['run 20',
        'press space',f'wait {leaving} 1 3','release space',f'wait {done} 1 60',
        'wait xram:0x7517 255 2']+hidden+['run 100','peek xram:0x0082 1'])

    _,data=case('demo-splash-slide-monochrome',boot+restart+['run 20',
        'press f4','run 3','release f4','run 3','press p','run 3','release p','run 3']+snapshot)
    assert data[1]==scenes['plane'][1][1] and 200<struct.unpack('<h',data[0])[0]<320, 'F4 changed the slide or palette'

    case('demo-splash-f2-cancels-start',boot+['run 10','press space',
        f'wait {leaving} 1 3','release space','run 5']+restart+[
        'run 80',f'peek {leaving} 0',f'peek {done} 0',f'peek {xpos} 200 0',
        f'peek 0x{sym["ready"]:04x} 2']+visible)

    _,data=case('demo-splash-slide-out-help',boot+['run 10','press space',
        f'wait {leaving} 1 3','release space','run 3',
        'press p','run 3','release p','run 3']+snapshot+opening+closing+snapshot+[
        f'peek {leaving} 1','press p','run 3','release p','run 3',
        'run 136','peek xram:0x0082 1']+hidden)
    assert data[:2]==data[2:] and -128<struct.unpack('<h',data[0])[0]<200, 'F1 changed a pending slide-out'
    for variant in range(3):
        commands=boot+['press f2','run 3','release f2','run 8']*variant+['run 125']
        commands+=frame+['dump xram:0x6500 4096','dump xram:0xd600 4096',
            f'shot "{(output/f"demo-splash-game{variant+1}.png").as_posix()}"',
            'run 120']+frame
        commands+=['press f4','run 3','release f4','run 3']+frame
        commands+=opening+closing+frame+['dump xram:0x6500 4096','dump xram:0xd600 4096']
        commands+=['press f4','run 3','release f4','run 3',
            'press space','run 136','release space','run 4']+frame
        commands+=opening+closing+frame
        # F2 returns to demo after a live game, including the DUO transition.
        commands+=['press f2','run 3','release f2','run 80']+frame
        _,data=case(f'demo-splash-game{variant+1}',commands)
        check_frame(data[:3],True)
        assert data[3]+data[4]==asset[:8192], 'Splash corrupted by startup/audio installation'
        check_frame(data[5:8],True)
        check_frame(data[8:11],True,True)
        check_frame(data[11:14],True,True)
        assert data[14]+data[15]==asset[:8192], 'F1 did not reload the sprite pixels'
        check_frame(data[16:19],False)
        check_frame(data[19:22],False)
        check_frame(data[22:25],True)

