# LinuxCNC: Getting and Running LinuxCNC

<!--
Source: LinuxCNC_Documentation_2.9.pdf
Original PDF pages: 61-70 (printed pages 6-15)
Included complete sections: 1.3 Getting LinuxCNC and 1.4 Running LinuxCNC
Format: text-only Markdown conversion for indexing tests
-->

## 1.3 Getting LinuxCNC

This section describes the recommended way to download and make a fresh install of LinuxCNC. There are also Alternate Install Methods for the adventurous. If you have an existing install that you want to upgrade, go to the Updating LinuxCNC section instead.

> **Note**
>
> To operate machinery LinuxCNC requires a special kernel with real-time extensions. There are three possibilities here: preempt-rt, RTAI or Xenomai. In addition there are two versions of LinuxCNC which work with these kernels. See the table below for details. However for code testing and simulation it is possible to run the `linuxcnc-uspace` application on a stock kernel.

Fresh installs of LinuxCNC are most easily created using the Live/Install Image. This is a hybrid ISO filesystem image that can be written to a USB storage device or a DVD and used to boot a computer. At boot time you will be given a choice of booting the “Live” system (to run LinuxCNC without making any permanent changes to your computer) or booting the Installer (to install LinuxCNC and its operating system onto your computer’s hard drive).

The outline of the process looks like this:

1. Download the Live/Install Image.
2. Write the image to a USB storage device or DVD.
3. Boot the Live system to test out LinuxCNC.
4. Boot the Installer to install LinuxCNC.

### 1.3.1 Download the image

This section describes some methods for downloading the Live/Install image.

#### 1.3.1.1 Normal Download

