/* Coalesce small RPC requests without changing the existing wire protocol. */
static int send_request(uint32_t *header, unsigned count, RpcArg *args) {
    unsigned char batch[4096];
    unsigned used=8, i;
    memcpy(batch,header,8);
    for(i=0;i<count;i++) {
        uint32_t h[2]={args[i].mode,args[i].data?args[i].size:0};
        unsigned payload=h[0]==2?0:h[1];
        if(h[1]>67108864) return 0;
        if(payload>sizeof(batch)-8 || used>sizeof(batch)-8-payload) break;
        memcpy(batch+used,h,8);used+=8;
        if(payload) {memcpy(batch+used,args[i].data,payload);used+=payload;}
    }
    if(i==count) return transfer(batch,used,1);
    /* Texture uploads remain streaming, with no extra large allocation. */
    if(!transfer(header,8,1)) return 0;
    for(i=0;i<count;i++) {
        uint32_t h[2]={args[i].mode,args[i].data?args[i].size:0};
        if(h[1]>67108864 || !transfer(h,8,1)) return 0;
        if(h[0]!=2 && h[1] && !transfer(args[i].data,h[1],1)) return 0;
    }
    return 1;
}
