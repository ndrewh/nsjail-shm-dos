nsjail DoS using shared memory
====

Disclaimer: This was reported using the process in the project's [security.md](https://github.com/google/.github/blob/master/SECURITY.md), but was found to be
"not severe enough for us to track it as a security bug". Therefore, I am filing it as a functional bug (`s/PoC/reproducer/g`). https://github.com/google/nsjail/issues/231

This demonstrates how a process running in nsjail
with strict cgroup-based memory limits can cause
processes outside the jail to be killed by the OOM-killer. This
uses the Sys-V shared memory mechanism (shmget, shmat, etc.),
which does not require any unusual mappings or
options passed to nsjail.

The vulnerability is triggered by setting up and using a large amount of shared memory (up to the maximum allowed by cgroup_mem_max) in a number of short-running processes. This type of shared memory will not be immediately cleaned up by the kernel upon the exit of the jailed process (this is by design in Linux -- more detail at the end of this writeup), and will remain resident in RAM and unclaimable by other processes. This type of shared memory will eventually be cleaned up by the kernel in the background after the IPC namespace is destroyed, allowing it to be reclaimed by other processes. However, this may take many seconds to occur, especially if there are a large number of shared memory regions. The shared memory regions can be immediately reclaimed by other processes if deliberately destroyed by the user i.e. with `ipcrm -a`.

The important parts of our configuration are below (see jail.cfg):

```
mode: LISTEN
time_limit: 10
max_conns: 20

# 500MB
cgroup_mem_max: 536870912

# No swap
cgroup_mem_swap_max: 0

# 1 sec CPU per second
cgroup_cpu_ms_per_sec: 1000
```

Our PoC uses LISTEN mode, but this is not strictly required---
any setup where ***namespaces are created for every execution***
is vulnerable: for example, downstream applications which wrap nsjail in ONCE
mode but allow multiple executions (e.g. compiler explorer, Google's [kctf](https://github.com/google/kctf/blob/v1/dist/challenge-templates/pwn/challenge/nsjail.cfg)) are likely
vulnerable to the same attack.

The attack also works fine if you only set `cgroup_mem_memsw_max` instead
of the two options above. A reading of the above configuration suggests
that the processes spawned by the jail ought to never exceed a total
of 20 * 0.5GB = 10GB of memory. Our reproducer is able to consume
1TB of RAM in ~5 minutes with only 10 simultaneous connections.

Tested on:
- 5.15.0-89-generic
- 6.2.0-1018-aws

Running the reproducer
---

To run the reproducer, we assume a machine with at least
32GB of RAM. You may need to reduce the number of allocations
(`COUNT` in app.c) to run on machines with less RAM than this. The exploit was
tested on a 1TB machine and 32GB machine.

To run and build the vulnerable nsjail:

```
git clone git@github.com:google/nsjail.git
cd nsjail
docker build -t nsjailcontainer .
cd ..
docker build -t nsjaildos .
docker run -it --cgroupns=host --privileged --rm -p 1337:1337 nsjaildos
```

At this point nsjail is listening on port 1337. Now you can run the poc on the host:

WARNING: If you have a large amount of swap, this will quickly make your computer very slow or unstable.

```
python3 poc.py
```

Expected output:
```
victim started at 2024-05-27 18:17:46.096278
victim is dead at 2024-05-27 18:22:29.451227
```

While the exploit is running, you can watch `htop` in awe
as the RAM usage increases without bound. The PoC demonstrates
that a process running on the host (running `victim_thread`)
is killed by the OOM-killer (verify with `sudo dmesg | grep Killed`)
as a result of processes running in nsjail.

The victim will get killed much quicker on a machine with less ram.

- 32 GB RAM: ~5 seconds
- 1 TB RAM: ~3-5 minutes

Explanation
----

This shows an attacker with sandboxed code execution
can reserve memory that persists beyond the termination of the
sandboxed process. I believe the reason is that IPC namespace cleanup
is performed lazily by a kernel workqueue ([source](https://elixir.bootlin.com/linux/v6.2.11/source/ipc/namespace.c#L163)).
This workqueue cannot keep up with the creation of new namespaces by nsjail, and thus
the shared memory regions are not promptly freed. I suspect Linux has good reasons for doing things this way,
but it does mean that nsjail needs to clean up the IPC resources itself.

Fix
----

The issue can be fixed by destroying the IPC resources
in the sandbox IPC namespace (e.g. with `ipcrm -a` from within the sandbox) as part of
the cleanup of the jail.

It's not clear exactly how this should happen within nsjail, simply because the only
process running within the namespace is, by design, the target process. Once that process
exits, we need to run cleanup inside the namespace. This seems a bit tricky---my thought
is for nsjail to spawn another process, have it `setns` into the IPC namespace of the child
before the child execve's, and then once the child exits, it can cleanup IPC resources
(e.g. as in [ipcrm](https://github.com/util-linux/util-linux/blob/55ca447a6a95226fd031a126fb48b01b3efd6284/sys-utils/ipcrm.c#L74)).

### Attack scenario

This vulnerability enables a low-complexity denial-of-service attack by a user with sandboxed code execution. nsjail is a component that was deliberately designed to prevent such attacks.

nsjail is often used to run untrusted user code for multiple users on the same machine (for example, in [compiler explorer](https://godbolt.org)) (where anyone can submit code). nsjail is also used by google's [kctf](https://github.com/google/kctf) project, where untrusted, anonymous users have sandboxed code execution.
