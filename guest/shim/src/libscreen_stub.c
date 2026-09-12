/* Phase-1 fake libscreen.so.1: an in-process object model with logging.
 * No Screen server, no /dev/screen. Property ids follow the QNX Screen enum
 * (reports/screen-property-enum.txt). Unknown functions log and return 0.
 */
#define STUB_LOG_ENV "LIBSCREEN_STUB_LOG"
#define STUB_LOG_DEFAULT "/dev/shmem/screenstub.log"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <pthread.h>
#include <errno.h>
#include <unistd.h>
#include <time.h>
#include "frame_transport.h"
static FILE *stub_log_file;
static pthread_mutex_t stub_lock = PTHREAD_MUTEX_INITIALIZER;
static void stub_log(const char *fmt, ...) {
    va_list ap;
    pthread_mutex_lock(&stub_lock);
    if (!stub_log_file) {
        const char *p = getenv(STUB_LOG_ENV);
        stub_log_file = fopen(p ? p : STUB_LOG_DEFAULT, "a");
        if (stub_log_file) setvbuf(stub_log_file, NULL, _IOLBF, 0);
    }
    if (stub_log_file) { va_start(ap, fmt); vfprintf(stub_log_file, fmt, ap); va_end(ap); fputc('\n', stub_log_file); }
    pthread_mutex_unlock(&stub_lock);
}

