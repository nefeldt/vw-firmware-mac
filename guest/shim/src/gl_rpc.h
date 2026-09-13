/* Local QEMU -> Mac graphics RPC. Protocol integers are little endian. */
#include <stdint.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <errno.h>
typedef struct { void *data; uint32_t size, mode; } RpcArg;
static int rpc_fd=-1;
static pthread_mutex_t rpc_lock=PTHREAD_MUTEX_INITIALIZER;
static GLenum rpc_error;
static int transfer(void *data, unsigned size, int sending) {
    unsigned done=0;
    while(done<size) {
        int n=sending ? send(rpc_fd,(char *)data+done,size-done,0) : recv(rpc_fd,(char *)data+done,size-done,0);
        if(n<0 && errno==EINTR) continue;
        if(n<=0) return 0;
        done+=n;
    }
    return 1;
}
#include "gl_rpc_request.h"
static uint32_t rpc(unsigned op, unsigned count, RpcArg *args, void *extra, unsigned capacity) {
    uint32_t header[2]={op,count}, reply[2], result=0;
    unsigned i;
    pthread_mutex_lock(&rpc_lock);
    if(rpc_fd<0) {
        const char *host=getenv("MIB_GL_HOST");
        struct sockaddr_in addr;
        struct timeval timeout={20,0};
        int nodelay=1;
        if(!host) goto fail;
        memset(&addr,0,sizeof(addr)); addr.sin_family=AF_INET; addr.sin_port=htons(8768);
        if(inet_pton(AF_INET,host,&addr.sin_addr)!=1) goto fail;
        rpc_fd=socket(AF_INET,SOCK_STREAM,0);
        if(rpc_fd<0) goto fail;
        setsockopt(rpc_fd,IPPROTO_TCP,TCP_NODELAY,&nodelay,sizeof(nodelay));
        setsockopt(rpc_fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
        setsockopt(rpc_fd,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
        if(connect(rpc_fd,(struct sockaddr *)&addr,sizeof(addr))) goto fail;
    }
    if(!send_request(header,count,args)) goto fail;
    if(!transfer(reply,8,0)) goto fail;
    result=reply[0];
    if(reply[1]>capacity) goto fail;
    if(reply[1] && !transfer(extra,reply[1],0)) goto fail;
    for(i=0;i<count;i++) if(args[i].mode==2) {
        uint32_t length;
        if(!transfer(&length,4,0) || length>args[i].size) goto fail;
        if(length && !transfer(args[i].data,length,0)) goto fail;
    }
    pthread_mutex_unlock(&rpc_lock);
    return result;
fail:
    if(rpc_fd>=0) close(rpc_fd);
    rpc_fd=-1; rpc_error=GL_INVALID_OPERATION;
    stub_log("GL bridge failure op=%u errno=%d",op,errno);
    pthread_mutex_unlock(&rpc_lock);
    return 0;
}
void mib_gl_swap(void) { rpc(0,0,0,0,0); }
static unsigned pixel_bytes(int w,int h,unsigned format,unsigned type) {
    unsigned channels=format==GL_RGBA?4:format==GL_RGB?3:format==GL_LUMINANCE_ALPHA?2:1;
    unsigned bytes=type==GL_UNSIGNED_BYTE?channels:2;
    if(w<0 || h<0 || w>8192 || h>8192) return 0;
    return (unsigned)w*(unsigned)h*bytes;
}
