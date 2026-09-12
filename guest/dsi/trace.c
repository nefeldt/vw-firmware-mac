/* Emulator-only DSI transport tracing. All calls are forwarded unchanged. */
#include <jni.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdint.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

#define TX "_ZN3tsd13communication14HMITransceiver4sendEP7JNIEnv_P11_jbyteArrayi"
#define RX "_ZN3tsd13communication17DSIReceiverThread15messageReceivedEPKvj"
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static void record(const char *direction, const unsigned char *data, unsigned length) {
    pthread_mutex_lock(&lock);
    FILE *f = fopen("/dev/shmem/dsi-packets.log", "a");
    if (f) {
        unsigned i, count = length < 96 ? length : 96;
        fprintf(f, "%s len=%u hex=", direction, length);
        for (i = 0; i < count; i++) fprintf(f, "%02x", data[i]);
        fputc('\n', f);
        fclose(f);
    }
    pthread_mutex_unlock(&lock);
}
void trace_tx(void *self, JNIEnv *env, jbyteArray bytes, jint size) __asm__(TX);
void trace_tx(void *self, JNIEnv *env, jbyteArray bytes, jint size) {
    typedef void (*Fn)(void *, JNIEnv *, jbyteArray, jint);
    Fn original = (Fn)dlsym(RTLD_NEXT, TX);
    if (bytes && size > 0 && size <= (*env)->GetArrayLength(env, bytes)) {
        unsigned char data[96];
        (*env)->GetByteArrayRegion(env, bytes, 0, size < 96 ? size : 96, (jbyte *)data);
        if (!(*env)->ExceptionCheck(env)) record("TX", data, (unsigned)size);
    }
    if (original) original(self, env, bytes, size);
    else record("TX_FORWARD_MISSING", (const unsigned char *)"", 0);
}
void trace_rx(void *self, const void *data, unsigned size) __asm__(RX);
void trace_rx(void *self, const void *data, unsigned size) {
    typedef void (*Fn)(void *, const void *, unsigned);
    Fn original = (Fn)dlsym(RTLD_NEXT, RX);
    if (data) record("RX", data, size);
    if (original) original(self, data, size);
    else record("RX_FORWARD_MISSING", (const unsigned char *)"", 0);
}
__attribute__((constructor)) static void loaded(void) {
    record("TRACE_LOADED", (const unsigned char *)"", 0);
}