enum { OBJ_CONTEXT = 1, OBJ_DISPLAY, OBJ_WINDOW, OBJ_PIXMAP, OBJ_BUFFER, OBJ_EVENT, OBJ_GROUP, OBJ_DEVICE };
#define NPROP 200
typedef struct obj {
    int type; int id;
    int iv[NPROP][4]; int iv_set[NPROP];
    void *pv[NPROP][4];
    char cv[NPROP][128];
    struct obj *buffers[8]; int nbuffers;
    void *pixels;
} obj;
static const char *typename_(int t) {
    static const char *n[] = {"?", "context", "display", "window", "pixmap", "buffer", "event", "group", "device"};
    return (t > 0 && t <= 8) ? n[t] : "?";
}
static int next_id = 1;
static obj *the_display;
static int screen_w = 800, screen_h = 480;
static obj *new_obj(int type) {
    obj *o = calloc(1, sizeof *o); o->type = type; o->id = next_id++;
    return o;
}
static obj *get_display(void) {
    if (!the_display) {
        const char *s = getenv("SCREEN_STUB_SIZE");
        if (s) sscanf(s, "%dx%d", &screen_w, &screen_h);
        the_display = new_obj(OBJ_DISPLAY);
    }
    return the_display;
}
static int vec_len(int pname) {
    switch (pname) {
    case 5: case 35: case 40: case 41: case 42: case 66: case 68: case 69: case 72: case 74: case 75: case 91: case 92: return 2;
    case 33: return 3;
    case 127: return 9;
    default: return 1;
    }
}
static int get_iv(obj *o, int pname, int *param) {
    int n = vec_len(pname), i;
    if (!o) { errno = EINVAL; return -1; }
    if (pname < 0 || pname >= NPROP) { *param = 0; errno = ENOTSUP; return -1; }
    if (o->iv_set[pname]) { for (i = 0; i < n; i++) param[i] = o->iv[pname][i]; return 0; }
    switch (pname) {
    case 40: case 42: case 5: case 66: case 75: case 92: param[0] = screen_w; param[1] = screen_h; return 0; /* SIZE family */
    case 35: case 41: case 68: case 74: case 91: param[0] = param[1] = 0; return 0;
    case 59: *param = 1; return 0;            /* DISPLAY_COUNT */
    case 87: *param = (o->type == OBJ_DISPLAY) ? 1 : o->id; return 0; /* ID */
    case 70: *param = 1; return 0;            /* FORMAT_COUNT */
    case 71: *param = 8; return 0;            /* FORMATS: SCREEN_FORMAT_RGBA8888 */
    case 14: *param = 8; return 0;            /* FORMAT */
    case 44: *param = screen_w * 4; return 0; /* STRIDE */
    case 4: *param = o->nbuffers ? o->nbuffers : 2; return 0; /* BUFFER_COUNT */
    case 53: *param = o->nbuffers ? o->nbuffers : 2; return 0;
    case 64: *param = 1; return 0;            /* ATTACHED */
    case 47: *param = 0; return 0;            /* TYPE */
    case 51: *param = 1; return 0;            /* VISIBLE */
    case 88: *param = 0; return 0;            /* POWER_MODE on */
    case 17: *param = 1; return 0;            /* PIPELINE */
    case 45: *param = 1; return 0;            /* SWAP_INTERVAL */
    case 89: *param = 1; return 0;            /* MODE_COUNT */
    case 69: param[0] = 154; param[1] = 86; return 0; /* PHYSICAL_SIZE mm */
    default: for (i = 0; i < n; i++) param[i] = 0; return 0;
    }
}
static int set_iv(obj *o, int pname, const int *param) {
    int n = vec_len(pname), i;
    if (!o || pname < 0 || pname >= NPROP) { errno = EINVAL; return -1; }
    for (i = 0; i < n; i++) o->iv[pname][i] = param[i];
    o->iv_set[pname] = 1;
    return 0;
}
static void ensure_buffers(obj *w, int count) {
    int i;
    if (count > 8) count = 8;
    for (i = w->nbuffers; i < count; i++) {
        obj *b = new_obj(OBJ_BUFFER);
        int sz[2] = {screen_w, screen_h};
        if (w->iv_set[5]) { sz[0] = w->iv[5][0]; sz[1] = w->iv[5][1]; }
        set_iv(b, 5, sz); set_iv(b, 40, sz);
        b->iv[44][0] = sz[0] * 4; b->iv_set[44] = 1;
        b->iv[14][0] = w->iv_set[14] ? w->iv[14][0] : 8; b->iv_set[14] = 1;
        b->pixels = calloc((size_t)sz[0] * sz[1], 4);
        w->buffers[i] = b;
    }
    w->nbuffers = count;
}
static int get_pv(obj *o, int pname, void **param) {
    int i;
    if (!o) { errno = EINVAL; return -1; }
    switch (pname) {
    case 60: param[0] = get_display(); return 0;           /* DISPLAYS */
    case 11: param[0] = get_display(); return 0;           /* DISPLAY */
    case 37: case 168: case 171:                           /* RENDER_BUFFERS / BUFFERS / FRONT_BUFFERS */
        if (o->type == OBJ_WINDOW || o->type == OBJ_PIXMAP) { if (!o->nbuffers) ensure_buffers(o, 2); for (i = 0; i < o->nbuffers; i++) param[i] = o->buffers[i]; }
        return 0;
    case 15: if (!o->nbuffers) ensure_buffers(o, 2); param[0] = o->buffers[0]; return 0; /* FRONT_BUFFER */
    case 34: param[0] = o->pixels; return 0;               /* POINTER */
    case 12: param[0] = o->pv[12][0]; return 0;            /* EGL_HANDLE */
    case 95: param[0] = o->pv[95][0]; return 0;            /* CONTEXT */
    default: param[0] = o->pv[pname < NPROP ? pname : 0][0]; return 0;
    }
}
#define LOG_CALL(o, pname) stub_log("%s %s#%d pname=%d", __func__, (o) ? typename_(((obj*)(o))->type) : "null", (o) ? ((obj*)(o))->id : 0, (int)(pname))

int screen_create_context(void **pctx, int flags) { obj *o = new_obj(OBJ_CONTEXT); stub_log("screen_create_context flags=%d -> context#%d", flags, o->id); *pctx = o; return 0; }
int screen_destroy_context(void *ctx) { LOG_CALL(ctx, 0); return 0; }
int screen_flush_context(void *ctx, int flags) { stub_log("screen_flush_context flags=%d", flags); return 0; }
int screen_flush_blits(void *ctx, int flags) { return 0; }
int screen_notify(void *ctx, int flags, const void *o, const void *p) { stub_log("screen_notify"); return 0; }
int screen_get_context_property_iv(void *ctx, int pname, int *param) { int r = get_iv(ctx, pname, param); stub_log("screen_get_context_property_iv pname=%d -> %d", pname, param[0]); return r; }
int screen_get_context_property_pv(void *ctx, int pname, void **param) { int r = get_pv(ctx, pname, param); stub_log("screen_get_context_property_pv pname=%d -> %p", pname, param[0]); return r; }
int screen_get_context_property_cv(void *ctx, int pname, int len, char *param) { LOG_CALL(ctx, pname); if (len > 0) param[0] = 0; return 0; }
int screen_set_context_property_iv(void *ctx, int pname, const int *param) { LOG_CALL(ctx, pname); return set_iv(ctx, pname, param); }
int screen_set_context_property_pv(void *ctx, int pname, void **param) { LOG_CALL(ctx, pname); if (pname < NPROP) ((obj*)ctx)->pv[pname][0] = param[0]; return 0; }
int screen_set_context_property_cv(void *ctx, int pname, int len, const char *param) { LOG_CALL(ctx, pname); return 0; }

