/* Original HMI frame transport and input console. SPDX-License-Identifier: GPL-2.0-or-later */
#include "qemu/osdep.h"
#include "qemu/module.h"
#include "qemu/bswap.h"
#include "qemu/timer.h"
#include "qapi/error.h"
#include "hw/core/qdev-properties.h"
#include "hw/core/qdev-properties-system.h"
#include "chardev/char-fe.h"
#include "ui/console.h"
#include "ui/input.h"
#include "ui/vgafont.h"
#include "qom/object.h"
#define TYPE_MIB_DISPLAY "mib-display"
OBJECT_DECLARE_SIMPLE_TYPE(MIBDisplay, MIB_DISPLAY)
#define FW 800
#define FH 480
#define WW 1000
#define WH 600
struct MIBDisplay {
    DeviceState parent_obj;
    CharFrontend chr;
    QemuConsole *con;
    QemuInputHandlerState *input;
    uint8_t header[8], *pixels;
    unsigned received;
    int x, y, pressed, press_x, press_y;
    bool touching, moved;
    bool has_frame;
    unsigned spinner_phase;
    QEMUTimer *loading_timer;
};
static void label(DisplaySurface *ds, int x, int y, const char *text) {
    uint32_t *p = (uint32_t *)surface_data(ds);
    int stride = surface_stride(ds) / 4;
    for (; *text; text++, x += 8) {
        for (int r=0;r<16;r++) for(int c=0;c<8;c++) {
            if (vgafont16[(unsigned char)*text*16+r] & (0x80 >> c))
                p[(y+r)*stride+x+c]=0xffdddddd;
        }
    }
}
static void button_outline(DisplaySurface *ds, int x, int y, int w, int h) {
    uint32_t *p = (uint32_t *)surface_data(ds);
    int stride = surface_stride(ds) / 4;
    for (int row=0; row<h; row++) for (int col=0; col<w; col++) {
        bool edge = row==0 || row==h-1 || col==0 || col==w-1;
        p[(y+row)*stride+x+col] = edge ? 0xff65656d : 0xff29292f;
    }
}
static const char *left[] = {"RADIO","MEDIA","PHONE","VOICE"};
static const char *right[] = {"NAV","TRAFFIC","CAR","MENU"};
static const char *buttons[] = {"RADIO","MEDIA","PHONE","VOICE","NAV","TRAFFIC","CAR","MENU","POWER","TUNE"};
static void paint(MIBDisplay *s) {
    DisplaySurface *ds=qemu_console_surface(s->con);
    uint32_t *p=(uint32_t *)surface_data(ds); int stride=surface_stride(ds)/4;
    for(int y=0;y<WH;y++) for(int x=0;x<WW;x++) p[y*stride+x]=0xff202024;
    for(int y=0;y<FH;y++) for(int x=0;x<FW;x++) {
        uint8_t *v=s->pixels+(y*FW+x)*4;
        p[(y+60)*stride+x+100]=0xff000000|(v[0]<<16)|(v[1]<<8)|v[2];
    }
    if (!s->has_frame) {
        /* Twelve dots animate without any guest or graphics bridge activity. */
        static const int dx[12]={0,18,31,36,31,18,0,-18,-31,-36,-31,-18};
        static const int dy[12]={-36,-31,-18,0,18,31,36,31,18,0,-18,-31};
        for (int i=0;i<12;i++) {
            unsigned age=(s->spinner_phase+12-i)%12;
            unsigned red=70+(11-age)*16;
            uint32_t color=0xff000000|(red<<16)|0x2020;
            for (int y=-4;y<=4;y++) for (int x=-4;x<=4;x++)
                if (x*x+y*y<=16) p[(240+dy[i]+y)*stride+500+dx[i]+x]=color;
        }
        label(ds,396,315,"Starting the SEAT system...");
        label(ds,384,345,"This may take 2-3 minutes.");
    }
    label(ds, 324, 20, "SEAT MIB2 - ORIGINAL QNX HMI");
    for(int i=0;i<4;i++) {
        button_outline(ds,6,84+i*85,88,73);
        button_outline(ds,906,84+i*85,88,73);
    }
    button_outline(ds,6,486,88,46);button_outline(ds,906,486,88,46);
    for(int side=0;side<2;side++) for(int knob=0;knob<2;knob++)
        button_outline(ds,6+side*900+knob*50,538,38,28);
    for(int i=0;i<4;i++) { label(ds, 18, 112+i*85,left[i]);label(ds,910,112+i*85,right[i]); }
    label(ds, 10, 514, "POWER/VOL");label(ds,918,514,"TUNE");
    label(ds, 18, 546, "[-]  [+]");label(ds,918,546,"[-]  [+]");
    label(ds, 260, 570, "Touch: mouse | Knobs: wheel | F1-F8: buttons");
    qemu_console_update_full(s->con);
}
static void loading_tick(void *opaque) {
    MIBDisplay *s=opaque;
    if (s->has_frame) return;
    s->spinner_phase=(s->spinner_phase+1)%12;
    paint(s);
    timer_mod(s->loading_timer,qemu_clock_get_ms(QEMU_CLOCK_REALTIME)+100);
}
static int can_read(void *opaque) { MIBDisplay *s=opaque; return s->received<8 ? 8-s->received : FW*FH*4+8-s->received; }
static void read_frame(void *opaque,const uint8_t *buf,int size) {
    MIBDisplay *s=opaque;
    if(s->received<8) {
        memcpy(s->header+s->received,buf,size);s->received+=size;
        if(s->received==8 && (memcmp(s->header,"MIBF",4)||ldl_le_p(s->header+4)!=FW*FH*4)) {
            s->received=0;
        }
    } else {
        memcpy(s->pixels+s->received-8,buf,size);s->received+=size;
        if(s->received==FW*FH*4+8) {
            s->has_frame=true;timer_del(s->loading_timer);
            paint(s);s->received=0;
        }
    }
}
static void chr_event(void *opaque,QEMUChrEvent event) { MIBDisplay *s=opaque;if(event==CHR_EVENT_CLOSED)s->received=0; }
static void send_touch(MIBDisplay *s,const char *phase) {
    char msg[160];int n=snprintf(msg,sizeof(msg),"{\"type\":\"touch\",\"phase\":\"%s\",\"x\":%d,\"y\":%d}\n",phase,CLAMP(s->x-100,0,799),CLAMP(s->y-60,0,479));
    qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
}
static void send_button(MIBDisplay *s,int button) {
    if (button>=10) {
        char msg[100];
        int n=snprintf(msg,sizeof(msg),"{\"type\":\"encoder\",\"name\":\"%s\",\"delta\":%d}\n",
                       button<12?"VOLUME":"TUNE",button%2?1:-1);
        qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
        return;
    }
    char msg[96];int n=snprintf(msg,sizeof(msg),"{\"type\":\"button\",\"name\":\"%s\"}\n",buttons[button]);qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
}
static int hit(MIBDisplay *s) {
    if(s->x>=100 && s->x<900)return -1;
    if(s->y>=536 && s->y<568)
        return s->x<100 ? (s->x<50?10:11) : (s->x<950?12:13);
    if(s->y>=480)return s->x<100?8:9;
    int row=(s->y-80)/85;
    return s->y>=80 && row<4 ? row+(s->x<100?0:4) : -1;
}
static void input_event(DeviceState *dev,QemuConsole *src,QemuInputEvent *evt) {
    MIBDisplay *s=MIB_DISPLAY(dev);
    if(evt->type==INPUT_EVENT_KIND_ABS) {
        if(evt->abs.axis==INPUT_AXIS_X)s->x=qemu_input_scale_axis(evt->abs.value,0,0x7fff,0,WW-1);
        else s->y=qemu_input_scale_axis(evt->abs.value,0,0x7fff,0,WH-1);
        if(s->touching && (abs(s->x-s->press_x)>3 || abs(s->y-s->press_y)>3))s->moved=true;
    } else if(evt->type==INPUT_EVENT_KIND_BTN) {
        if(evt->btn.button==INPUT_BUTTON_LEFT) {
            if(evt->btn.down) {s->pressed=hit(s);s->touching=s->x>=100&&s->x<900&&s->y>=60&&s->y<540;s->press_x=s->x;s->press_y=s->y;s->moved=false;if(s->touching)send_touch(s,"down");}
            else {if(s->touching)send_touch(s,s->moved?"release":"up");else if(s->pressed>=0&&s->pressed==hit(s))send_button(s,s->pressed);s->touching=false;s->pressed=-1;}
        } else if(evt->btn.down && (evt->btn.button==INPUT_BUTTON_WHEEL_UP||evt->btn.button==INPUT_BUTTON_WHEEL_DOWN)) {
            char msg[100];int n=snprintf(msg,sizeof(msg),"{\"type\":\"encoder\",\"name\":\"%s\",\"delta\":%d}\n",s->x<500?"VOLUME":"TUNE",evt->btn.button==INPUT_BUTTON_WHEEL_UP?1:-1);qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
        }
    } else if(evt->type==INPUT_EVENT_KIND_KEY && !evt->key.down && evt->key.key>=59 && evt->key.key<=66)send_button(s,evt->key.key-59);
}
static void input_sync(DeviceState *dev) { MIBDisplay *s=MIB_DISPLAY(dev);if(s->touching&&s->moved)send_touch(s,"move"); }
static const QemuInputHandler handler={.name="SEAT touch and buttons",.mask=INPUT_EVENT_MASK_ABS|INPUT_EVENT_MASK_BTN|INPUT_EVENT_MASK_KEY,.event=input_event,.sync=input_sync};
static const GraphicHwOps graphics={0};
static void realize(DeviceState *dev,Error **errp) {
    MIBDisplay *s=MIB_DISPLAY(dev);
    if(!qemu_chr_fe_backend_connected(&s->chr)) {error_setg(errp,"mib-display requires chardev");return;}
    s->pixels=g_malloc0(FW*FH*4);s->pressed=-1;
    s->con=qemu_graphic_console_create(dev,0,&graphics,dev);qemu_console_resize(s->con,WW,WH);paint(s);
    s->loading_timer=timer_new_ms(QEMU_CLOCK_REALTIME,loading_tick,s);
    timer_mod(s->loading_timer,qemu_clock_get_ms(QEMU_CLOCK_REALTIME)+100);
    qemu_chr_fe_set_handlers(&s->chr,can_read,read_frame,chr_event,NULL,s,NULL,true);
    s->input=qemu_input_handler_register(dev,&handler);qemu_input_handler_activate(s->input);
    /* Sole input handler on SabreLite; device ID is not registered until realize returns. */
}
static const Property props[]={DEFINE_PROP_CHR("chardev",MIBDisplay,chr)};
static void class_init(ObjectClass *klass,const void *data) {
    DeviceClass *dc=DEVICE_CLASS(klass);dc->realize=realize;dc->desc="SEAT original HMI frame and input bridge";set_bit(DEVICE_CATEGORY_DISPLAY,dc->categories);device_class_set_props(dc,props);
}
static const TypeInfo info={.name=TYPE_MIB_DISPLAY,.parent=TYPE_DEVICE,.instance_size=sizeof(MIBDisplay),.class_init=class_init};
static void register_types(void) {type_register_static(&info);}
type_init(register_types)