static unsigned u32(const unsigned char *p) {
    return (unsigned)p[0] | (unsigned)p[1]<<8 | (unsigned)p[2]<<16 | (unsigned)p[3]<<24;
}
static void put32(unsigned char *p, unsigned value) {
    p[0]=value; p[1]=value>>8; p[2]=value>>16; p[3]=value>>24;
}
static jclass input_bm,input_bb,input_dc;
/* Feed a normal pooled receive buffer into the original asynchronous dispatcher. */
static int deliver(JNIEnv *e, const unsigned char *data, unsigned size) {
    jclass bm, bb, dc;
    jmethodID get, array, instance, receive;
    jobject buffer, dispatcher;
    jbyteArray bytes;
    if ((*e)->PushLocalFrame(e, 16) < 0) return 0;
    bm=input_bm ? input_bm : (*e)->FindClass(e,"tsd/mibstd2/hmi/dsi/communication/DSIBufferManager");
    bb=input_bb ? input_bb : (*e)->FindClass(e,"java/nio/ByteBuffer");
    dc=input_dc ? input_dc : (*e)->FindClass(e,"tsd/mibstd2/hmi/dsi/communication/DSIRXDispatcherThread");
    if (!bm || !bb || !dc) goto fail;
    get=(*e)->GetStaticMethodID(e,bm,"getBufferRx","(I)Ljava/nio/ByteBuffer;");
    array=(*e)->GetMethodID(e,bb,"array","()[B");
    instance=(*e)->GetStaticMethodID(e,dc,"getInstance","()Ltsd/mibstd2/hmi/dsi/communication/DSIRXDispatcherThread;");
    receive=(*e)->GetMethodID(e,dc,"receiveFromApp","(Ljava/nio/ByteBuffer;)V");
    if (!get || !array || !instance || !receive) goto fail;
    dispatcher=(*e)->CallStaticObjectMethod(e,dc,instance);
    if (!dispatcher || (*e)->ExceptionCheck(e)) goto fail;
    buffer=(*e)->CallStaticObjectMethod(e,bm,get,(jint)size);
    if (!buffer || (*e)->ExceptionCheck(e)) goto fail;
    bytes=(*e)->CallObjectMethod(e,buffer,array);
    if (!bytes || (*e)->ExceptionCheck(e)) goto fail;
    (*e)->SetByteArrayRegion(e,bytes,0,(jint)size,(jbyte *)data);
    if ((*e)->ExceptionCheck(e)) goto fail;
    (*e)->CallVoidMethod(e,dispatcher,receive,buffer);
    if ((*e)->ExceptionCheck(e)) goto fail;
    record("EMPTY_STORE_RX",data,size);
    (*e)->PopLocalFrame(e,0);
    return 1;
fail:
    record("EMPTY_STORE_DELIVERY_FAILED",(const unsigned char *)"",0);
    (*e)->PopLocalFrame(e,0);
    return 0;
}
static int empty_store(JNIEnv *e, const unsigned char *p, unsigned size) {
    unsigned event, response, length=0;
    unsigned char out[40]={0};
    const char *enabled=getenv("MIB_DSI_EMPTY_STORE");
    if (!enabled || strcmp(enabled,"1") || size<12 || u32(p)!=0x0203b000 || u32(p+4)!=0x57f18c24) return 0;
    event=u32(p+8);
    put32(out,0x0203b800); put32(out+4,0x57f18c24);
    /* Empty virtual flash medium, valid notification. No physical flash access. */
    if ((event==0 && size==21 && p[12]==1 && u32(p+13)==1 && u32(p+17)==1) ||
        (event==3839 && size>=16 && u32(p+12)==1) || event==1016) {
        put32(out+8,1); put32(out+12,1); put32(out+16,1); length=20;
    } else {
        response=event;
        if (event>=1019 && event<=1023) response=1001+(event-1019)*2;
        if (response>=1000 && response<=1009 && size>=24) {
            put32(out+8,response+1000); memcpy(out+12,p+12,12);
            if (!(response&1)) { /* Writes are explicitly unavailable. */
                put32(out+24,6); length=28;
            } else if (response==1001) {
                put32(out+24,0); put32(out+28,2); length=32;
            } else { /* Null value followed by ERRORCODE_INVALID_KEY. */
                out[24]=0; put32(out+25,2); length=29;
            }
        }
    }
    return length ? deliver(e,out,length) : 0;
}
/* Simulator power state: original DSIPowerManagement constants and wire ABI. */
static int power_on(JNIEnv *e, const unsigned char *p, unsigned size) {
    const char *enabled=getenv("MIB_DSI_POWER_ON");
    unsigned event,count=0,offset=0,i,handled=0;
    if(!enabled || strcmp(enabled,"1") || size<16 || u32(p)!=0x02040000 || u32(p+4)!=0xa63ff7f4) return 0;
    event=u32(p+8);
    if(event==0 && size>=17 && p[12]==1) { count=u32(p+13); offset=17; }
    else if(event==3839) { count=1; offset=12; }
    if(count>16 || offset+count*4>size) return 0;
    for(i=0;i<count;i++) {
        unsigned attr=u32(p+offset+4*i),length=20;
        unsigned char out[24]={0};
        put32(out,0x02040800);put32(out+4,0xa63ff7f4);put32(out+8,attr);
        if(attr==1 || attr==2) {
            put32(out+12,1); /* POWERSTATE_ON */
            put32(out+16,7); /* POWEREVENT_OTHER */
            put32(out+20,1);length=24;
        } else if(attr==3 || attr==5 || attr==6 || attr==9) {
            put32(out+12,attr==6?1:attr==9?2:0);
            put32(out+16,1);
        } else if(attr==7 || attr==8 || attr==11) {
            out[12]=0;put32(out+13,1);length=17;
        } else continue;
        if(deliver(e,out,length)) handled++;
    }
    return handled!=0;
}

#include "input.h"

/* JNI resolves this entry point in the proxy library. Its other JNI exports
 * remain available through the original library's DT_NEEDED dependency. */
JNIEXPORT void JNICALL Java_tsd_mibstd2_hmi_dsi_communication_DSITransceiverThread__1send(
        JNIEnv *env, jobject object, jbyteArray bytes, jint size) {
    typedef void (*Fn)(JNIEnv *, jobject, jbyteArray, jint);
    void *handle = dlopen("/seat/shim/libdsi-original.so", RTLD_NOW);
    Fn original = handle ? (Fn)dlsym(handle,
        "Java_tsd_mibstd2_hmi_dsi_communication_DSITransceiverThread__1send") : 0;
    if (bytes && size > 0 && size <= (*env)->GetArrayLength(env, bytes)) {
        unsigned char data[96];
        (*env)->GetByteArrayRegion(env, bytes, 0, size < 96 ? size : 96, (jbyte *)data);
        if (!(*env)->ExceptionCheck(env)) {
            record("JNI_TX", data, (unsigned)size);
            if (size >= 12 && u32(data) == 0x0201d000) start_input(env);
            if (size<=96 && (power_on(env,data,(unsigned)size) || empty_store(env,data,(unsigned)size))) {
                if (handle) dlclose(handle);
                return;
            }
        }
    }
    if (original) original(env, object, bytes, size);
    else {
        jclass error = (*env)->FindClass(env, "java/lang/UnsatisfiedLinkError");
        if (error) (*env)->ThrowNew(env, error, "DSI proxy cannot resolve original send");
    }
    if (handle) dlclose(handle);
}