int screen_get_display_property_iv(void *d, int pname, int *param) { int r = get_iv(d, pname, param); stub_log("screen_get_display_property_iv pname=%d -> %d %d", pname, param[0], vec_len(pname) > 1 ? param[1] : 0); return r; }
int screen_get_display_property_pv(void *d, int pname, void **param) { int r = get_pv(d, pname, param); LOG_CALL(d, pname); return r; }
int screen_get_display_property_cv(void *d, int pname, int len, char *param) { LOG_CALL(d, pname); if (len > 0) snprintf(param, len, "%s", pname == 20 ? "stubdisplay" : ""); return 0; }
int screen_set_display_property_iv(void *d, int pname, const int *param) { LOG_CALL(d, pname); return set_iv(d, pname, param); }
int screen_set_display_property_pv(void *d, int pname, void **param) { LOG_CALL(d, pname); return 0; }
int screen_set_display_property_cv(void *d, int pname, int len, const char *param) { LOG_CALL(d, pname); return 0; }
int screen_get_display_modes(void *d, int max, void *modes) { stub_log("screen_get_display_modes max=%d", max); if (max > 0) { int *m = modes; m[0] = screen_w; m[1] = screen_h; m[2] = 60; m[3] = 0; m[4] = 0; m[5] = 0; m[6] = 0; m[7] = 0; } return 0; }
int screen_read_display(void *d, void *buf, int count, const int *rects, int flags) { stub_log("screen_read_display count=%d", count); return 0; }
int screen_wait_vsync(void *d) { return 0; }

int screen_create_window(void **pwin, void *ctx) { obj *o = new_obj(OBJ_WINDOW); o->pv[95][0] = ctx; stub_log("screen_create_window -> window#%d", o->id); *pwin = o; return 0; }
int screen_create_window_type(void **pwin, void *ctx, int type) { obj *o = new_obj(OBJ_WINDOW); o->pv[95][0] = ctx; o->iv[47][0] = type; o->iv_set[47] = 1; stub_log("screen_create_window_type type=%d -> window#%d", type, o->id); *pwin = o; return 0; }
int screen_destroy_window(void *w) { LOG_CALL(w, 0); return 0; }
int screen_create_window_buffers(void *w, int count) { stub_log("screen_create_window_buffers window#%d count=%d", ((obj*)w)->id, count); ensure_buffers(w, count); return 0; }
int screen_attach_window_buffers(void *w, int count, void **bufs) { stub_log("screen_attach_window_buffers count=%d", count); return 0; }
int screen_destroy_window_buffers(void *w) { LOG_CALL(w, 0); return 0; }
int screen_get_window_property_iv(void *w, int pname, int *param) { int r = get_iv(w, pname, param); stub_log("screen_get_window_property_iv window#%d pname=%d -> %d", ((obj*)w)->id, pname, param[0]); return r; }
int screen_get_window_property_pv(void *w, int pname, void **param) { int r = get_pv(w, pname, param); LOG_CALL(w, pname); return r; }
int screen_get_window_property_cv(void *w, int pname, int len, char *param) { LOG_CALL(w, pname); if (len > 0) snprintf(param, len, "%s", pname < NPROP ? ((obj*)w)->cv[pname] : ""); return 0; }
int screen_set_window_property_iv(void *w, int pname, const int *param) { stub_log("screen_set_window_property_iv window#%d pname=%d = %d %d", ((obj*)w)->id, pname, param[0], vec_len(pname) > 1 ? param[1] : 0); return set_iv(w, pname, param); }
int screen_set_window_property_pv(void *w, int pname, void **param) { stub_log("screen_set_window_property_pv window#%d pname=%d = %p", ((obj*)w)->id, pname, param[0]); if (pname < NPROP) ((obj*)w)->pv[pname][0] = param[0]; return 0; }
int screen_set_window_property_cv(void *w, int pname, int len, const char *param) { stub_log("screen_set_window_property_cv window#%d pname=%d = %.*s", ((obj*)w)->id, pname, len, param); if (pname < NPROP) snprintf(((obj*)w)->cv[pname], 128, "%.*s", len, param); return 0; }
int screen_join_window_group(void *w, const char *name) { stub_log("screen_join_window_group window#%d group=%s", ((obj*)w)->id, name); return 0; }
int screen_leave_window_group(void *w) { LOG_CALL(w, 0); return 0; }
int screen_create_window_group(void *w, const char *name) { stub_log("screen_create_window_group %s", name); return 0; }
int screen_post_window(void *w, void *buf, int count, const int *dirty, int flags) {
    obj *b = buf;
    stub_log("screen_post_window window#%d count=%d", ((obj*)w)->id, count);
    if (getenv("MIB_FRAME_HOST")) {
        if (!b || b->type != OBJ_BUFFER) { errno = EINVAL; return -1; }
        return frame_publish(b->pixels, b->iv[5][0], b->iv[5][1], b->iv[44][0], b->iv[14][0]);
    }
    return 0;
}
int screen_read_window(void *w, void *buf, int count, const int *rects, int flags) { LOG_CALL(w, 0); return 0; }
int screen_share_window_buffers(void *w, void *share) { stub_log("screen_share_window_buffers"); if (((obj*)share)->nbuffers) { obj *a = w, *b = share; int i; a->nbuffers = b->nbuffers; for (i = 0; i < a->nbuffers; i++) a->buffers[i] = b->buffers[i]; } return 0; }
int screen_share_display_buffers(void *w, void *d, int count) { stub_log("screen_share_display_buffers"); ensure_buffers(w, count); return 0; }
int screen_discard_window_regions(void *w, int count, const int *rects) { return 0; }
int screen_ref_window(void *w) { return 0; }
int screen_unref_window(void *w) { return 0; }
int screen_wait_post(void *w, int flags) { return 0; }
int screen_manage_window(void *w, const char *data) { return 0; }

