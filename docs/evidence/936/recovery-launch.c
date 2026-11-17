#define _GNU_SOURCE
#include <dlfcn.h>
#include <spawn.h>
#include <stdio.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
static atomic_int launches;
int posix_spawnp(pid_t *pid, const char *path, const posix_spawn_file_actions_t *actions,
                const posix_spawnattr_t *attr, char *const argv[], char *const env[]) {
    int (*original)(pid_t*,const char*,const posix_spawn_file_actions_t*,const posix_spawnattr_t*,char *const[],char *const[]) = dlsym(RTLD_NEXT,"posix_spawnp");
    if (strstr(path,"/ep1-deadline/gated-gh") && atomic_fetch_add(&launches,1) == 3) {
        fputs("probe: fourth plan launch descheduled for 2.2 seconds\n",stderr);
        struct timespec delay = {2,200000000};
        nanosleep(&delay,NULL);
    }
    return original(pid,path,actions,attr,argv,env);
}
