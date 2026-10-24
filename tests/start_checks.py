"""Starting a game consumes fire until release, including both DUO pilots."""


def run_start_checks(case,sym,boot):
    for variant in range(3):
        select=boot+['press f2','run 3','release f2','run 8']*variant
        for key in ('space','enter','0xe0','r','f3','pad-fire','pad-select','short-space'):
            pad=key.startswith('pad-')
            short=key=='short-space'
            button='b' if key=='pad-fire' else 'select' if pad else 'space' if short else key
            press=f'pad 0 press {button}' if pad else f'press {button}'
            release=f'pad 0 release {button}' if pad else f'release {button}'
            commands=select+(['pad 0 connect'] if pad else [])+[press,'run 3']
            if short: commands+=[release]
            commands += [f'wait 0x{sym["ready"]:04x} 0 90',
                         'wait xram:0x0082 1 120','run 8']
            # Inspect the first live frames, while the start button is still
            # held: no missile and no native shot envelope may be present.
            for _ in range(8):
                commands+=['peek 0xfb 0','peek 0xb2 180','run 1']
                if variant==2:
                    commands += [f'peek 0x{sym["duo_players"]:04x} 180',
                                 f'peek 0x{sym["duo_players"]+23:04x} 180']
            if not short: commands+=[release]
            pilot=int(variant==2 and key in ('0xe0','pad-fire'))
            fire='0xe0' if pilot else 'space'
            commands+=['run 3',f'press {fire}','run 3','dump 0xfb 1','dump 0xb2 1']
            if variant==2: commands += [f'dump 0x{sym["duo_players"]+23*pilot:04x} 1']
            commands += [f'release {fire}','run 2']
            _,data=case(f'start-no-shot-game{variant+1}-{key}',commands)
            assert data[0][0]>0, 'A fresh fire press did not play the shot sound'
            assert (data[2] if variant==2 else data[1])[0]<162, 'A fresh fire press did not launch a missile'