int screen_create_pixmap(void **pp, void *ctx) { obj *o = new_obj(OBJ_PIXMAP); o->pv[95][0] = ctx; stub_log("screen_create_pixmap -> pixmap#%d", o->id); *pp = o; return 0; }
int screen_destroy_pixmap(void *p) { LOG_CALL(p, 0); return 0; }
int screen_create_pixmap_buffer(void *p) { stub_log("screen_create_pixmap_buffer pixmap#%d", ((obj*)p)->id); ensure_buffers(p, 1); return 0; }
int screen_attach_pixmap_buffer(void *p, void *buf) { return 0; }
int screen_destroy_pixmap_buffer(void *p) { return 0; }
int screen_get_pixmap_property_iv(void *p, int pname, int *param) { int r = get_iv(p, pname, param); LOG_CALL(p, pname); return r; }
int screen_get_pixmap_property_pv(void *p, int pname, void **param) { int r = get_pv(p, pname, param); LOG_CALL(p, pname); return r; }
int screen_get_pixmap_property_cv(void *p, int pname, int len, char *param) { LOG_CALL(p, pname); if (len > 0) param[0] = 0; return 0; }
int screen_set_pixmap_property_iv(void *p, int pname, const int *param) { stub_log("screen_set_pixmap_property_iv pixmap#%d pname=%d = %d %d", ((obj*)p)->id, pname, param[0], vec_len(pname) > 1 ? param[1] : 0); return set_iv(p, pname, param); }
int screen_set_pixmap_property_pv(void *p, int pname, void **param) { LOG_CALL(p, pname); return 0; }
int screen_set_pixmap_property_cv(void *p, int pname, int len, const char *param) { LOG_CALL(p, pname); return 0; }

