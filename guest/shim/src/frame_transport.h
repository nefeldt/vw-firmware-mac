/* Diagnostic software framebuffer transport: network-order header, RGBA bytes. */
#include <sys/socket.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdint.h>
static int frame_send_all(int fd, const void *data, size_t size) {
    const char *p = data;
    while (size) { int n = send(fd, p, size, 0); if (n <= 0) return -1; p += n; size -= n; }
    return 0;
}
static int frame_publish(const void *pixels, unsigned w, unsigned h, unsigned stride, unsigned format) {
    const char *host = getenv("MIB_FRAME_HOST");
    struct sockaddr_in addr; struct timeval timeout = {2, 0};
    uint32_t header[5]; int fd, result;
    if (!host || !pixels || !w || !h || w > 1920 || h > 1080 || stride != w * 4 || format != 8) return -1;
    fd = socket(AF_INET, SOCK_STREAM, 0); if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
    memset(&addr, 0, sizeof addr); addr.sin_family = AF_INET; addr.sin_port = htons(8766);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1 || connect(fd, (struct sockaddr *)&addr, sizeof addr) < 0) { close(fd); return -1; }
    header[0] = htonl(0x4d494246); header[1] = htonl(w); header[2] = htonl(h);
    header[3] = htonl(stride); header[4] = htonl(format);
    result = frame_send_all(fd, header, sizeof header);
    if (!result) result = frame_send_all(fd, pixels, stride * h);
    close(fd); return result;
}
