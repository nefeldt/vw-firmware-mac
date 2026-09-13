/* Emulator diagnostics only: preserve DMA results, log the failed hardware path. */
#include <hw/dma.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static dma_functions_t original;
static void *attach(const char *options, const struct sigevent *event,
                    unsigned *channel, int priority, dma_attach_flags flags) {
    void *handle = original.channel_attach(options, event, channel, priority, flags);
    int error = errno;
    fprintf(stderr, "MIB_DMA attach options=%s flags=%u handle=%p errno=%d\n",
            options ? options : "", (unsigned)flags, handle, error);
    errno = error;
    return handle;
}
static int setup(void *handle, const dma_transfer_t *transfer) {
    fprintf(stderr, "MIB_DMA setup handle=%p bytes=%u unit=%u src_flags=%u dst_flags=%u\n",
            handle, transfer ? transfer->xfer_bytes : 0,
            transfer ? transfer->xfer_unit_size : 0,
            transfer ? transfer->src_flags : 0, transfer ? transfer->dst_flags : 0);
    /* A failed attachment must remain a failure, never a fake successful DMA. */
    if (!handle || !transfer) { errno = EINVAL; return -1; }
    return original.setup_xfer(handle, transfer);
}
int get_dmafuncs(dma_functions_t *table, int size) {
    get_dmafuncs_t next = (get_dmafuncs_t)dlsym(RTLD_NEXT, "get_dmafuncs");
    if (!next) { fprintf(stderr, "MIB_DMA original get_dmafuncs missing\n"); errno = ENOSYS; return -1; }
    int result = next(table, size);
    fprintf(stderr, "MIB_DMA get_dmafuncs size=%d result=%d\n", size, result);
    if (result == 0 && size >= (int)sizeof(original)) {
        memcpy(&original, table, sizeof(original));
        table->channel_attach = attach;
        table->setup_xfer = setup;
    }
    return result;
}
