"""Escape from gameplay must start and advance the farewell score."""
from emulator_checks import poke


def run_outro_audio_checks(case,sym,fixture,resume):
    tap=lambda key: ['press '+key,'run 3','release '+key,'run 3']
    for name,setup,muted in (
        ('flying',resume,False),
        ('flying-later',resume+['run 37'],False),
        ('firing',resume+['press space','run 10'],False),
        ('paused',[],False),
        ('blast',resume+[poke(0xfa,[23,15]),'run 2'],False),
        ('crash',[poke(0xb3,4)]+resume,False),
        ('gameover',[poke(0xc0,sym['rr_Copyright0']&255),poke(0xb3,4)]+resume+[
            f'wait 0x{sym["demo_splash_gameover_phase"]:04x} 1 60','run 2'],False),
        ('victory',[poke(sym['tanks'],[0]*30),poke(0xa2,8),poke(0x96,4),
            poke(0x9c,0x37),poke(0xbd,50),poke(0x90,128),poke(0xb5,0),
            'press down',poke(0xb2,75),poke(0xf5,80)]+resume+[
            f'peek 0x{sym["jingle_kind"]:04x} 1'],False),
        ('after-help',resume+['press f1','wait xram:0x00b0 2 120','release f1',
            'wait xram:0x02a4 222 5','press z','run 3','release z',
            'wait xram:0x0080 82 320','run 4'],False),
        ('music-restored',resume+tap('f9')*3,False),
        ('music-muted',resume+tap('f9'),True),
        ('all-muted',resume+tap('f9')*2,True),
    ):
        commands=fixture+setup+['release space','press escape',
            'wait xram:0x00b4 1 120','wait xram:0x00b0 2 120',
            f'peek 0x{sym["intro_active"]:04x} {int(not muted)}',
            f'dump 0x{sym["audio_muted"]:04x} 1']
        for _ in range(5):
            commands += ['dump xram:0x0100 256','run 12']
        commands += ['expect-exit 0 220']
        _,data=case('outro-audio-'+name,commands,gameplay=False)
        if not muted:
            assert not data[0][0]&1, 'Music unexpectedly muted'
            regs=data[1:]
            assert len(set(regs))>2, 'Outro notes do not advance'
            for channel,slot in enumerate((0,1,2,8,9,10)):
                assert any(r[0xb0+channel]&32 and r[0x43+slot]<63 for r in regs), \
                    f'Outro voice {channel} never sounds'
