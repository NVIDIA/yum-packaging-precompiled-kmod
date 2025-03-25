# yum packaging precompiled kmod

## OCI

```shell
podman pull rockylinux:9;
podman run -it rockylinux:9 /bin/bash -c \
'dnf install -y dnf-plugins-core kernel-core kernel-headers kernel-devel && \
 testUTILS=https://copr.fedorainfracloud.org/coprs/rpmsoftwaremanagement/test-utils && \
 dnf config-manager --add-repo $testUTILS/repo/epel-9/rpmsoftwaremanagement-test-utils-epel-9.repo && \
 dnf install -y fakeuname epel-release gcc-g++ && bash'
```

Now enter a subshell

```
$ KERNEL=$(rpm -qa | grep kernel-core | sort -Vr | awk NR==1 | sed "s|kernel\-core\-||"); fakeuname "$KERNEL" bash
```

Then within the subshell

```shell
# uname -r
5.14.0-503.29.1.el9_5.x86_64
```

```shell
# dnf config-manager --add-repo https://developer.download.nvidia.com/compute/cuda/repos/rhel9/x86_64/cuda-rhel9.repo
```

```shell
# dnf install -y nvidia-driver-cuda kmod-nvidia-open-dkms
  Running scriptlet: nvidia-kmod-common-3:570.124.06-1.el9.noarch                                                              17/20
Nvidia driver setup: no bootloader configured. Please run 'nvidia-boot-update post' manually.
grep: /etc/kernel/cmdline: No such file or directory
[...]
Complete!
```

```shell
# dkms status
nvidia-open/570.124.06, 5.14.0-503.29.1.el9_5.x86_64, x86_64: installed
```

```shell
# find /lib/modules -name "nvidia*ko*"
/lib/modules/5.14.0-503.29.1.el9_5.x86_64/extra/nvidia.ko.xz
/lib/modules/5.14.0-503.29.1.el9_5.x86_64/extra/nvidia-modeset.ko.xz
/lib/modules/5.14.0-503.29.1.el9_5.x86_64/extra/nvidia-drm.ko.xz
/lib/modules/5.14.0-503.29.1.el9_5.x86_64/extra/nvidia-uvm.ko.xz
/lib/modules/5.14.0-503.29.1.el9_5.x86_64/extra/nvidia-peermem.ko.xz
```
