"""Actual projectile launches, audible pitch and enemy-effect lifetime."""
import struct
from emulator_checks import poke


def run_enemy_audio_checks(case,sym,fixture,resume,prefix,pcm=False):
    def frequency(regs,channel):
        b=regs[0xb0+channel]
        return ((b&3)*256+regs[0xa0+channel])*49716/(1<<(20-((b>>2)&7)))

    for shooter in ('bank','road','helicopter'):
        setup=fixture+[
            poke(sym['tanks'],[0]*30),poke(sym['bank_tanks'],[0]*39),
            poke(sym['helicopter_shots'],[0]*36),
            poke(sym['river_left'],[64]*192),poke(sym['river_right'],[80]*192),
            poke(0xf8,[0,0,0,0])]
        if shooter=='bank':
            setup += [poke(sym['bank_tanks'],struct.pack('<hhh7B',47,60,0,0,1,0,0,0,0,47))]
            fired=f'peek 0x{sym["bank_tanks"]+9:04x} 1'
        elif shooter=='road':
            setup += [poke(0x96,4),poke(0x9c,0x37),
                poke(sym['tanks']+10,struct.pack('<hBBB',47,1,0,0))]
            fired=f'peek 0x{sym["bank_tanks"]+26+9:04x} 1'
        else:
            setup += [poke(0xa2,5),poke(0x96,5),poke(0x9c,0x50),
                poke(0xbd,5),poke(sym['helicopter_types']+2,2)]
            fired=f'peek 0x{sym["helicopter_shots"]+12+4:04x} 1'
        commands=setup+resume+[fired,poke(0xfb,15),'run 1']
        # Remove shooters after the first actual launch so a second shot
        # cannot hide a stuck envelope. Existing projectiles remain harmless.
        commands += [poke(0xa0,[0]*6),poke(sym['tanks'],[0]*30),
            poke(sym['bank_tanks'],[0]*39)]
        sample=([f'dump 0x{sym["pcm_step"]:04x} 4',
                 f'dump 0x{sym["pcm_amplitude"]:04x} 2',
                 f'dump 0x{sym["pcm_tone"]:04x} 2'] if pcm else ['dump xram:0xc900 256'])
        for _ in range(20): commands+=sample+['run 1']
        _,data=case(f'{prefix}-shot-{shooter}',commands,rom_args=('/pcm',) if pcm else ())
        if pcm:
            active=[(int.from_bytes(step[:2],'little')*4000/65536,amp[0])
                    for step,amp,tone in zip(data[::3],data[1::3],data[2::3])
                    if tone[0] and amp[0]]
            assert active and data[-1][0]==0, 'PCM enemy tone missing or stuck'
            assert data[1][1] and data[2][1], 'Enemy shot suppressed the player shot'
        else:
            active=[(frequency(d,8),63-d[0x55]) for d in data if d[0xb8]&32]
            assert active and not data[-1][0xb8]&32, 'OPL enemy voice missing or stuck'
            assert data[0][0xb7]&32, 'Enemy shot suppressed the player shot'
            assert any(d[0xb0+n]&32 for d in data for n in range(3)), 'Melody stopped'
            assert 190<frequency(data[0],7)<405, 'Player pitch changed'
        pitches,levels=zip(*active)
        assert len(active)>=8 and levels[0]>levels[-1], 'Enemy shot lost its decay'
        assert (390<min(pitches)<max(pitches)<810 if shooter=='helicopter'
                else 90<min(pitches)<max(pitches)<205), 'Wrong enemy pitch relative to player'

        # Neither pause nor F9 may leave the tail sounding or replay it later.
        for key in ('p','f9'):
            # Music is disabled while paused/muted; effects then use C000.
            quiet_sample=sample if pcm else ['dump xram:0xc000 256']
            toggle=['press '+key,'run 3','release '+key,'run 3']*(2 if key=='f9' else 1)
            commands=setup+resume+[fired]+toggle+quiet_sample
            commands+=['press '+key,'run 3','release '+key,'run 3']
            commands+=[poke(0xa0,[0]*6),poke(sym['tanks'],[0]*30),
                poke(sym['bank_tanks'],[0]*39)]+sample
            _,data=case(f'{prefix}-shot-{shooter}-{key}',commands,rom_args=('/pcm',) if pcm else ())
            if pcm:
                assert data[1]==bytes(2), 'PCM effects still audible while paused/muted'
                assert not data[-1][0], 'PCM enemy shot resumed after pause/mute'
            else:
                assert not data[0][0xb8]&32 and not data[1][0xb8]&32, 'OPL enemy tail survives pause/mute'
