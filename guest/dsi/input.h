/* Emulator input thread. Only validated DSIKeyPanel notifications from loopback host. */
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
static JavaVM *input_vm;
static int input_started;
static int input_exact(int fd,void *data,unsigned count) {
    unsigned char *p=data;
    while(count) {int n=recv(fd,p,count,0);if(n<=0)return 0;p+=n;count-=n;}return 1;
}
static void *input_main(void *unused) {
    JNIEnv *env=0;
    if((*input_vm)->AttachCurrentThreadAsDaemon(input_vm,(void **)&env,0)!=JNI_OK)return 0;
    for(;;) {
        int fd=socket(AF_INET,SOCK_STREAM,0);struct sockaddr_in addr;unsigned char header[4],packet[256];
        memset(&addr,0,sizeof(addr));addr.sin_family=AF_INET;addr.sin_port=htons(8769);addr.sin_addr.s_addr=inet_addr("10.0.2.2");
        if(fd<0||connect(fd,(struct sockaddr *)&addr,sizeof(addr))<0) {if(fd>=0)close(fd);sleep(1);continue;}
        record("INPUT_CONNECTED",(unsigned char *)"",0);
        while(input_exact(fd,header,4)) {
            unsigned size=u32(header);
            if(size<12||size>sizeof(packet)||!input_exact(fd,packet,size))break;
            if(u32(packet)==0x0201d800 && u32(packet+4)==0xa63ff832 && (u32(packet+8)==20||u32(packet+8)==23||u32(packet+8)==25)) {
                deliver(env,packet,size);record("INPUT_RX",packet,size);
            }
        }
        close(fd);sleep(1);
    }
    return 0;
}
static void start_input(JNIEnv *env) {
    pthread_t thread;const char *enabled=getenv("MIB_INPUT");
    if(input_started||!enabled||strcmp(enabled,"1"))return;
    if((*env)->GetJavaVM(env,&input_vm)!=JNI_OK)return;
    input_bm=(*env)->NewGlobalRef(env,(*env)->FindClass(env,"tsd/mibstd2/hmi/dsi/communication/DSIBufferManager"));
    input_bb=(*env)->NewGlobalRef(env,(*env)->FindClass(env,"java/nio/ByteBuffer"));
    input_dc=(*env)->NewGlobalRef(env,(*env)->FindClass(env,"tsd/mibstd2/hmi/dsi/communication/DSIRXDispatcherThread"));
    if((*env)->ExceptionCheck(env)||!input_bm||!input_bb||!input_dc) {(*env)->ExceptionClear(env);return;}
    input_started=1;
    if(!pthread_create(&thread,0,input_main,0))pthread_detach(thread);else input_started=0;
}