Software for LinuxCNC to download is presented on the project’s [Downloads page](https://linuxcnc.org/downloads/). Most users will aim for the disk image for Intel/AMD PCs, the URL will resemble <https://www.linuxcnc.org/iso/linuxcnc_2.9.4-amd64.hybrid.iso>.

For the Raspberry Pi, multiple images are provided to address differences between the RPi4 and RPi5.

> **Note**
>
> Do not use the regular Raspbian distribution for LinuxCNC that may have shipped with your RPi starter kit — that will not have the real-time kernel and you cannot migrate from Raspbian to Debian’s kernel image.

#### 1.3.1.2 Download using zsync

`zsync` is a download application that efficiently resumes interrupted downloads and efficiently transfers large files with small modifications (if you have an older local copy). Use `zsync` if you have trouble downloading the image using the Normal Download method.

**zsync in Linux**

1. Install `zsync` using Synaptic or by running the following in a terminal:

   ```bash
   sudo apt-get install zsync
   ```

2. Then run this command to download the ISO to your computer:

   ```bash
   zsync https://www.linuxcnc.org/iso/linuxcnc_2.9.4-amd64.hybrid.iso
   ```

**zsync in Windows**

There is a Windows port of `zsync`. It works as a console application and can be downloaded from <https://www.assembla.com/spaces/zsync-windows/documents>.

#### 1.3.1.3 Verify the image

(This step is unnecessary if you used `zsync`.)

1. After downloading, verify the checksum of the image to ensure integrity.

   ```bash
   md5sum linuxcnc-2.9.4-amd64.iso
   ```

   or

   ```bash
   sha256sum linuxcnc-2.9.4-amd64.iso
   ```

2. Then compare to these checksums:

   **amd64 (PC)**

   ```text
   md5sum: 1815aceaac0e7861747aa34d61846e79
   sha256sum: 08b3f59233e47c91cf1c9a85c41df48542c97b134efefa7446d3060c9a3e644b
   ```

   **arm64 (Pi)**

   ```text
   md5sum: 4547e8a72433efb033f0a5cf166a5cd2
   sha256sum: ff3ba9b8dfb93baf1e2232746655f8521a606bc0fab91bffc04ba74cc3be6bf0
   ```

**Verify md5sum on Windows or Mac**

Windows and Mac OS X do not come with an `md5sum` program, but there are alternatives. More information can be found at [HowToMD5SUM](https://help.ubuntu.com/community/HowToMD5SUM).

### 1.3.2 Write the image to a bootable device

The LinuxCNC Live/Install ISO Image is a hybrid ISO image which can be written directly to a USB storage device (flash drive) or a DVD and used to boot a computer. The image is too large to fit on a CD.

#### 1.3.2.1 Raspberry Pi Image

The Raspbery Pi image is a completes SD card image and should be written to an SD card with the [Raspberry Pi Imager App](https://www.raspberrypi.com/software/).

#### 1.3.2.2 AMD-64 (x86-64, PC) Image using GUI tools

Download and install [Balena Etcher](https://etcher.balena.io/#download-etcher) (Linux, Windows, Mac) and write the downloaded image to a USB drive.

If your image fails to boot then please also try [Rufus](https://rufus.ie/). It looks more complicated but seems to be more compatible with various BIOSes.

#### 1.3.2.3 Command line — Linux

1. Connect a USB storage device (for example a flash drive or thumb drive type device).
2. Determine the device file corresponding to the USB flash drive. This information can be found in the output of `dmesg` after connecting the device. `/proc/partitions` may also be helpful.
3. Use the `dd` command to write the image to your USB storage device. For example, if your storage device showed up as `/dev/sde`, then use this command:

   ```bash
   dd if=linuxcnc_2.9.4-amd64.hybrid.iso of=/dev/sde
   ```

#### 1.3.2.4 Command line — MacOS

1. Open a terminal and type:

   ```bash
   diskutil list
   ```

2. Insert the USB and note the name of the new disk that appears, e.g. `/dev/disk5`.
3. Unmount the USB. The number found above should be substitued in place of the N:

   ```bash
   diskutil unmountDisk /dev/diskN
   ```

4. Transfer the data with `dd`, as for Linux above. Note that the disk name has an added “r” at the begining:

   ```bash
   sudo dd if=linuxcnc_2.9.4-amd64.hybrid.iso of=/dev/rdiskN bs=1m
   ```

5. Note that this may take a long time to complete and there will be no feedback during the process.

**Writing the image to a DVD in Linux**

1. Insert a blank DVD into your burner. A CD/DVD Creator or Choose Disc Type window will pop up. Close this, as we will not be using it.
2. Browse to the downloaded image in the file browser.
3. Right-click on the ISO image file and choose Write to Disc.
4. Select the write speed. It is recommended that you write at the lowest possible speed.
5. Start the burning process.
6. If a “choose a file name for the disc image” window pops up, just pick OK.

**Writing the image to a DVD in Windows**

1. Download and install InfraRecorder, a free and open source image burning program: <http://infrarecorder.org/>.
2. Insert a blank CD in the drive and select Do nothing or Cancel if an auto-run dialog pops up.
3. Open InfraRecorder, and select the Actions menu, then Burn image.

**Writing the image to a DVD in Mac OSX**

1. Download the `.iso` file.
2. Right-click on the file in the Finder window and select “Burn to disc”. (The option to burn to disc will only appear if the machine has an optical drive fitted or connected.)

### 1.3.3 Testing LinuxCNC

With the USB storage device plugged in or the DVD in the DVD drive, shut down the computer then turn the computer back on. This will boot the computer from the Live/Install Image and choose the Live boot option.

> **Note**
>
> If the system does not boot from the DVD or USB stick, it may be necessary to change the boot order in the PC BIOS.

Once the computer has booted up you can try out LinuxCNC without installing it. You can not create custom configurations or modify most system settings in a Live session, but you can (and should) run the latency test.

To try out LinuxCNC: from the Applications/CNC menu pick LinuxCNC. A dialog box will open from which you can choose one of many sample configurations. At this point it only really makes sense to pick a “sim” configuration. Some of the sample configurations include onscreen 3D simulated machines, look for “Vismach” to see these.

To see if your computer is suitable for software step pulse generation run the Latency Test as shown here.

At the time of writing the Live Image is only available with the preempt-rt kernel and a matching LinuxCNC. On some hardware this might not offer good enough latency. There is an experimental version available using the RTAI realtime kernel which will often give better latency.

### 1.3.4 Installing LinuxCNC

To install LinuxCNC from the Live CD select Install (Graphical) at bootup.

### 1.3.5 Updates to LinuxCNC

With the normal install the Update Manager will notify you of updates to LinuxCNC when you go online and allow you to easily upgrade with no Linux knowledge needed. It is OK to upgrade everything except the operating system when asked to.

> **Warning**
>
> Do not upgrade the operating system if prompted to do so. You should accept OS updates however, especially security updates.

### 1.3.6 Install Problems

In rare cases you might have to reset the BIOS to default settings if during the Live CD install it cannot recognize the hard drive during the boot up.

### 1.3.7 Alternate Install Methods

The easiest, preferred way to install LinuxCNC is to use the Live/Install Image as described above. That method is as simple and reliable as we can make it, and is suitable for novice users and experienced users alike. However, this will typically replace any existing operating system. If you have files on the target PC that you want to keep, then use one of the methods described in this section.

In addition, for experienced users who are familiar with Debian system administration (finding install images, manipulating apt sources, changing kernel flavors, etc.), new installs are supported on the following platforms: (“amd64” means “64-bit”, and is not specific to AMD processors, it will run on any 64-bit x86 system.)

| Distribution | Architecture | Kernel | Package name | Typical use |
| --- | --- | --- | --- | --- |
| Debian Bookworm | amd64 & arm64 | preempt-rt | linuxcnc-uspace | machine control & simulation |
| Debian Bookworm | amd64 | RTAI | linuxcnc | machine control |
| Debian Bullseye | amd64 | preempt-rt | linuxcnc-uspace | machine control & simulation |
| Debian Buster | amd64 & arm64 | preempt-rt | linuxcnc-uspace | machine control & simulation |
| Debian Buster | amd64 | RTAI | linuxcnc | machine control |
| Any | Any | Stock | linuxcnc-uspace | simulation ONLY |

> **Note**
>
> LinuxCNC v2.9 is not supported on Debian 9 or older.

**Preempt-RT kernels**

The Preempt-RT kernels are available for Debian from the regular debian.org archive. The package is called `linux-image-rt-*`. Simply install the package in the same way as any other package from the Synaptic Package Manager or with `apt-get` at the command line.

**RTAI Kernels**

The RTAI kernels are available for download from the linuxcnc.org Debian archive. The apt sources are:

- Debian Bookworm: `deb http://linuxcnc.org bookworm base`
- Debian Bullseye: `deb http://linuxcnc.org bullseye base`
- Debian Buster: `deb http://linuxcnc.org buster base`

LinuxCNC and the RTAI kernel are now only available for 64-bit OSes but there are very few surviving systems that can not run a 64-bit OS.

#### 1.3.7.1 Installing on Debian Bookworm (with Preempt-RT kernel)

1. Install Debian Bookworm (Debian 12), amd64 version. You can download the installer here: <https://www.debian.org/distrib/>.
2. After burning the ISO and booting up, if you don’t want Gnome desktop select Advanced Options > Alternative desktop environments and pick the one you like. Then select Install or Graphical Install.

   > **Warning**
   >
   > Do not enter a root password. If you do, sudo is disabled and you won’t be able to complete the following steps.

3. Run the following in a terminal to bring the machine up to date with the latest packages:

   ```bash
   sudo apt-get update
   sudo apt-get dist-upgrade
   ```

   > **Note**
   >
   > It is possible to download a version of LinuxCNC directly from Debian but this will install an old pre-release version, and is not recommended at this time.

1. Install the Preempt-RT kernel and modules:

   ```bash
   sudo apt-get install linux-image-rt-amd64
   ```

2. Reboot and select the Linux `6.1.0-10-rt-amd64` kernel. The exact kernel version might be different, look for the `-rt` suffix. This might be hidden in the “Advanced options for Debian Bookworm” submenu in Grub. When you log in, verify that `PREEMPT RT` is reported by the following command:

   ```bash
   uname -v
   ```

3. Open Applications Menu > System > Synaptic Package Manager, search for `linux-image` and right-click on the original non-RT and select Mark for Complete Removal. Reboot. This is to force the system to boot from the RT kernel. If you prefer to retain both kernels then the other kernels need not be deleted, but Grub boot configuration changes will be needed beyond the scope of this document.
4. Add the LinuxCNC Archive Signing Key to your apt keyring by downloading [the LinuxCNC installer script](https://www.linuxcnc.org/linuxcnc-install.sh). You will need to make the script executable to run it:

   ```bash
   chmod +x linuxcnc-install.sh
   ```

   Then you can run the installer:

   ```bash
   sudo ./linuxcnc-install.sh
   ```

#### 1.3.7.2 Installing on Debian Bookworm (with experimental RTAI kernel)

1. This kernel and LinuxCNC version can be installed on top of the Live DVD install, or alternatively on a fresh install of Debian Bookworm 64-bit as described above.
2. You can add the LinuxCNC Archive signing key and repository information by downloading and running the installer script as decribed above. If an RTAI kernel is detected it will stop before installing any packages.
3. Update the package list from linuxcnc.org:

   ```bash
   sudo apt-get update
   ```

4. Remove the existing uspace version of LinuxCNC and install the new realtime kernel, RTAI and the RTAI version of LinuxCNC:

   ```bash
   sudo apt-get purge linuxcnc-uspace
   sudo apt-get purge linuxcnc-doc*
   sudo apt-get install linuxcnc
   ```

Reboot the machine, ensuring that the system boots from the new `5.4.258-rtai` kernel.

#### 1.3.7.3 Installing on Raspbian 12

Don’t do that. The latencies are too bad with the default kernel and the PREEMPT_RT (the RT is important) kernel of Debian does not boot on the Pi (as of 1/2024). Please refer to the images provided online. You can create them yourself following the [scripts provided online](https://github.com/rodw-au/rpi-img-builder-lcnc).

## 1.4 Running LinuxCNC

### 1.4.1 Invoking LinuxCNC

After installation, LinuxCNC starts just like any other Linux program: run it from the terminal by issuing the command `linuxcnc`, or select it in the Applications → CNC menu.

### 1.4.2 Configuration Launcher

When starting LinuxCNC (from the CNC menu or from the command line without specifying an INI file) the Configuration Selector dialog starts.

The Configuration Selector dialog allows the user to pick one of their existing configurations (My Configurations) or select a new one (from the Sample Configurations) to be copied to their home directory. Copied configurations will appear under My Configurations on the next invocation of the Configuration Selector.

The Configuration Selector offers a selection of configurations organized as follows:

- **My Configurations** — user configurations located in `linuxcnc/configs` in your home directory.
- **Sample Configurations** — sample configurations, when selected, are copied to `linuxcnc/configs`. Once a sample configuration was copied to your local directory, the launcher will offer it as My Configurations. The names under which these local configurations are presented correspond to the names of the directories within the `configs/` directory:
  - `sim` — configurations that include simulated hardware. These can be used for testing or learning how LinuxCNC works.
  - `by_interface` — configurations organized by GUI.
  - `by_machine` — configurations organized by machine.
  - `apps` — applications that do not require starting LinuxCNC but may be useful for testing or trying applications like PyVCP or GladeVCP.
  - `attic` — obsolete or historical configurations.

The `sim` configurations are often the most useful starting point for new users and are organized around supported GUIs:

- `axis` — keyboard and mouse GUI.
- `craftsman` — touch screen GUI (no longer maintained ???).
- `gmoccapy` — touch screen GUI.
- `gscreen` — touch screen GUI.
- `pyvcp_demo` — Python Virtual Control Panel.
- `qtaxis` — touch screen GUI, AXIS lookalike.
- `qtdragon` — touch screen GUI.
- `qtdragon_hd` — touch screen GUI, high definition.
- `qtplasmac` — touch screen GUI for plasma tables.
- `qttouchy` — touch screen GUI.
- `tklinuxcnc` — keyboard and mouse GUI (no longer maintained).
- `touchy` — touch screen GUI.
- `woodpecker` — touch screen GUI.

A GUI configuration directory may contain subdirectories with configurations that illustrate special situations or the embedding of other applications.

The `by_interface` configurations are organized around common, supported interfaces like:

- `generalmechatronics`
- `mesa`
- `parport`
- `pico`
- `pluto`
- `servotogo`
- `vigilant`
- `vitalsystems`

Related hardware may be required to use these configurations as starting points for a system.

The `by_machine` configurations are organized around complete, known systems like:

- `boss`
- `cooltool`
- `scortboterIII`
- `sherline`
- `smithy`
- `tormach`

A complete system may be required to use these configurations.

The `apps` items are typically either:

1. Utilities that don’t require starting LinuxCNC.
2. Demonstrations of applications that can be used with LinuxCNC.

The available applications include:

- `info` — creates a file with system information that may be useful for problem diagnosis.
- `gladevcp` — example GladeVCP applications.
- `halrun` — starts `halrun` in a terminal.
- `latency` — applications to investigate latency:
  - `latency-histogram-1` — histogram for single servo thread.
  - `latency-histogram` — histogram.
  - `latency-test` — standard test.
  - `latency-plot` — stripchart.
- `parport` — applications to test parport.
- `pyvcp` — example PyVCP applications.
- `xhc-hb04` — applications to test an `xhc-hb04` USB wireless MPG.

> **Note**
>
> Under the Apps directory, only applications that are usefully modified by the user are offered for copying to the user’s directory.

*Figure 1.1: LinuxCNC Configuration Selector*

Click any of the listed configurations to display specific information about it. Double-click a configuration or click OK to start the configuration.

Select Create Desktop Shortcut and then click OK to add an icon on the Ubuntu desktop to directly launch this configuration without showing the Configuration Selector screen.

When you select a configuration from the Sample Configurations section, it will automatically place a copy of that config in the `~/linuxcnc/configs` directory.

### 1.4.3 Next steps in configuration

After finding the sample configuration that uses the same interface hardware as your machine (or a simulator configuration), and saving a copy to your home directory, you can customize it according to the details of your machine. Refer to the Integrator Manual for topics on configuration.

### 1.4.4 Simulator Configurations

All configurations listed under Sample Configurations/sim are intended to run on any computer. No specific hardware is required and real-time support is not needed.

These configurations are useful for studying individual capabilities or options. The `sim` configurations are organized according to the graphical user interface used in the demonstration. The directory for `axis` contains the most choices and subdirectories because it is the most tested GUI. The capabilities demonstrated with any specific GUI may be available in other GUIs as well.

### 1.4.5 Configuration Resources

The Configuration Selector copies all files needed for a configuration to a new subdirectory of `~/linuxcnc/configs` (equivalently: `/home/username/linuxcnc/configs`). Each created directory will include at least one INI file (`inifilename.ini`) that is used to describe a specific configuration.

File resources within the copied directory will typically include one or more INI files (`filename.ini`) for related configurations and a tool table file (`toolfilename.tbl`). Additionally, resources may include HAL files (`filename.hal`, `filename.tcl`), a README file for describing the directory, and configuration-specific information in a text file named after a specific configuration (`inifilename.txt`). That latter two files are displayed when using the Configuration Selector.

The supplied sample configurations may specify the parameter `HALFILE` (`filename.hal`) in the configuration INI file that are not present in the copied directory because they are found in the system HAL file library. These files can be copied to the user configuration directory and altered as required by the user for modification or test. Since the user configuration directory is searched first when finding HAL files, local modifications will then prevail.

The Configuration Selector makes a symbolic link in the user configuration directory (named `hallib`) that points to the system HAL file library. This link simplifies copying a library file. For example, to copy the library `core_sim.hal` file in order to make local modifications:

```bash
cd ~/linuxcnc/configs/name_of_configuration
cp hallib/core_sim.hal core_sim.hal
```
