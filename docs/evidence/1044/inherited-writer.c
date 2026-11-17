#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
static pid_t owner, retained=-1;
__attribute__((constructor)) static void start(void){
 const char *root=getenv("OW_UPDATE_ROOT_PID");
 if(root)owner=(pid_t)atol(root);
 else {char pid[32];owner=getpid();snprintf(pid,sizeof pid,"%ld",(long)owner);setenv("OW_UPDATE_ROOT_PID",pid,1);}
}
__attribute__((destructor)) static void finish(void){if(getpid()==owner && retained>0) waitpid(retained,NULL,0);}
int close(int fd){
 int (*original)(int)=dlsym(RTLD_NEXT,"close");
 if(getpid()==owner && retained==-1){
  char link[64],path[PATH_MAX];snprintf(link,sizeof link,"/proc/self/fd/%d",fd);
  ssize_t n=readlink(link,path,sizeof path-1);int mode=fcntl(fd,F_GETFL);
  if(n>0 && mode>=0 && (mode&O_ACCMODE)!=O_RDONLY){
   path[n]=0;
   const char *name=strrchr(path,'/');
   if(strstr(path,"/service/builds/") && name && strcmp(name,"/openwiz-service")==0){
    int ack[2];if(pipe(ack)!=0)_exit(91);
    int keep=getenv("OW_UPDATE_KEEP_WRITER") && strcmp(getenv("OW_UPDATE_KEEP_WRITER"),"1")==0;
    pid_t child=fork();if(child==-1)_exit(92);
    if(child==0){original(ack[0]);if(!keep)original(fd);if(write(ack[1],"x",1)!=1)_exit(93);original(ack[1]);struct timespec pause={30,0};nanosleep(&pause,NULL);_exit(0);}
    retained=child;original(ack[1]);char byte;if(read(ack[0],&byte,1)!=1)_exit(94);original(ack[0]);
    const char *note=keep?"probe: inherited candidate writer retained\n":"probe: inherited candidate writer closed\n";
    write(STDERR_FILENO,note,strlen(note));
   }
  }
 }
 return original(fd);
}
