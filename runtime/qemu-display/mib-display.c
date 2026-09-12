/* Original HMI frame transport and input console. SPDX-License-Identifier: GPL-2.0-or-later */
#include "qemu/osdep.h"
#include "qemu/module.h"
#include "qemu/bswap.h"
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
    int x, y, pressed;
    bool touching, moved;
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
    label(ds, 324, 20, "SEAT MIB2 - ORIGINAL QNX HMI");
    for(int i=0;i<4;i++) { label(ds, 18, 112+i*85,left[i]);label(ds,910,112+i*85,right[i]); }
    label(ds, 10, 514, "POWER/VOL");label(ds,918,514,"TUNE");
    label(ds, 260, 570, "Touch: mouse | Knobs: wheel | F1-F8: buttons");
    qemu_console_update_full(s->con);
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
        if(s->received==FW*FH*4+8) {paint(s);s->received=0;}
    }
}
static void chr_event(void *opaque,QEMUChrEvent event) { MIBDisplay *s=opaque;if(event==CHR_EVENT_CLOSED)s->received=0; }
static void send_touch(MIBDisplay *s,const char *phase) {
    char msg[160];int n=snprintf(msg,sizeof(msg),"{\"type\":\"touch\",\"phase\":\"%s\",\"x\":%d,\"y\":%d}\n",phase,CLAMP(s->x-100,0,799),CLAMP(s->y-60,0,479));
    qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
}
static void send_button(MIBDisplay *s,int button) {
    char msg[96];int n=snprintf(msg,sizeof(msg),"{\"type\":\"button\",\"name\":\"%s\"}\n",buttons[button]);qemu_chr_fe_write(&s->chr,(uint8_t *)msg,n);
}
static int hit(MIBDisplay *s) {
    if(s->x>=100 && s->x<900)return -1;
    if(s->y>=480)return s->x<100?8:9;
    int row=(s->y-80)/85;
    return s->y>=80 && row<4 ? row+(s->x<100?0:4) : -1;
}
static void input_event(DeviceState *dev,QemuConsole *src,QemuInputEvent *evt) {
    MIBDisplay *s=MIB_DISPLAY(dev);
    if(evt->type==INPUT_EVENT_KIND_ABS) {
        if(evt->abs.axis==INPUT_AXIS_X)s->x=qemu_input_scale_axis(evt->abs.value,0,0x7fff,0,WW-1);
        else s->y=qemu_input_scale_axis(evt->abs.value,0,0x7fff,0,WH-1);
        if(s->touching)s->moved=true;
    } else if(evt->type==INPUT_EVENT_KIND_BTN) {
        if(evt->btn.button==INPUT_BUTTON_LEFT) {
            if(evt->btn.down) {s->pressed=hit(s);s->touching=s->x>=100&&s->x<900&&s->y>=60&&s->y<540;s->moved=false;if(s->touching)send_touch(s,"down");}
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
