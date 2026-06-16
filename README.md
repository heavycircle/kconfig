# KConfig

_KConfig_ aims to reverse-engineer kernel `.config` files.

## Background

Reversing a `.config` from a kernel is a extremely difficult task. This is most important when a kernel is configured with `CONFIG_MODVERSIONS=y`, requiring kernel modules be built with proper signatures (CRC checksums) for all function signatures and declared structures. You can check if a kernel was built `modversions` using `uname -a`. Additionally, local kernel modules can reveal if they were built with `modversions` using `modinfo`.

_Kconfig_ takes away a lot of the grunt work of reverse engineering the configuration by automatically checking structures from known-good modules, then using the specific kernel's header files to determine the `CONFIG` values that produce the proper kernel.

Sometimes, kernels are called _frankenstein kernels_, which are kernels that partially patch older kernels with newer kernel versions. This allows custom kernels to remove bugs associated with old kernel versions in relevant locations without having to refactor their entire project to support major API changes. _KConfig_ does not yet support identifying and reporting frankenstein kernels.

Other times, kernels are patched with common security or feature patches, such as the _PREEMPT_RT_ or _linux-pf_ patch. These can provide many benefits, to include additional security and watchdog metrics, kernel minifiers, etc. _KConfig_ does not yet support identifying kernel patches.

## How _KConfig_ Works

TODO - Write this