int screen_create_buffer(void **pb) { obj *o = new_obj(OBJ_BUFFER); *pb = o; stub_log("screen_create_buffer -> buffer#%d", o->id); return 0; }
int screen_destroy_buffer(void *b) { LOG_CALL(b, 0); return 0; }
int screen_get_buffer_property_iv(void *b, int pname, int *param) { int r = get_iv(b, pname, param); LOG_CALL(b, pname); return r; }
int screen_get_buffer_property_pv(void *b, int pname, void **param) { int r = get_pv(b, pname, param); LOG_CALL(b, pname); return r; }
int screen_get_buffer_property_cv(void *b, int pname, int len, char *param) { LOG_CALL(b, pname); if (len > 0) param[0] = 0; return 0; }
int screen_set_buffer_property_iv(void *b, int pname, const int *param) { LOG_CALL(b, pname); return set_iv(b, pname, param); }
int screen_set_buffer_property_pv(void *b, int pname, void **param) { LOG_CALL(b, pname); if (pname == 34) ((obj*)b)->pixels = param[0]; return 0; }
int screen_set_buffer_property_cv(void *b, int pname, int len, const char *param) { LOG_CALL(b, pname); return 0; }
int screen_blit(void *ctx, void *dst, void *src, const int *attribs) { stub_log("screen_blit"); return 0; }
int screen_fill(void *ctx, void *dst, const int *attribs) { stub_log("screen_fill"); return 0; }

int screen_create_event(void **pe) { obj *o = new_obj(OBJ_EVENT); *pe = o; return 0; }
int screen_destroy_event(void *e) { return 0; }
int screen_get_event(void *ctx, void *e, long long timeout) { stub_log("screen_get_event timeout=%lld", timeout); if (timeout > 0) { struct timespec ts = {(int)(timeout / 1000000000LL), (long)(timeout % 1000000000LL)}; nanosleep(&ts, NULL); } else if (timeout < 0) { sleep(3600); } ((obj*)e)->iv[47][0] = 0; ((obj*)e)->iv_set[47] = 1; return 0; }
int screen_send_event(void *ctx, void *e, int pid) { return 0; }
int screen_inject_event(void *d, void *e) { return 0; }
int screen_get_event_property_iv(void *e, int pname, int *param) { return get_iv(e, pname, param); }
int screen_get_event_property_pv(void *e, int pname, void **param) { param[0] = 0; return 0; }
int screen_get_event_property_cv(void *e, int pname, int len, char *param) { if (len > 0) param[0] = 0; return 0; }
int screen_set_event_property_iv(void *e, int pname, const int *param) { return set_iv(e, pname, param); }
int screen_set_event_property_pv(void *e, int pname, void **param) { return 0; }
int screen_set_event_property_cv(void *e, int pname, int len, const char *param) { return 0; }

int screen_create_group(void **pg, void *ctx) { obj *o = new_obj(OBJ_GROUP); *pg = o; return 0; }
int screen_destroy_group(void *g) { return 0; }
int screen_get_group_property_iv(void *g, int pname, int *param) { return get_iv(g, pname, param); }
int screen_get_group_property_pv(void *g, int pname, void **param) { param[0] = 0; return 0; }
int screen_get_group_property_cv(void *g, int pname, int len, char *param) { if (len > 0) param[0] = 0; return 0; }
int screen_set_group_property_iv(void *g, int pname, const int *param) { return set_iv(g, pname, param); }
int screen_set_group_property_pv(void *g, int pname, void **param) { return 0; }
int screen_set_group_property_cv(void *g, int pname, int len, const char *param) { return 0; }
int screen_create_device_type(void **pd, void *ctx, int type) { obj *o = new_obj(OBJ_DEVICE); *pd = o; return 0; }
int screen_destroy_device(void *d) { return 0; }
int screen_get_device_property_iv(void *d, int pname, int *param) { return get_iv(d, pname, param); }
int screen_get_device_property_pv(void *d, int pname, void **param) { param[0] = 0; return 0; }
int screen_get_device_property_cv(void *d, int pname, int len, char *param) { if (len > 0) param[0] = 0; return 0; }
int screen_set_device_property_iv(void *d, int pname, const int *param) { return set_iv(d, pname, param); }
int screen_set_device_property_pv(void *d, int pname, void **param) { return 0; }
int screen_set_device_property_cv(void *d, int pname, int len, const char *param) { return 0; }
int screen_get_debug_stats(void *ctx, int *stats) { return 0; }
int screen_print_debug_info(void *ctx) { return 0; }
int screen_request_events(void *ctx) { stub_log("screen_request_events"); return 0; }
int screen_stop_events(void *ctx) { return 0; }
int screen_ref_context(void *ctx) { return 0; }
int screen_unref_context(void *ctx) { return 0; }
int screen_flush_get_event(void *ctx, void *e, long long timeout) { return screen_get_event(ctx, e, timeout); }
