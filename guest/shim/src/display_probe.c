/* Runs inside QNX. This is a transport test, not the MIB HMI. */
#include <stdio.h>
#include <unistd.h>
extern int screen_create_context(void **, int);
extern int screen_create_window(void **, void *);
extern int screen_set_window_property_iv(void *, int, const int *);
extern int screen_create_window_buffers(void *, int);
extern int screen_get_window_property_pv(void *, int, void **);
extern int screen_get_buffer_property_pv(void *, int, void **);
extern int screen_post_window(void *, void *, int, const int *, int);
int main(int argc, char **argv) {
    void *ctx, *win, *buf, *pixels; int size[2]={800,480}, fmt=8, x,y,t;
    const unsigned char colors[8][3]={{235,235,235},{235,210,30},{30,210,210},{30,210,50},{210,40,210},{220,40,40},{40,60,220},{20,20,20}};
    if(screen_create_context(&ctx,0)||screen_create_window(&win,ctx)) return 1;
    screen_set_window_property_iv(win,5,size); screen_set_window_property_iv(win,14,&fmt);
    screen_create_window_buffers(win,1); screen_get_window_property_pv(win,37,&buf);
    screen_get_buffer_property_pv(buf,34,&pixels);
    if (argc == 2) {
        FILE *input = fopen(argv[1], "rb");
        if (!input) { perror(argv[1]); return 3; }
        if (fread(pixels, 1, 800*480*4, input) != 800*480*4 || fgetc(input) != EOF) {
            fprintf(stderr, "Expected exactly 800x480 RGBA pixels\n"); fclose(input); return 4;
        }
        fclose(input);
    }
    for(t=0;t<120;t++) {
        unsigned char *p=pixels;
        if (argc != 2) for(y=0;y<480;y++) for(x=0;x<800;x++,p+=4) {
            int k=x/100; p[0]=colors[k][0]; p[1]=colors[k][1]; p[2]=colors[k][2]; p[3]=255;
            if(y>350) p[0]=p[1]=p[2]=(x*255/799);
            if(y>425 && x>=t*6%780 && x<t*6%780+20) p[0]=255,p[1]=32,p[2]=32;
        }
        if(screen_post_window(win,buf,0,0,0)) {perror("screen_post_window");return 2;}
        printf("QNX framebuffer posted: %d 800x480 RGBA\n",t);fflush(stdout);sleep(1);
    }
    return 0;
}
