#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/shm.h>
#include <string.h>

/* This program allocates COUNT shm regions, each of size SHMSIZE.
 *
 * It ensures they get mapped into memory by calling memset.
 */

#define MB (1024 * 1024)
#define SHMSIZE (100 * MB)
#define COUNT 5

int main() {
  fprintf(stderr, "start\n");
  for (int i=0; i<COUNT; i++) {
    int shmid = shmget(1337 + i, SHMSIZE, IPC_CREAT | 0666);
    if (shmid == -1) {
      fprintf(stderr, "shmget fail %s\n", strerror(errno));
      return -1;
    }
    void *m = shmat(shmid, NULL, 0);
    if (m == -1) {
      fprintf(stderr, "shmat fail %s\n", strerror(errno));
      return -1;
    }

    memset(m, 1, SHMSIZE);
  }

  fprintf(stderr, "done\n");
}
