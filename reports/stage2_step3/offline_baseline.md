## Сводка

| Метрика | Значение |
|---|---|
| `samples` | 42 |
| `retrieval/recall@k` | 1.000 |
| `retrieval/hit_rate` | 1.000 |
| `retrieval/mrr` | 1.000 |
| `answer/token_f1` | 0.265 |
| `answer/must_include` | 0.693 |
| `citations/precision` | 1.000 |
| `citations/recall` | 1.000 |
| `citations/answered_with_citation` | 1.000 |
| `hallucination/false_refusal_rate` | 0.000 |
| `hallucination/trap_refusal_rate` | 0.000 |
| `latency/mean_s` | 0.002 |

## По вопросам

| id | recall@k | F1 | факты | цит. P | отказ | ответ |
|---|---|---|---|---|---|---|
| lc01 | 1.00 | 0.29 | 1.00 | 1.00 | нет | This section describes the recommended way to download and make a fresh install of Linu… |
| lc02 | 1.00 | 0.18 | 0.00 | 1.00 | нет | This section describes the recommended way to download and make a fresh install of Linu… |
| lc03 | 1.00 | 0.32 | 0.75 | 1.00 | нет | See the table below for details. However for code testing and simulation it is possible… |
| lc04 | 1.00 | 0.39 | 1.00 | 1.00 | нет | Software for LinuxCNC to download is presented on the project’s [Downloads page](https:… |
| lc05 | 1.00 | 0.17 | 1.00 | 1.00 | нет | Software for LinuxCNC to download is presented on the project’s [Downloads page](https:… |
| lc06 | 1.00 | 0.25 | 1.00 | 1.00 | нет | Software for LinuxCNC to download is presented on the project’s [Downloads page](https:… |
| lc07 | 1.00 | 0.36 | 1.00 | 1.00 | нет | `zsync` is a download application that efficiently resumes interrupted downloads and ef… |
| lc08 | 1.00 | 0.18 | 1.00 | 1.00 | нет | `zsync` is a download application that efficiently resumes interrupted downloads and ef… |
| lc09 | 1.00 | 0.16 | 0.00 | 1.00 | нет | `zsync` is a download application that efficiently resumes interrupted downloads and ef… |
| lc10 | 1.00 | 0.10 | 1.00 | 1.00 | нет | (This step is unnecessary if you used `zsync`.)  1. After downloading, verify the check… |
| lc11 | 1.00 | 0.00 | 0.00 | 1.00 | нет | The Raspbery Pi image is a completes SD card image and should be written to an SD card … |
| lc12 | 1.00 | 0.67 | 1.00 | 1.00 | нет | The LinuxCNC Live/Install ISO Image is a hybrid ISO image which can be written directly… |
| lc13 | 1.00 | 0.68 | 1.00 | 1.00 | нет | The Raspbery Pi image is a completes SD card image and should be written to an SD card … |
| lc14 | 1.00 | 0.07 | 0.00 | 1.00 | нет | ```  5. Note that this may take a long time to complete and there will be no feedback d… |
| lc15 | 1.00 | 0.33 | 1.00 | 1.00 | нет | 1. Connect a USB storage device (for example a flash drive or thumb drive type device).… |
| lc16 | 1.00 | 0.28 | 1.00 | 1.00 | нет | 1. Connect a USB storage device (for example a flash drive or thumb drive type device).… |
| lc17 | 1.00 | 0.21 | 1.00 | 1.00 | нет | 1. Open a terminal and type:  ```bash    diskutil list    ```  2. Insert the USB and no… |
| lc18 | 1.00 | 0.35 | 1.00 | 1.00 | нет | 1. Open a terminal and type:  ```bash    diskutil list    ```  2. Insert the USB and no… |
| lc19 | 1.00 | 0.10 | 1.00 | 1.00 | нет | ```  5. Note that this may take a long time to complete and there will be no feedback d… |
| lc20 | 1.00 | 0.32 | 1.00 | 1.00 | нет | Start the burning process. 6. If a “choose a file name for the disc image” window pops … |
| lc21 | 1.00 | 0.21 | 0.00 | 1.00 | нет | The LinuxCNC Live/Install ISO Image is a hybrid ISO image which can be written directly… |
| lc22 | 1.00 | 0.16 | 0.00 | 1.00 | нет | See the table below for details. However for code testing and simulation it is possible… |
| lc23 | 1.00 | 0.38 | 1.00 | 1.00 | нет | makes sense to pick a “sim” configuration. Some of the sample configurations include on… |
| lc24 | 1.00 | 0.02 | 0.00 | 1.00 | нет | With the USB storage device plugged in or the DVD in the DVD drive, shut down the compu… |
| lc25 | 1.00 | 0.04 | 0.00 | 1.00 | нет | After installation, LinuxCNC starts just like any other Linux program: run it from the … |
| lc26 | 1.00 | 0.43 | 1.00 | 1.00 | нет | In rare cases you might have to reset the BIOS to default settings if during the Live C… |
| lc27 | 1.00 | 0.22 | 0.60 | 1.00 | нет | from Debian but this will install an old pre-release version, and is not recommended at… |
| lc28 | 1.00 | 0.08 | 0.00 | 1.00 | нет | \| Distribution \| Architecture \| Kernel \| Package name \| Typical use \| \| --- \| -… |
| lc29 | 1.00 | 0.10 | 1.00 | 1.00 | нет | 1. Install Debian Bookworm (Debian 12), amd64 version. You can download the installer h… |
| lc30 | 1.00 | 0.35 | 1.00 | 1.00 | нет | from Debian but this will install an old pre-release version, and is not recommended at… |
| lc31 | 1.00 | 0.16 | 0.33 | 1.00 | нет | Any \| Any \| Stock \| linuxcnc-uspace \| simulation ONLY \|  > **Note** > > LinuxCNC v… |
| lc32 | 1.00 | 0.44 | 1.00 | 1.00 | нет | Don’t do that. The latencies are too bad with the default kernel and the PREEMPT_RT (th… |
| lc33 | 1.00 | 0.57 | 1.00 | 1.00 | нет | After installation, LinuxCNC starts just like any other Linux program: run it from the … |
| lc34 | 1.00 | 0.40 | 1.00 | 1.00 | нет | on the next invocation of the Configuration Selector.  The Configuration Selector offer… |
| lc35 | 1.00 | 0.29 | 1.00 | 1.00 | нет | All configurations listed under Sample Configurations/sim are intended to run on any co… |
| lc36 | 1.00 | 0.29 | 0.25 | 1.00 | нет | in a text file named after a specific configuration (`inifilename.txt`). That latter tw… |
| lc37 | — | — | — | — | нет ✘ (ловушка) | Software for LinuxCNC to download is presented on the project’s [Downloads page](https:… |
| lc38 | — | — | — | — | нет ✘ (ловушка) | See the table below for details. However for code testing and simulation it is possible… |
| lc39 | — | — | — | — | нет ✘ (ловушка) | When starting LinuxCNC (from the CNC menu or from the command line without specifying a… |
| lc40 | — | — | — | — | нет ✘ (ловушка) | With the USB storage device plugged in or the DVD in the DVD drive, shut down the compu… |
| lc41 | — | — | — | — | нет ✘ (ловушка) | makes sense to pick a “sim” configuration. Some of the sample configurations include on… |
| lc42 | — | — | — | — | нет ✘ (ловушка) | Any \| Any \| Stock \| linuxcnc-uspace \| simulation ONLY \|  > **Note** > > LinuxCNC v… |
