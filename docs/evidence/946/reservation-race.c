#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static int cleanup, scan, fired;
static int target_fd(int fd, char *path) {
    char link[64];
    snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
    ssize_t n = readlink(link, path, PATH_MAX-1);
    if (n < 0) return 0;
    path[n] = 0;
    return strstr(path, "/web_aw5_send-state/attachments/att-") != NULL;
}
int unlinkat(int fd, const char *name, int flags) {
    int (*real_unlinkat)(int,const char*,int) = dlsym(RTLD_NEXT,"unlinkat");
    char path[PATH_MAX];
    if (target_fd(fd,path) && flags == 0) {
        pthread_mutex_lock(&lock);
        if (!fired) {
            cleanup = 1;
            fputs("probe: holding aborted-upload cleanup before reservation removal\n",stderr);
            struct timespec until;
            clock_gettime(CLOCK_REALTIME,&until); until.tv_sec += 3;
            while (!scan && pthread_cond_timedwait(&changed,&lock,&until) == 0) {}
            fired = 1;
        }
        pthread_mutex_unlock(&lock);
    }
    return real_unlinkat(fd,name,flags);
}
ssize_t read(int fd, void *buf, size_t size) {
    ssize_t (*real_read)(int,void*,size_t) = dlsym(RTLD_NEXT,"read");
    char path[PATH_MAX];
    if (target_fd(fd,path) && strstr(path,"/.reserve")) {
        pthread_mutex_lock(&lock);
        if (cleanup && !scan) {
            scan = 1;
            pthread_cond_broadcast(&changed);
            pthread_mutex_unlock(&lock);
            char *slash = strrchr(path,'/'); *slash = 0;
            struct timespec delay = {0,1000000};
            struct timespec start, now; clock_gettime(CLOCK_MONOTONIC,&start);
            while (access(path,F_OK) == 0) {
                nanosleep(&delay,NULL); clock_gettime(CLOCK_MONOTONIC,&now);
                if (now.tv_sec-start.tv_sec >= 5) { fputs("probe: cleanup never completed\n",stderr); _exit(90); }
            }
            fputs("probe: aborted reservation removed between scan read and directory listing\n",stderr);
            return real_read(fd,buf,size);
        }
        pthread_mutex_unlock(&lock);
    }
    return real_read(fd,buf,size);
}
