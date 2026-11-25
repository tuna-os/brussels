# License Information

## Brussels BuildStream Project

This project integrates multiple open-source components with various licenses. 

### Project Configuration & Build Infrastructure
The BuildStream project configuration, element definitions, and build automation scripts in this repository are provided as-is for building Brussels distributions.

### Component Licenses

This project builds and integrates the following components, each with their own licenses:

#### freedesktop-sdk
- **License:** Multiple (LGPL, MIT, GPL)
- **Source:** https://gitlab.com/freedesktop-sdk/freedesktop-sdk

#### gnome-build-meta
- **License:** Multiple (LGPL, MIT, GPL)
- **Source:** https://gitlab.gnome.org/GNOME/gnome-build-meta

#### XFCE Desktop Environment
- **License:** GPL 2.0 or later
- **Components:** xfce4-session, xfce4-panel, xfwm4, xfdesktop, xfce4-terminal, etc.
- **Source:** https://github.com/xfce-mirror/ and https://github.com/tuna-os/brussels

#### xfce-wayland (Wayland Support)
- **License:** GPL 2.0 or later
- **Source:** https://github.com/tuna-os/brussels

#### Linux Kernel
- **License:** GPL 2.0
- **Source:** https://www.kernel.org/

#### BuildStream
- **License:** LGPL 2.1
- **Source:** https://buildstream.build/

#### Podman
- **License:** Apache 2.0
- **Source:** https://podman.io/

### Additional Libraries

This project includes many additional libraries and tools from:
- GNU (glib, gcc, etc.) — LGPL
- Freedesktop (dbus, systemd, etc.) — LGPL/MIT
- Mesa 3D — MIT
- And many others (see respective upstream projects)

### Your Contributions

When you contribute to this project:
- Your contributions are assumed to be compatible with the above licenses
- You confirm you have the right to license your contributions
- Your contributions may be used under the same terms as the project

### License Compliance

When building and distributing images from this project:

1. **Comply with GPL requirements:** Provide source code access for GPL components
2. **Respect LGPL requirements:** Include LGPL license texts and library information
3. **Honor MIT licenses:** Include MIT license texts where applicable
4. **Follow BuildStream terms:** Maintain compliance with LGPL 2.1

### Disclaimer

This project is provided as-is. The authors are not responsible for any legal issues arising from the use of this project or its outputs.

Users building distributions based on this project are responsible for:
- License compliance
- Legal clearance for all included components
- Proper attribution of used licenses
- Distribution of source code where required

### For More Information

- See upstream project licenses at their respective sources
- Review LICENSE files in component sources
- Consult LICENSES.txt in built images (when generated)

---

**Project Status:** Open Source (GPL/LGPL/MIT compatible)  
**Compliance:** Users responsible for ensuring compliance
