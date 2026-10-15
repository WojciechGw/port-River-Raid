/* Included after collisions(): DUO reuses the native player rules without
 * stepping the world twice. Shared enemy/terrain/sound updates remain in rr_step. */
#pragma optimize(push, on)
static void duo_flight(void)
{
    static int16_t distance;
    if (duo_players[0].state!=1 || duo_players[1].state!=1) return;
    /* Native world velocity is speed/128 pixels per tick. The shared
     * camera follows the mean; the pilots move equally about its center.
     * Keep fractional distance and discard excess lead at the screen limit. */
    duo_gap+=(int16_t)duo_players[0].speed_y-duo_players[1].speed_y;
    if (duo_gap>DUO_LEAD*128) duo_gap=DUO_LEAD*128;
    if (duo_gap<-DUO_LEAD*128) duo_gap=-DUO_LEAD*128;
    distance=duo_gap>>7;
    duo_players[0].y=106-(distance>>1);
    duo_players[1].y=duo_players[0].y+distance;
}
static void duo_kill(void)
{
    if (duo_p->state!=1) return;
    duo_p->lives=duo_p->lives<=DUO_MAX_LIVES*8 && duo_p->lives>=8 ? duo_p->lives-8 : 0;
    duo_p->state=duo_p->lives ? 2 : 0;
    duo_p->timer=32; duo_p->missile_y=180;
    duo_p->shape=(uint16_t)rr_JetExplode-1;
    G(0xf8)=1; G(0xf9)=31;
}
static uint8_t duo_overlap(void)
{
    static uint8_t y,a,b;
    static int16_t dx,dy;
    dx=(int16_t)duo_players[1].x+(duo_players[1].reflect!=0)-
        duo_players[0].x-(duo_players[0].reflect!=0);
    if (dx<=-8 || dx>=8) return 0;
    for (y=1;y<=18;++y) {
        /* Native jet rows run from bottom to top. */
        dy=(int16_t)duo_players[1].y-duo_players[0].y+y;
        if (dy<1 || dy>18) continue;
        a=G(duo_players[0].shape+y); b=G(duo_players[1].shape+dy);
        if (duo_players[0].reflect) a=reverse_bits[a];
        if (duo_players[1].reflect) b=reverse_bits[b];
        if (dx>=0 ? (a&(b>>dx)) : (b&(a>>-dx))) return 1;
    }
    return 0;
}
static void duo_spawn(void)
{
    static uint8_t attempt,other;
    other=PLAYER^1;
    duo_p->shape=(uint16_t)rr_JetStraight-1;
    duo_p->missile_y=180; duo_p->reflect=duo_p->accel=duo_p->speed_x=0;
    duo_p->speed_y=duo_players[other].state==1 ? duo_players[other].speed_y : 64;
    /* Retain the fallen pilot's altitude and accumulated separation.
     * The survivor stays still vertically while flying alone. */
    /* Bound each retry to two candidates, including narrow/blocked rivers.
     * A stride of nine visits all 128 candidate columns before repeating. */
    for (attempt=0;attempt<2;++attempt) {
        duo_p->x=duo_p->spawn_x;
        duo_p->spawn_x=16+((duo_p->spawn_x-16+9)&127);
        if (duo_players[other].state==1 &&
            (int16_t)duo_p->x-duo_players[other].x>-12 &&
            (int16_t)duo_p->x-duo_players[other].x<12) continue;
        duo_load(duo_p); reflected=0; duo_dead=0;
        collisions();
        if (duo_dead || G(0xe4)!=255 ||
            (G(0xe8)!=255 && ID(G(0xe8))!=10)) continue;
        duo_p->fuel_hi=duo_p->fuel_lo=255;
        duo_p->joystick=255; duo_p->state=1; duo_p->timer=0;
        return;
    }
}
static void duo_restart_stage(void)
{
    static uint8_t n;
    /* Native partial initialization restores this section's saved RNG and
     * level, including rollback when the next section was generated early. */
    rr_duo_restart();
    for (n=0;n<2;++n) {
        duo_p=duo_players+n;
        duo_p->state=duo_p->lives ? 3 : 0;
        duo_p->timer=0; duo_p->missile_y=180;
        duo_p->spawn_x=n ? 84 : 68; duo_p->y=106;
        duo_p->fuel_hi=duo_p->fuel_lo=255;
    }
    duo_started=1; duo_over=duo_bridge=duo_turn=0; duo_gap=0;
}
void duo_tick(void)
{
    static uint8_t n,i,count,crossing,front;
    static uint16_t speed;
    if (!duo_started) {
        memset(duo_players,0,sizeof(duo_players));
        for (n=0;n<2;++n) {
            duo_p=duo_players+n;
            memset(duo_p->score,88,5); duo_p->score[5]=0;
            duo_p->lives=24; duo_p->state=3; duo_p->spawn_x=n ? 84 : 68;
            duo_p->y=106;
        }
        duo_started=1; duo_over=duo_bridge=duo_turn=0; duo_gap=0;
    }
    duo_flight();
    front=255;
    for (n=0;n<2;++n) if (duo_players[n].state==1) {
        if (duo_players[n].y<front) front=duo_players[n].y;
    }
    /* Record the first living pilot to pass. If the other pilot then dies,
     * this bridge is already behind the leader and cannot revive them.
     * With a waiting pilot, passage follows the sole survivor. Retain the
     * latch through throttle changes and subsequent block shifts. */
    crossing=count=0;
    for (n=0;n<3;++n) if (FLAGS(n)&128) {
        count=1;
        if (front!=255 && 136+(int16_t)OFFSET-(int16_t)n*32>=front+18) crossing=1;
    }
    if (crossing && !duo_bridge)
        for (n=0;n<2;++n) if (duo_players[n].state==2) {
            duo_players[n].state=3; duo_players[n].spawn_x=n ? 84 : 68;
        }
    if (crossing) duo_bridge=1;
    else if (!count) duo_bridge=0;
    duo_call=1;
    for (n=0;n<2;++n) {
        PLAYER=n; duo_p=duo_players+n;
        if (duo_p->timer) --duo_p->timer;
        if (duo_p->state==3 && !duo_over) duo_spawn();
    }
    /* Alternating priority resolves same-frame shots once, without a
     * permanent P1 advantage. The second shot sees the first destruction. */
    duo_turn^=1;
    for (i=0;i<2;++i) {
        n=i^duo_turn; PLAYER=n; duo_p=duo_players+n;
        if (duo_p->state!=1) continue;
        duo_load(duo_p); reflected=G(0xe0); duo_dead=0;
        collisions(); G(0xe0)=0;
        if (!duo_dead) rr_duo_player();
        if (tank_bonus) rr_tank_bonus();
        update_high_score(); duo_save(duo_p);
        if (duo_dead) duo_kill();
    }
    if (duo_players[0].state==1 && duo_players[1].state==1 && duo_overlap()) {
        duo_p=duo_players; duo_kill(); duo_p=duo_players+1; duo_kill();
    }
    speed=0; count=0;
    for (n=0;n<2;++n) if (duo_players[n].state==1) {
        speed+=duo_players[n].speed_y; ++count;
    }
    if (count) duo_started=2;
    else if (duo_started==2) {
        if (++duo_over>=32) {
            /* Each lost plane already paid once in duo_kill(). */
            if (duo_players[0].lives || duo_players[1].lives) duo_restart=1;
            else MODE=255;
        }
    }
    /* Native fuel alarm follows the living pilot with the lower reserve. */
    PLAYER=duo_players[0].state==1 && (duo_players[1].state!=1 ||
        duo_players[0].fuel_hi<=duo_players[1].fuel_hi) ? 0 : 1;
    duo_load(duo_players+PLAYER);
    G(0xb5)=count==2 ? speed>>1 : speed;
    reflected=G(0xe0); duo_call=0;
}
static void duo_render(void)
{
    static uint8_t n;
    static sprite_t *s,*shot;
    for (n=0;n<2;++n) {
        duo_p=duo_players+n; s=sprites+22+n; shot=sprites+20+n;
        s->y=shot->y=-256;
        if (ready || !duo_started) continue;
        if (duo_p->state==1 || duo_p->timer) {
            s->x=(duo_p->x+(duo_p->reflect!=0))*2; s->y=RIVER_TOP+duo_p->y;
            s->image=XRAM_DUO_JETS+(duo_p->timer ? 160 :
                duo_p->shape==(uint16_t)rr_JetMove-1 ? 80 : 0);
            s->palette=n ? XRAM_DUO_PALETTE : XRAM_JET_PALETTE;
            s->size=0x41; s->options=0x42|(duo_p->reflect ? 0x10 : 0);
        }
        if (duo_p->state==1 && duo_p->missile_y<=161) {
            s=shot; s->x=duo_p->missile_x*2; s->y=RIVER_TOP+153-(int16_t)duo_p->missile_y;
            s->image=BULLET_IMAGE; s->palette=XRAM_PALETTE; s->size=0x10; s->options=0x42;
        }
    }
    sprites[0]=sprites[22]; sprites[1].y=-256;
}
#pragma optimize(pop)
